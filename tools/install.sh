#!/bin/bash
# AI Second Brain · one-time installer (macOS, Apple Silicon recommended)
# Installs: ffmpeg, yt-dlp, deno, Python 3.12, open-source claude-watch, local mlx-whisper,
# and a launchd queue runner that processes videos dropped into <brain>/inbox/queue/.
#
# Usage:
#   bash tools/install.sh                       # brain at ~/LLM/AI第二大脑
#   AI_BRAIN_DIR=~/Notes/brain bash tools/install.sh
set -e
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRAIN="${AI_BRAIN_DIR:-$HOME/LLM/AI第二大脑}"
BRAIN="${BRAIN/#\~/$HOME}"
TOOLS="$BRAIN/tools"

echo "==> 0/6 第二大脑目录 / brain folder: $BRAIN"
mkdir -p "$BRAIN"/{raw,sources,wiki,assets,inbox/queue,inbox/logs} "$TOOLS"
for f in README.md index.md; do [ -f "$BRAIN/$f" ] || cp "$REPO/template/brain/$f" "$BRAIN/$f"; done
[ -f "$BRAIN/brain.config.json" ] || sed "s#\"~/LLM/AI第二大脑\"#\"${BRAIN/#$HOME/~}\"#" "$REPO/template/brain/brain.config.example.json" > "$BRAIN/brain.config.json"
cp "$REPO/tools/runner.py" "$TOOLS/runner.py"

echo "==> 1/6 Homebrew"
if ! command -v brew >/dev/null; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$($b shellenv)"; done
fi
if ! command -v brew >/dev/null; then
  echo "Installing Homebrew (asks for your Mac password)"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

echo "==> 2/6 ffmpeg, yt-dlp, deno, python@3.12, git"
brew install ffmpeg yt-dlp deno python@3.12 git

echo "==> 3/6 claude-watch (MIT, https://github.com/devinilabs/claude-watch)"
if [ -d "$TOOLS/claude-watch/.git" ]; then git -C "$TOOLS/claude-watch" pull --ff-only
else git clone --depth 1 https://github.com/devinilabs/claude-watch "$TOOLS/claude-watch"; fi
echo "--remote-components ejs:github" > "$TOOLS/claude-watch/yt-dlp.conf"

echo "==> 4/6 Python venv + local Whisper (no API key needed)"
"$(brew --prefix python@3.12)/bin/python3.12" -m venv "$TOOLS/.venv"
"$TOOLS/.venv/bin/pip" install -q --upgrade pip mlx-whisper "yt-dlp[default]"
date > "$TOOLS/.ejs_installed"

echo "==> 5/6 launchd queue runner (com.aibrain.videoqueue)"
PL="$HOME/Library/LaunchAgents/com.aibrain.videoqueue.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PL" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.aibrain.videoqueue</string>
  <key>ProgramArguments</key><array><string>$TOOLS/.venv/bin/python3</string><string>$TOOLS/runner.py</string></array>
  <key>EnvironmentVariables</key><dict><key>AI_BRAIN_DIR</key><string>$BRAIN</string></dict>
  <key>WatchPaths</key><array><string>$BRAIN/inbox/queue</string></array>
  <key>StartInterval</key><integer>300</integer>
  <key>StandardOutPath</key><string>$BRAIN/inbox/logs/launchd.log</string>
  <key>StandardErrorPath</key><string>$BRAIN/inbox/logs/launchd.log</string>
</dict></plist>
EOF
launchctl unload "$PL" 2>/dev/null || true
launchctl load "$PL"

echo "==> 6/6 done"
echo "ok" > "$TOOLS/.installed"
echo ""
echo "✅ 装好了 / Installed. Brain: $BRAIN"
echo "   Open it in Obsidian (Open folder as vault), then send Claude a YouTube link."
