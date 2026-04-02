#!/usr/bin/env python3
import argparse
import json
import os
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time
import wave
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM


@dataclass
class SegmentResult:
    ts: float
    text: str
    translated: str


class LLMHelper:
    def __init__(self, model: str):
        self.model = model
        self.client = None
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            from openai import OpenAI

            self.client = OpenAI(api_key=api_key)

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def translate(self, text: str, target_lang: str) -> str:
        if target_lang.lower() in {"auto", "none"}:
            return text

        if not self.enabled:
            return f"[未翻译: 未设置 OPENAI_API_KEY] {text}"

        prompt = (
            f"请把下面这段口语翻译成{target_lang}，保持简洁自然，只返回翻译文本。\n\n{text}"
        )
        try:
            resp = self.client.responses.create(model=self.model, input=prompt)
            return resp.output_text.strip()
        except Exception as e:  # pragma: no cover
            return f"[翻译失败: {e}] {text}"

    def summarize(self, items: Deque[str], summary_lang: str) -> str:
        src = "\n".join(items).strip()
        if not src:
            return ""

        if not self.enabled:
            lines = list(items)[-3:]
            return "（简易总结）" + " / ".join(lines)

        prompt = f"你是会议速记助手。请用{summary_lang}总结下面最近的发言，输出3条要点。\n\n{src}"
        try:
            resp = self.client.responses.create(model=self.model, input=prompt)
            return resp.output_text.strip()
        except Exception as e:  # pragma: no cover
            return f"总结失败: {e}"


