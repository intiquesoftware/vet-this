#!/usr/bin/env bash
# vet-this preflight: report which free tools are available. Never installs anything.
# Exit 0 = core tools present (git, python3, curl). Optional tools are reported as warnings.

missing_core=0
check() {
  local name="$1" kind="$2" hint="$3"
  if command -v "$name" >/dev/null 2>&1; then
    echo "ok       $name"
  else
    if [ "$kind" = core ]; then
      echo "MISSING  $name  (required)  install: $hint"
      missing_core=1
    else
      echo "missing  $name  (optional)  install: $hint"
    fi
  fi
}

check git      core     "xcode-select --install   (macOS)"
check python3  core     "brew install python"
check curl     core     "preinstalled on macOS"
check yt-dlp   optional "brew install yt-dlp   (needed for video and reel links)"
check ffmpeg   optional "brew install ffmpeg   (needed for video frames)"
check ffprobe  optional "brew install ffmpeg"
if command -v mlx_whisper >/dev/null 2>&1; then
  echo "ok       mlx_whisper"
elif command -v whisper >/dev/null 2>&1; then
  echo "ok       whisper (openai-whisper)"
else
  echo "missing  mlx_whisper  (optional)  install: pipx install mlx-whisper   (Apple Silicon; or pipx install openai-whisper elsewhere)"
fi
if [ -n "${GITHUB_TOKEN:-}" ]; then
  echo "ok       GITHUB_TOKEN set (5000 GitHub API calls/hour)"
else
  echo "note     GITHUB_TOKEN not set (60 GitHub API calls/hour; fine for a few reviews)"
fi

exit $missing_core
