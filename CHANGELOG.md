# Changelog

All notable changes to this skill are listed here. Versions follow [semver](https://semver.org/):
patch = fixes and scanner tuning, minor = new patterns, sources or checks, major = a change to the
report format or profile file.

## [1.0.0] - 2026-11-15

First public release.

### Added
- `SKILL.md`: review a repo, YouTube video, Instagram reel or other video link and answer three
  questions: (A) does it live up to the hype, (B) is it safe to install and use, (C) is it a fit
  for your work. Never installs or runs the subject.
- `scripts/safety_scan.py`: static scan with 48 patterns mapped to published research
  (`references/pattern-sources.md`), an outside-host list, and flags for the risky combinations
  real stealers use. Agent files such as `SKILL.md` get the full rule set.
- `scripts/fetch_media.py`: downloads a video with yt-dlp or reads a local file, then writes the
  caption, transcript (captions first, then local whisper), frames and a contact sheet. Flags
  engagement-gated posts and "full video on YouTube" leads.
- `scripts/repo_stats.py`: public GitHub signals through the REST API, no gh CLI needed.
- `scripts/md_to_html.py`: turns `report.md` into a styled, self-contained `report.html`.
- `scripts/preflight.sh`: reports which free tools are installed. Never installs anything.
- `references/`: report template, safety checklist, pattern sources and an example profile.
- `tests/smoke.sh`: offline smoke tests with planted fixtures. No network, nothing installed.