def build_audio_pipeline(url: str):
    ytdlp_cmd = ["yt-dlp", "-q", "-f", "bestaudio", "-o", "-", url]
    ffmpeg_cmd = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-f",
        "s16le",
        "-ac",
        str(CHANNELS),
        "-ar",
        str(SAMPLE_RATE),
        "pipe:1",
    ]

    ytdlp_proc = subprocess.Popen(ytdlp_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ffmpeg_proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=ytdlp_proc.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if ytdlp_proc.stdout:
        ytdlp_proc.stdout.close()

    return ytdlp_proc, ffmpeg_proc


def pcm_to_temp_wav_path(pcm: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        wav_path = tf.name

    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)

    return wav_path


def append_jsonl(path: str, row: dict):
    payload = json.dumps(row, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(payload + "\n")


def transcribe_worker(
    in_q: "queue.Queue[bytes]",
    out_q: "queue.Queue[SegmentResult]",
    stop_event: threading.Event,
    llm: LLMHelper,
    target_lang: str,
    model_size: str,
    compute_type: str,
    device: str,
    source_lang: str,
):
    from faster_whisper import WhisperModel

    whisper = WhisperModel(model_size, device=device, compute_type=compute_type)

    while not stop_event.is_set():
        try:
            pcm = in_q.get(timeout=0.2)
        except queue.Empty:
            continue

        if pcm is None:
            break

        wav_path = pcm_to_temp_wav_path(pcm)

        try:
            kwargs = {"vad_filter": True}
            if source_lang.lower() != "auto":
                kwargs["language"] = source_lang
            segments, _ = whisper.transcribe(wav_path, **kwargs)

            text = " ".join(seg.text.strip() for seg in segments).strip()
            if not text:
                continue

            translated = llm.translate(text, target_lang=target_lang)
            out_q.put(SegmentResult(ts=time.time(), text=text, translated=translated))
        finally:
            try:
                os.remove(wav_path)
            except OSError:
                pass


def safe_read_process_stderr(proc: subprocess.Popen, limit: int = 1200) -> str:
    if not proc.stderr:
        return ""
    try:
        raw = proc.stderr.read(limit)
        return raw.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def main():
    parser = argparse.ArgumentParser(description="YouTube Live 实时转写 + 翻译 + 总结")
    parser.add_argument("url", help="YouTube 直播链接")
    parser.add_argument("--chunk-seconds", type=int, default=8, help="每段音频时长（秒）")
    parser.add_argument("--whisper-model", default="small", help="faster-whisper 模型，如 tiny/base/small/medium")
    parser.add_argument("--compute-type", default="int8", help="faster-whisper compute_type，如 int8/float16")
    parser.add_argument("--device", default="cpu", help="Whisper 运行设备：cpu/cuda/auto")
    parser.add_argument("--source-lang", default="auto", help="语音源语言（如 en/ja/zh）；auto 自动识别")
    parser.add_argument("--translate-to", default="中文", help="翻译目标语言；auto/none 表示不翻译")
    parser.add_argument("--summary-lang", default="中文", help="总结输出语言")
    parser.add_argument("--summary-every", type=int, default=60, help="每隔多少秒输出一次总结")
    parser.add_argument("--context-lines", type=int, default=12, help="总结窗口保留最近多少条译文")
    parser.add_argument("--llm-model", default="gpt-4o-mini", help="翻译/总结使用的 OpenAI 模型")
    parser.add_argument("--save-jsonl", default="", help="将每条结果保存到 JSONL 文件")
    args = parser.parse_args()

    stop_event = threading.Event()

    def _handle_sigint(_sig, _frame):
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_sigint)

    llm = LLMHelper(args.llm_model)

    ytdlp_proc, ffmpeg_proc = build_audio_pipeline(args.url)
    if not ffmpeg_proc.stdout:
        print("无法读取音频流。")
        sys.exit(1)

    in_q: "queue.Queue[bytes]" = queue.Queue(maxsize=16)
    out_q: "queue.Queue[SegmentResult]" = queue.Queue()

    worker = threading.Thread(
        target=transcribe_worker,
        args=(
            in_q,
            out_q,
            stop_event,
            llm,
            args.translate_to,
            args.whisper_model,
            args.compute_type,
            args.device,
            args.source_lang,
        ),
        daemon=True,
    )
    worker.start()

    bytes_per_second = SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS
    chunk_bytes = bytes_per_second * args.chunk_seconds
    buf = bytearray()

    summary_buffer: Deque[str] = deque(maxlen=args.context_lines)
    last_summary = time.time()

    save_path = args.save_jsonl.strip()
    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

    print("开始处理，按 Ctrl+C 停止...\n")

    try:
        while not stop_event.is_set():
            data = ffmpeg_proc.stdout.read(4096)
            if not data:
                if ffmpeg_proc.poll() is not None:
                    print("[错误] ffmpeg 进程提前退出。")
                    break
                continue

            buf.extend(data)
            while len(buf) >= chunk_bytes:
                chunk = bytes(buf[:chunk_bytes])
                del buf[:chunk_bytes]
                try:
                    in_q.put(chunk, timeout=1.0)
                except queue.Full:
                    print("[警告] 转写队列已满，丢弃一段音频")

            while True:
                try:
                    result = out_q.get_nowait()
                except queue.Empty:
                    break

                ts = time.strftime("%H:%M:%S", time.localtime(result.ts))
                print(f"[{ts}] 原文: {result.text}")
                if result.translated != result.text:
                    print(f"[{ts}] 译文: {result.translated}")
                print("-")

                summary_buffer.append(result.translated)

                if save_path:
                    append_jsonl(
                        save_path,
                        {
                            "timestamp": result.ts,
                            "human_time": ts,
                            "source_text": result.text,
                            "translated_text": result.translated,
                        },
                    )

            if time.time() - last_summary >= args.summary_every and summary_buffer:
                summary = llm.summarize(summary_buffer, args.summary_lang)
                print("\n========== 实时总结 ==========")
                print(summary)
                print("============================\n")
                if save_path:
                    append_jsonl(
                        save_path,
                        {
                            "timestamp": time.time(),
                            "human_time": time.strftime("%H:%M:%S"),
                            "summary": summary,
                        },
                    )
                last_summary = time.time()

    finally:
        stop_event.set()
        try:
            in_q.put(None, timeout=0.2)
        except Exception:
            pass

        worker.join(timeout=4)

        for p in (ffmpeg_proc, ytdlp_proc):
            if p and p.poll() is None:
                p.terminate()

        # drain minimal stderr for diagnostics
        yt_err = safe_read_process_stderr(ytdlp_proc)
        ff_err = safe_read_process_stderr(ffmpeg_proc)
        if yt_err:
            print(f"[yt-dlp] {yt_err}")
        if ff_err:
            print(f"[ffmpeg] {ff_err}")

        print("已停止。")


if __name__ == "__main__":
    main()
