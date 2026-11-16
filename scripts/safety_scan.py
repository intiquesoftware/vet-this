#!/usr/bin/env python3
"""Static safety scan of a cloned repo. Reads files only; runs nothing from the repo.

Usage:
  python3 -I safety_scan.py <repo-dir> [--out findings.md]

Prints a markdown report: inventory, then findings by category with file:line.
A finding is a lead for Claude to read in context, not a verdict on its own.
"""
import argparse
import json
import os
import re
import stat
from collections import Counter, defaultdict

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "vendor"}
TEXT_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".bash", ".zsh", ".fish", ".ps1",
            ".rb", ".go", ".rs", ".php", ".pl", ".lua", ".json", ".toml", ".yaml", ".yml", ".md", ".txt",
            ".cfg", ".ini", ".swift", ".java", ".kt", ".c", ".h", ".cpp", ".html", ".plist", ""}
BIN_EXT = {".exe", ".dll", ".so", ".dylib", ".bin", ".app", ".pkg", ".dmg", ".msi", ".jar", ".node", ".wasm", ".pyc"}

# (category, severity, regex, explanation)
RULES = [
    ("Remote code execution", "high", r"(curl|wget)[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b", "pipes a download straight into a shell"),
    ("Remote code execution", "high", r"(iwr|Invoke-WebRequest)[^\n|]*\|\s*iex", "PowerShell download-and-run"),
    ("Remote code execution", "high", r"eval\s*\(\s*(atob|Buffer\.from|base64)", "evaluates decoded data"),
    ("Remote code execution", "high", r"exec\s*\(\s*(base64\.b64decode|bytes\.fromhex|zlib\.decompress|marshal\.loads)", "executes decoded data"),
    ("Remote code execution", "med", r"\bnew Function\s*\(|\beval\s*\(", "dynamic code evaluation"),
    ("Remote code execution", "med", r"subprocess\.[a-zA-Z_]+\([^)]*shell\s*=\s*True", "shell command from Python"),
    ("Remote code execution", "med", r"child_process|execSync\(|spawnSync\(", "spawns shell commands from Node"),
    ("Credentials and secrets", "high", r"~/\.ssh|\.ssh/id_|id_rsa|id_ed25519", "touches SSH keys"),
    ("Credentials and secrets", "high", r"~/\.aws|\.aws/credentials|gcloud/credentials|\.kube/config", "touches cloud credentials"),
    ("Credentials and secrets", "high", r"Login Data|Cookies\.binarycookies|/Cookies\b|keychain|security\s+find-(generic|internet)-password", "reads browser or keychain secrets"),
    ("Credentials and secrets", "high", r"wallet\.dat|metamask|\.electrum/|exodus\.wallet|(phantom|exodus|solflare)[^\n]{0,25}wallet", "references crypto wallets"),
    ("Credentials and secrets", "low", r"(ANTHROPIC|OPENAI|GITHUB|AWS|GOOGLE|STRIPE)_[A-Z_]*(KEY|TOKEN|SECRET)", "reads an API key from the environment"),
    ("Credentials and secrets", "med", r"os\.environ\b(?!\.get|\[)|process\.env\b(?!\.)|printenv|\benv\s*>\s*", "reads the whole environment"),
    ("Credentials and secrets", "med", r"\.claude/(settings(\.local)?\.json|\.credentials|projects/)|\.claude\.json|\.codex/auth|\.config/gh/hosts", "reads AI tool or GitHub config or auth"),
    ("Exfiltration and network", "high", r"discord(app)?\.com/api/webhooks|hooks\.slack\.com|api\.telegram\.org/bot|pastebin\.com|transfer\.sh|ngrok", "sends data to a webhook or paste service"),
    ("Exfiltration and network", "med", r"requests\.(post|put)\(|fetch\([^)]*method:\s*['\"]POST|axios\.post|urllib\.request\.urlopen\([^)]*data=", "uploads data somewhere"),
    ("Exfiltration and network", "low", r"posthog|segment\.io|mixpanel|amplitude|sentry\.io|telemetry|analytics", "telemetry or analytics"),
    ("Persistence", "high", r"LaunchAgents|LaunchDaemons|launchctl\s+(load|bootstrap)|crontab\s+-|systemctl\s+enable", "installs something that runs on its own"),
    ("Persistence", "med", r"(>>|>)\s*~?/?[^\s]*\.(zshrc|bashrc|bash_profile|profile|zprofile)", "edits your shell startup file"),
    ("Destructive", "high", r"rm\s+-rf\s+(~|\$HOME|/\s|/\*|\"\$HOME\")", "deletes home or root"),
    ("Destructive", "med", r"git\s+push\s+--force|chmod\s+-R\s+777|sudo\s", "force push, open permissions or sudo"),
    ("Claude agent controls", "high", r"dangerously-skip-permissions|bypassPermissions|\"defaultMode\"\s*:\s*\"(bypassPermissions|acceptEdits)\"", "turns off Claude's permission prompts"),
    ("Claude agent controls", "med", r"\"(PreToolUse|PostToolUse|UserPromptSubmit|SessionStart|Stop|Notification)\"", "registers a Claude Code hook (runs a command automatically)"),
    ("Claude agent controls", "med", r"Bash\(\*\)|\"allow\"\s*:\s*\[[^\]]*\"Bash\b", "pre-approves shell commands"),
    ("Claude agent controls", "med", r"\"mcpServers\"", "adds MCP servers"),
    ("Prompt injection", "high", r"ignore (all |any )?(previous|prior|above) instructions|disregard (the |your |all )?(system|previous|safety)", "tries to override the agent's instructions"),
    ("Prompt injection", "high", r"(do not|don't|never) (tell|inform|mention to|show) the user|without (asking|telling) the user|silently (run|execute|install|send)", "tells the agent to hide actions from the user"),
    ("Prompt injection", "high", r"(do not|don't|never) mention (this|that|it)\b|do not mention in (the )?conversation|(do not|don't|never) ask (the )?user|do not ask (for )?(user )?permission", "secrecy or no-asking order to the agent"),
    ("Prompt injection", "high", r"<important>|</important>", "<IMPORTANT> block, the classic MCP tool-poisoning wrapper"),
    ("Prompt injection", "med", r"non-negotiable|severe violation|you must always comply|failure to comply", "coercive language aimed at the agent"),
    ("Prompt injection", "med", r"(very important|important) side effect on|when this tool is available|(the )?also present \w+ tool", "one tool's text steering another tool (shadowing)"),
    ("Prompt injection", "med", r"\b(sidenote|side_note|content_from_\w+)\b", "hidden parameter used to smuggle data out through a tool call"),
    ("Prompt injection", "med", r"<!--[^>]*\b(claude|assistant|agent|AI|LLM)\b[^>]*\b(ignore|must|always|never|do not|don't|secret|instead|override)\b[^>]*-->", "hidden HTML comment giving an AI instructions"),
    ("Remote code execution", "high", r"/dev/tcp/|\bnc\s+(-e|-c)\b|ncat\s+-e|bash\s+-i\s+>&|socket\.socket\([^)]*\)[^\n]*(subprocess|pty\.spawn|os\.dup2)|pty\.spawn\(", "reverse shell (hands control of the machine to a remote host)"),
    ("Remote code execution", "med", r"pickle\.loads?\(|marshal\.loads\(|yaml\.load\((?![^)]*SafeLoader)", "loads serialized code (can run anything)"),
    ("Remote code execution", "med", r"\bexec(Sync)?\(\s*`[^`]*\$\{", "shell command built from variables (command injection)"),
    ("Credentials and secrets", "high", r"169\.254\.169\.254|metadata\.google\.internal|GetSecretValue|ListSecrets|VAULT_TOKEN", "reaches cloud metadata or secret stores"),
    ("Credentials and secrets", "high", r"ANTHROPIC_BASE_URL|OPENAI_BASE_URL|enableAllProjectMcpServers", "redirects AI API traffic or auto-trusts project MCP servers"),
    ("Credentials and secrets", "med", r"\.npmrc|\.pypirc|\.netrc|\.git-credentials|\.pem\b", "reads package-publishing tokens or key files"),
    ("Credentials and secrets", "low", r"\.env\b(?!\.example|\.sample)", "reads a .env file (normal for its own settings; a concern if it reads other projects')"),
    ("Persistence", "high", r"((>>|>)\s*\S*|open\([^)]*|write(File|FileSync|_text)?\([^)]*|appendFile\w*\([^)]*)(CLAUDE\.md|AGENTS\.md|\.cursorrules|mcp\.json|\.claude/settings)", "writes to AI agent instructions or MCP config"),
    ("Anti-forensics", "med", r"history\s+-c|unset\s+HISTFILE|rm\s+[^\n]*_history|/dev/shm|\bnohup\b[^\n]*&", "hides traces or runs hidden in the background"),
    ("Reconnaissance", "low", r"\bnmap\b|\bnetstat\b|\barp\s+-a\b|\bifconfig\b|\bwhoami\b", "surveys the machine or network"),
    ("Network exposure", "low", r"(host|HOST)\s*[=:]\s*['\"]0\.0\.0\.0['\"]|--host\s+0\.0\.0\.0", "server listens on all network interfaces"),
    ("Obfuscation", "med", r"[A-Za-z0-9+/]{300,}={0,2}", "long base64 blob"),
    ("Obfuscation", "med", r"(\\x[0-9a-fA-F]{2}){40,}", "long hex-escaped string"),
    ("Obfuscation", "med", r"_0x[0-9a-f]{4,}\b", "obfuscator.io-style variable names"),
    ("Obfuscation", "low", r"[​‌‍⁠﻿]", "zero-width characters (can hide text)"),
]
# Text categories that matter even in plain docs (README etc.).
DOC_CATEGORIES = {"Prompt injection", "Remote code execution"}
URL_HOST = re.compile(r"https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
COMMON_HOSTS = re.compile(r"(^|\.)(github\.com|githubusercontent\.com|python\.org|pypi\.org|npmjs\.(com|org)|"
                          r"example\.(com|org)|localhost|w3\.org|schema\.org|mozilla\.org|apple\.com|microsoft\.com|"
                          r"google(apis)?\.com|anthropic\.com|claude\.(ai|com)|openai\.com|shields\.io|readthedocs\.io|"
                          r"wikipedia\.org|stackoverflow\.com|opensource\.org|creativecommons\.org)$", re.I)
# Well-known official installers: piping these to a shell is normal practice, so it is low.
KNOWN_INSTALLERS = re.compile(r"(astral\.sh/uv|claude\.ai/install|get\.docker\.com|raw\.githubusercontent\.com/Homebrew|sh\.rustup\.rs|deno\.land/install|bun\.sh/install|nvm-sh/nvm)", re.I)
# Code that does not ship to users: tests, docs, sites, examples, CI, vendored libraries.
NON_RUNTIME = re.compile(r"(^|/)(tests?|spec|__tests__|docs?|site|examples?|\.github|_vendor|vendor|fixtures|benchmarks?)/")
COMPILED = [(c, s, re.compile(p, re.I), e) for c, s, p, e in RULES]
DEP_FILES = {"package.json", "requirements.txt", "pyproject.toml", "setup.py", "Pipfile", "Cargo.toml",
             "go.mod", "Gemfile", "composer.json", "Package.swift"}
AGENT_FILES = re.compile(r"(SKILL\.md|CLAUDE\.md|AGENTS\.md|hooks\.json|plugin\.json|marketplace\.json|\.mcp\.json|settings(\.local)?\.json)$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--out")
    a = ap.parse_args()
    root = os.path.abspath(a.repo)

    # The repo's own raw.githubusercontent.com prefix, so its own installer is not mistaken for a stranger's.
    own_raw = None
    try:
        m = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(\.git)?\s*$", open(os.path.join(root, ".git", "config")).read(), re.M)
        if m:
            own_raw = f"raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/".lower()
    except OSError:
        pass
    findings = defaultdict(list)
    outside = Counter()
    hosts = defaultdict(set)
    langs, files, binaries, execs, deps, agent_files, install_hooks, minified = Counter(), 0, [], [], {}, [], [], []
    total_bytes = 0

    for d, dirs, fnames in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for fn in fnames:
            p = os.path.join(d, fn)
            rel = os.path.relpath(p, root)
            if os.path.islink(p):
                tgt = os.readlink(p)
                if tgt.startswith("/") or tgt.startswith(".."):
                    findings["Suspicious links"].append(("med", rel, 0, f"symlink points outside the repo: {tgt}"))
                continue
            files += 1
            ext = os.path.splitext(fn)[1].lower()
            try:
                st = os.stat(p)
            except OSError:
                continue
            total_bytes += st.st_size
            langs[ext or "(none)"] += 1
            if ext in BIN_EXT:
                binaries.append(rel)
            if AGENT_FILES.search(fn):
                agent_files.append(rel)
            if fn in DEP_FILES:
                deps[rel] = None
            if ext == ".pth":
                install_hooks.append(f"{rel}: Python .pth file (can run code on every Python start)")
            if ext not in TEXT_EXT or st.st_size > 2_000_000:
                if st.st_size > 0 and ext not in TEXT_EXT and ext not in BIN_EXT and ext not in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".mp4", ".mp3", ".wav", ".woff", ".woff2", ".ttf", ".otf", ".pdf", ".lock", ".css", ".csv"}:
                    with open(p, "rb") as fh:
                        head = fh.read(4)
                    if head[:4] in (b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"MZ\x90\x00") or head[:2] == b"MZ":
                        binaries.append(rel)
                continue
            if st.st_mode & stat.S_IXUSR and ext not in {".sh", ".py", ".bash", ".zsh", ""}:
                execs.append(rel)
            try:
                text = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if fn == "package.json":
                try:
                    pj = json.loads(text)
                    sc = pj.get("scripts", {})
                    for k in ("preinstall", "install", "postinstall", "prepare", "prepublish"):
                        if k in sc:
                            install_hooks.append(f"{rel}: {k} = {sc[k]}")
                    deps[rel] = len(pj.get("dependencies", {})) + len(pj.get("devDependencies", {}))
                except ValueError:
                    pass
            elif fn == "requirements.txt":
                deps[rel] = sum(1 for l in text.splitlines() if l.strip() and not l.startswith("#"))
            elif fn == "setup.py" and re.search(r"cmdclass|class\s+\w+\((install|develop|build_py)\)", text):
                install_hooks.append(f"{rel}: custom setup.py install command")
            elif fn == "build.rs":
                install_hooks.append(f"{rel}: Cargo build script (runs on build)")
            # Agent instruction files are read by the AI, so they get the full rule set:
            # most malicious skill content lives in SKILL.md (arXiv 2602.06547).
            in_skill = os.path.exists(os.path.join(d, "SKILL.md")) or "/references/" in f"/{rel}"
            is_agent_text = bool(AGENT_FILES.search(fn)) or (ext == ".md" and in_skill)
            is_doc = (ext in {".md", ".txt", ""} and not text.startswith("#!") or fn.startswith(".git")) and not is_agent_text
            if not is_doc and not NON_RUNTIME.search(rel):
                for h in URL_HOST.findall(text):
                    if not COMMON_HOSTS.search(h):
                        hosts[h.lower()].add(rel)
            for i, line in enumerate(text.splitlines(), 1):
                if len(line) > 3000:
                    minified.append(f"{rel}:{i}")
                    line = line[:3000]
                is_code = not is_doc and not is_agent_text and ext not in {".json", ".yaml", ".yml", ".toml"}
                if is_code and re.match(r"\s*(#|//|\*|/\*)", line):
                    continue  # code comments are not executed and not read as instructions
                for cat, sev, rx, why in COMPILED:
                    # Plain docs only matter for injection text and copy-paste installers.
                    if is_doc and cat not in DOC_CATEGORIES:
                        continue
                    if is_doc and cat == "Remote code execution" and sev != "high":
                        continue
                    if rx.search(line):
                        if cat == "Remote code execution" and KNOWN_INSTALLERS.search(line):
                            sev, why = "low", "pipes a well-known official installer into a shell"
                        elif cat == "Remote code execution" and own_raw and own_raw in line.lower():
                            sev, why = "med", "pipes the project's own installer into a shell (read that script)"
                        if cat == "Prompt injection" and is_code and sev == "high":
                            sev = "med"  # a string in ordinary code, not text the agent loads as instructions
                        if NON_RUNTIME.search(rel) and not (cat == "Prompt injection" and sev == "high"):
                            outside[cat] += 1
                            continue
                        findings[cat].append((sev, rel, i, why, line.strip()[:160]))

    out = []
    out.append("# Safety scan\n")
    out.append(f"Repo: `{root}`\n")
    out.append("## Inventory\n")
    out.append(f"- Files scanned: {files} ({total_bytes/1e6:.1f} MB)")
    out.append("- Top file types: " + ", ".join(f"{k} {v}" for k, v in langs.most_common(8)))
    out.append("- Dependency manifests: " + (", ".join(f"`{k}`" + (f" ({v} deps)" if v is not None else "") for k, v in deps.items()) or "none"))
    out.append("- Install-time hooks: " + ("; ".join(f"`{h}`" for h in install_hooks) or "none found"))
    out.append("- Agent files (skills, hooks, MCP, settings): " + (", ".join(f"`{x}`" for x in agent_files[:30]) or "none"))
    out.append("- Binaries or compiled files: " + (", ".join(f"`{x}`" for x in binaries[:20]) or "none"))
    out.append("- Unexpected executables: " + (", ".join(f"`{x}`" for x in execs[:20]) or "none"))
    out.append("- Very long (minified) lines: " + (", ".join(minified[:10]) or "none"))
    out.append("- Outside hosts named in shipped code and agent files (compare with what the README says it contacts): "
               + (", ".join(f"`{h}` ({len(v)} files)" for h, v in sorted(hosts.items(), key=lambda kv: -len(kv[1]))[:25]) or "none"))
    out.append("")
    sev_rank = {"high": 0, "med": 1, "low": 2}
    counts = Counter(f[0] for v in findings.values() for f in v)

    # Combinations seen together in confirmed malicious skills (arXiv 2602.06547):
    # credential reads + outbound uploads (36.9% of malicious skills), and remote scripts + credential reads.
    def has(cat, sevs=("high", "med")):
        return any(f[0] in sevs for f in findings.get(cat, []))
    combos = []
    if has("Credentials and secrets") and has("Exfiltration and network"):
        combos.append("reads credentials **and** sends data out (the most common stealer pattern)")
    if has("Credentials and secrets", ("high",)) and has("Remote code execution", ("high",)):
        combos.append("reads credentials **and** downloads or runs remote code")
    if has("Prompt injection", ("high",)) and has("Remote code execution", ("high",)):
        combos.append("instructs the agent **and** runs remote code (hybrid hijacker)")
    if combos:
        out.append("## Risky combinations\n")
        out.extend(f"- {c}" for c in combos)
        out.append("\nThese pairings are what confirmed malicious skills look like. Check whether the same code path does both.\n")

    out.append(f"## Findings: {counts.get('high',0)} high, {counts.get('med',0)} medium, {counts.get('low',0)} low\n")
    out.append("Each finding is a lead. Read the file around the line before judging it.\n")
    for cat in sorted(findings, key=lambda c: min(sev_rank[f[0]] for f in findings[c])):
        items = sorted(findings[cat], key=lambda f: sev_rank[f[0]])
        out.append(f"### {cat} ({len(items)})\n")
        for f in items[:25]:
            sev, rel, ln, why = f[0], f[1], f[2], f[3]
            snippet = f[4] if len(f) > 4 else ""
            out.append(f"- **{sev}** `{rel}:{ln}` {why}" + (f"  \n  `{snippet.replace('`', '')}`" if snippet else ""))
        if len(items) > 25:
            out.append(f"- ...and {len(items) - 25} more")
        out.append("")
    if outside:
        out.append("### Outside shipped code (tests, docs, site, vendored libraries)\n")
        out.append("Counted, not listed: " + ", ".join(f"{k} {v}" for k, v in outside.most_common()) + ". Skim only if the repo's own code looks off.\n")
    if not findings:
        out.append("No pattern matches. That lowers risk but is not proof of safety; still read the entry points.\n")

    txt = "\n".join(out)
    if a.out:
        open(a.out, "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
