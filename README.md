# YouTube Live 实时翻译+总结小工具（改进版）

这个小软件用于 **YouTube 直播讲话** 的实时处理：

1. 实时转写（`faster-whisper` 本地）
2. 实时翻译（可选，OpenAI）
3. 定时总结（可选，OpenAI；无 Key 时自动降级）
4. 可选写入 JSONL，便于后续做字幕/检索

> 示例链接：`https://www.youtube.com/live/p25iBUTAKeE?si=yp2V9-DaF6Le46Ea`

## 安装

### 1) 系统依赖

- Python 3.10+
- `ffmpeg`

### 2) Python 依赖

```bash
pip install -r requirements.txt
```

## 快速开始

## 一键启动（推荐）

直接运行（默认就是你给的直播链接）：

```bash
./start_live.sh
```

如果要改直播链接：

```bash
./start_live.sh "https://www.youtube.com/live/你的链接"
```

可选环境变量（覆盖默认参数）：

```bash
export OPENAI_API_KEY="你的key"
export DEVICE=cpu
export SOURCE_LANG=auto
export TRANSLATE_TO=中文
export SAVE_JSONL=output/live_log.jsonl
./start_live.sh
```

```bash
python live_translate_summarize.py "https://www.youtube.com/live/p25iBUTAKeE?si=yp2V9-DaF6Le46Ea" \
  --chunk-seconds 8 \
  --whisper-model small \
  --source-lang auto \
  --translate-to 中文 \
  --summary-lang 中文 \
  --summary-every 60 \
  --save-jsonl output/live_log.jsonl
```

## OpenAI 可选配置

如需更自然翻译/总结：

```bash
export OPENAI_API_KEY="你的key"
```

如果未设置 Key：
- 翻译会输出“未翻译”提示并保留原文
- 总结使用简易规则摘要（最近几条合并）

## 参数说明

- `url`：YouTube 直播链接
- `--chunk-seconds`：每次送转写的音频块长度（默认 8）
- `--whisper-model`：Whisper 模型，如 `tiny/base/small/medium`
- `--compute-type`：如 `int8`（CPU 推荐）或 `float16`
- `--device`：`cpu/cuda/auto`
- `--source-lang`：语音原语言代码，如 `en/ja/zh`，`auto` 自动识别
- `--translate-to`：翻译目标语言；`none/auto` 表示不翻译
- `--summary-every`：多少秒输出一次总结
- `--context-lines`：总结窗口保留最近多少条
- `--llm-model`：OpenAI 模型（翻译/总结）
- `--save-jsonl`：可选 JSONL 输出路径

## 这版改进点

- 降低默认分块时长（12s -> 8s），提升“实时感”。
- 移除重复临时文件中转，降低 I/O 开销。
- 支持显式 `--source-lang`，避免自动识别误判带来的延迟。
- 增加 `--save-jsonl`，方便后续生成字幕、搜索、审阅。
- 在退出时补充 `yt-dlp/ffmpeg` 错误信息，排障更直接。

## 注意

- 直播本身通常有平台延迟，结果不保证逐字同步。
- Whisper 首次加载模型会较慢。
- 建议在 `tmux/screen` 中长时间运行。
