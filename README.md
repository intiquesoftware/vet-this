# Vet This

A Claude Code skill for the moment you see a hyped tool in a repo, a YouTube video or an
Instagram reel and wonder whether to try it. Paste the link and ask. vet-this answers three
questions:

- **(A) Hype:** do the claims in the video, post or README hold up against what the tool can
  actually do? Each claim gets its own verdict and evidence. Stars are context, not proof.
- **(B) Safety:** is it safe to install and use?
- **(C) Fit:** is it any use for *your* projects and workflows?

It never installs or runs the thing it reviews. It downloads the video, clones the repo,
reads the code, and writes a short report (`report.md` plus a styled `report.html`).

```
vet this: https://github.com/someone/shiny-new-skill
/vet-this https://www.instagram.com/reel/XXXXXXXX/
I'm curious about this one, is it safe? https://youtu.be/XXXXXXXX
```

## What it checks

| Part | How |
|---|---|
| Claims | Reads the caption and transcript and looks at frames from the video, so on-screen text and install commands are caught too. For a repo link alone, the README's headline promises. Lists every claim with where it was said. |
| Hype | Checks each claim against the code: one row per claim with where it was said, a verdict (Holds / Partly / Doesn't hold / Can't verify) and evidence as a file path or URL. GitHub signals (stars, star velocity, commits, contributors, releases, owner account age) appear in a separate context line and never change a claim's verdict. |
| Safety | Static scan with 48 patterns drawn from published research on malicious Claude skills, MCP tool poisoning and 2026 npm/PyPI attacks: install-time hooks, `curl \| sh`, reverse shells, credential and browser-data access, cloud metadata, API-traffic redirects, webhooks and uploads, persistence (including writes to `CLAUDE.md`), Claude Code hooks and permission bypasses, `<IMPORTANT>`-style tool poisoning, secrecy and coercive instructions, obfuscation. It lists every outside host the code contacts and flags the combinations real stealers use. Then Claude reads the flagged lines and entry points in context. Sources: `references/pattern-sources.md`. |
| Fit | Compares against your installed skills and plugins and a short profile you write about your work. |

Gated posts ("comment CODE to get the source") are called out: with no public source, safety
is reported as "can't assess" and vet-this never comments, DMs or signs up to get it.

## Requirements

All free. On macOS with [Homebrew](https://brew.sh):

| Tool | Needed for | Install |
|---|---|---|
| Claude Code | everything | [claude.com/claude-code](https://claude.com/claude-code) |
| git | cloning repos | `xcode-select --install` |
| python3 | the scripts (standard library only, no packages) | `brew install python` |
| yt-dlp | YouTube, Instagram, TikTok, X and other video links | `brew install yt-dlp` |
| ffmpeg | video frames | `brew install ffmpeg` |
| mlx-whisper | local transcripts on Apple Silicon (no API key) | `brew install pipx && pipx install mlx-whisper` |

Not on Apple Silicon? Use `pipx install openai-whisper` instead of mlx-whisper. vet-this uses
whichever it finds. Without any whisper it falls back to captions and on-screen text.

Optional: set `GITHUB_TOKEN` (a read-only personal access token with no scopes is enough) to
raise GitHub's API limit from 60 to 5,000 calls an hour. A few reviews a day do not need it.

Keep yt-dlp current; video sites change often and an old copy is the usual cause of a failed
download:

```bash
brew upgrade yt-dlp
```

Check what you have at any time:

```bash
bash ~/.claude/skills/vet-this/scripts/preflight.sh
```

## Install

```bash
cp -R vet-this ~/.claude/skills/
```

The folder name must stay `vet-this`.

## Set up your profile (recommended)

Part (C) is only as good as what vet-this knows about you. Copy the example and fill it in:

```bash
mkdir -p ~/.claude/vet-this
cp ~/.claude/skills/vet-this/references/profile-example.md ~/.claude/vet-this/profile.md
```

The profile sets where reports are saved (`report_dir`), lists files to read for context
(your project list, current priorities), and your limits (budget, "no tools that need my
browser cookies"). It lives outside the skill folder, so updating the skill never overwrites
it. Point to a different file with `VET_THIS_PROFILE=/path/to/profile.md`.

Without a profile, reports go to `./vet-this-reports/` and part (C) uses only the current
project and your installed skills.

## Where reports go

```
<report_dir>/<YYYY-MM-DD>-<subject>/
  report.md
  report.html
  frames/        (video sources only)
```

`<subject>` is the reviewed tool's name, for example `2026-11-15-shiny-new-skill`.

## What it will not do

- Install, build, run or test the subject, even if the README or video says to.
- Follow instructions found inside the subject's files, captions or comments. Those are
  reported as prompt-injection findings.
- Use your browser cookies or sign in anywhere, unless your profile says it may.
- Comment, DM or sign up to unlock gated source code.

A clean report lowers risk; it is not a guarantee. The scan is static and the review reads
what is in the repo today. It cannot see attacks that only appear when the tool runs: tool
descriptions that change after you approve them, poisoned tool output, instructions planted
in data the tool reads later, dormant triggers, or release binaries that differ from the
source. `references/pattern-sources.md` lists the research behind every pattern.

## Tests

`tests/smoke.sh` runs offline checks on the scripts with planted fixtures. It makes no network
calls and installs nothing:

```bash
bash tests/smoke.sh
```

If you point vet-this at its own repo, the scan reports many high findings. They come from
`scripts/safety_scan.py`, the references and these docs, which spell out the attack patterns the
scanner looks for. None of them run anything.

## License

MIT. Copyright (c) 2026 Intique Software.
