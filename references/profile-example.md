# vet-this profile

Copy this file to `~/.claude/vet-this/profile.md` and edit it. vet-this reads it on every run
to judge part (C), "is it for me?", and to know where to save reports. Without a profile,
reports go to `./vet-this-reports/` and part (C) uses only what Claude can see in the
current project.

## Report folder

report_dir: ~/Documents/vet-this-reports

## About me

- What I do: {e.g. solo developer, design agency owner, data analyst}
- Main tools: {e.g. Claude Code on macOS, VS Code, Figma, Premiere}
- Budget for new tools: {e.g. free only / up to $20 a month}
- Hard limits: {e.g. no tools that need my browser cookies; nothing that phones home}

## Read these for context

List files or folders vet-this should read to understand your work. Keep it short.

- {~/path/to/your/projects-list.md}
- {~/path/to/current-priorities.md}

## My projects and workflows

- {Project name}: {one line on what it is and what slows it down}
- {Workflow}: {e.g. weekly client SEO reports, editing short-form video}

## Already installed (optional)

vet-this also lists `~/.claude/skills/` and installed plugins on its own. Add anything else
it should know you already use.

- {tool}: {what you use it for}
