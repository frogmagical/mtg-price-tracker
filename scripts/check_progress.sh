#!/usr/bin/env bash
# 画像ダウンロードと日本語名エンリッチメントの進捗確認

DOWNLOAD_LOG="/tmp/download_images.log"
ENRICH_LOG="/tmp/enrich_ja_names.log"
API="https://oxstj9q420.execute-api.ap-northeast-1.amazonaws.com"

hr() { printf '%.0s─' {1..60}; echo; }

# ── 画像ダウンロード ────────────────────────────────────────
hr
echo "📸 画像ダウンロード (S3)"
hr

if pgrep -f "download_images.py" > /dev/null 2>&1; then
  STATUS="実行中"
else
  STATUS="停止中"
fi

if [[ -f "$DOWNLOAD_LOG" ]]; then
  python3 - "$DOWNLOAD_LOG" "$STATUS" <<'PY'
import sys, re

log_path, status = sys.argv[1], sys.argv[2]
with open(log_path) as f:
    lines = f.readlines()

progress_lines = [l for l in lines if l.startswith("[")]
errors = [l for l in lines if "failed" in l]

print(f"  状態    : {status}")
if progress_lines:
    last = progress_lines[-1].strip()
    m = re.match(r'\[(\d+)/(\d+)\] (.+?): ', last)
    if m:
        cur, total, card = int(m.group(1)), int(m.group(2)), m.group(3)
        pct = 100 * cur / total
        bar_len = 30
        filled = int(bar_len * cur / total)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"  進捗    : [{bar}] {cur:,}/{total:,} ({pct:.1f}%)")
        print(f"  最新    : {card}")
print(f"  エラー  : {len(errors)}件")
PY
else
  echo "  ログなし ($DOWNLOAD_LOG)"
fi

# ── 日本語名エンリッチメント ────────────────────────────────
hr
echo "🈳 日本語名エンリッチメント"
hr

if pgrep -f "enrich_japanese_names.py" > /dev/null 2>&1; then
  JA_STATUS="実行中"
else
  JA_STATUS="停止中"
fi

if [[ -f "$ENRICH_LOG" ]]; then
  python3 - "$ENRICH_LOG" "$JA_STATUS" <<'PY'
import sys, re

log_path, status = sys.argv[1], sys.argv[2]
with open(log_path) as f:
    content = f.read()

print(f"  状態    : {status}")

# ページ進捗
pages = re.findall(r'Page (\d+): \d+ cards \(total so far: (\d+)\)', content)
if pages:
    last_page, last_mapped = pages[-1]
    print(f"  Scryfallページ: {last_page} ページ完了 / ユニーク {int(last_mapped):,} 件取得")

# 確定数
m = re.search(r'Found (\d+) unique Japanese', content)
if m:
    found = int(m.group(1))
    print(f"  マッピング確定: {found:,} 件")

# DB更新完了
m = re.search(r'Updated (\d+) cards', content)
if m:
    updated = int(m.group(1))
    print(f"  DB更新完了  : {updated:,} 件")
elif "Updating DynamoDB" in content:
    print(f"  DB更新      : 実行中...")
PY
else
  echo "  状態    : $JA_STATUS"
  echo "  ログなし ($ENRICH_LOG)"
fi

# ── DynamoDB 現在の日本語名件数 (API経由) ──────────────────
hr
echo "📊 DynamoDB 現在の状態 (API)"
hr

RESP_FILE=$(mktemp)
if curl -sf "$API/cards" -o "$RESP_FILE" 2>/dev/null; then
  python3 - "$RESP_FILE" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
cards = data.get("cards", [])
total = len(cards)
with_ja = sum(1 for c in cards if c.get("card_name_ja"))
pct = 100 * with_ja / total if total else 0
bar_len = 30
filled = int(bar_len * with_ja / total) if total else 0
bar = "█" * filled + "░" * (bar_len - filled)
print(f"  総カード  : {total:,}件")
print(f"  日本語名  : [{bar}] {with_ja:,}件 ({pct:.1f}%)")
PY
else
  echo "  API 取得失敗"
fi
rm -f "$RESP_FILE"

hr
