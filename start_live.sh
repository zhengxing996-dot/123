#!/usr/bin/env bash
set -euo pipefail

# 一键启动脚本：默认直接跑你给的直播链接
URL_DEFAULT="https://www.youtube.com/live/p25iBUTAKeE?si=yp2V9-DaF6Le46Ea"
URL="${1:-$URL_DEFAULT}"

# 可通过环境变量覆盖参数
CHUNK_SECONDS="${CHUNK_SECONDS:-8}"
WHISPER_MODEL="${WHISPER_MODEL:-small}"
COMPUTE_TYPE="${COMPUTE_TYPE:-int8}"
DEVICE="${DEVICE:-cpu}"
SOURCE_LANG="${SOURCE_LANG:-auto}"
TRANSLATE_TO="${TRANSLATE_TO:-中文}"
SUMMARY_LANG="${SUMMARY_LANG:-中文}"
SUMMARY_EVERY="${SUMMARY_EVERY:-60}"
LLM_MODEL="${LLM_MODEL:-gpt-4o-mini}"
SAVE_JSONL="${SAVE_JSONL:-output/live_log.jsonl}"

if ! command -v python >/dev/null 2>&1; then
  echo "[错误] 未找到 python，请先安装 Python 3.10+"
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "[错误] 未找到 ffmpeg，请先安装后再运行"
  exit 1
fi

echo "[1/3] 安装 Python 依赖..."
python -m pip install -r requirements.txt

echo "[2/3] 启动实时转写/翻译/总结..."
echo "      URL: $URL"
echo "      输出: $SAVE_JSONL"

echo "[3/3] 运行中（Ctrl+C 停止）"
exec python live_translate_summarize.py "$URL" \
  --chunk-seconds "$CHUNK_SECONDS" \
  --whisper-model "$WHISPER_MODEL" \
  --compute-type "$COMPUTE_TYPE" \
  --device "$DEVICE" \
  --source-lang "$SOURCE_LANG" \
  --translate-to "$TRANSLATE_TO" \
  --summary-lang "$SUMMARY_LANG" \
  --summary-every "$SUMMARY_EVERY" \
  --llm-model "$LLM_MODEL" \
  --save-jsonl "$SAVE_JSONL"
