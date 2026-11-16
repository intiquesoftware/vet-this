# Where the scan patterns come from

`scripts/safety_scan.py` checks 48 patterns plus install-hook, binary and outside-host inventories. Each one maps to a technique documented in
public research or incident reports. Last checked against these sources: 2026-11-15.

## Sources

| Key | Source | What it covers |
|---|---|---|
| SKILLS | Malicious Agent Skills in the Wild: A Large-Scale Security Empirical Study, arXiv 2602.06547 (Feb 2026). https://arxiv.org/abs/2602.06547 | 98,380 community skills scanned; 157 confirmed malicious; 13 techniques with counts. The most direct evidence for Claude skills. |
| TPA | Invariant Labs, "MCP Security Notification: Tool Poisoning Attacks" (Apr 2025). https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks | Tool poisoning, shadowing, rug pulls, the `<IMPORTANT>` and `sidenote` tricks. |
| MCP20 | agyn, "The MCP Attack Surface: Top-20 Documented Attacks (2026)". https://agyn.io/blog/mcp-attack-surface | Survey of MCP incidents and CVEs, including CVE-2025-59536 / CVE-2026-21852 (Claude Code project files), CVE-2025-53107 (command injection), CyberArk full-schema poisoning. |
| OWASP | OWASP Top 10 for Agentic Applications (Dec 2025), especially ASI02 Tool Misuse and ASI04 Agentic Supply Chain. https://genai.owasp.org | Risk categories and mitigations (least privilege, approval for actions). |
| NPM26 | 2026 npm, PyPI and Crates supply-chain campaigns (TrapDoor, Shai-Hulud-style worms, TanStack / Mistral AI compromise), as reported by Socket, GitGuardian, Microsoft and The Hacker News. | Install hooks, import-time execution, `build.rs`, cloud metadata theft, publish-token theft, zero-width text planted in `CLAUDE.md` and `.cursorrules`. |

## Pattern map

| Scanner category | Patterns | Sources |
|---|---|---|
| Remote code execution | `curl \| sh`, PowerShell `iex`, eval or exec of decoded data, dynamic eval, shell from Python or Node, reverse shells, pickle / marshal / unsafe YAML loads, shell commands built from variables | SKILLS (SC1, SC2, SC3: 25% of all malicious findings), MCP20 (CVE-2025-53107), NPM26 |
| Credentials and secrets | SSH keys, cloud credentials, browser and keychain data, crypto wallets, API keys from the environment, whole-environment dumps, AI tool auth files, cloud metadata and secret stores, `ANTHROPIC_BASE_URL` / `enableAllProjectMcpServers`, package-publishing tokens, `.env` files | SKILLS (E2, E3, PE3: 23%), TPA, MCP20 (CVE-2025-59536), NPM26 |
| Exfiltration and network | webhooks and paste sites, uploads, telemetry, plus the list of every outside host in shipped code | SKILLS (E1, P3: 19%; "undocumented network endpoints" were the top hidden feature, 47%) |
| Persistence | LaunchAgents, cron, services, shell startup edits, writes to `CLAUDE.md` / `AGENTS.md` / `.cursorrules` / MCP config | NPM26 (TrapDoor), MCP20 (CVE-2025-54135) |
| Destructive | `rm -rf ~`, force push, open permissions, sudo | SKILLS (PE2) |
| Claude agent controls | permission bypass flags, hooks, pre-approved Bash, MCP server entries | SKILLS (hook abuse, `--dangerously-skip-permissions`, `.mcp.json` hijacking) |
| Prompt injection | instruction overrides, "don't tell / don't ask the user", `<IMPORTANT>` blocks, coercive language ("NON-NEGOTIABLE"), shadowing text, `sidenote`-style smuggling parameters, hidden HTML comments | SKILLS (P1, P2, P4: 28%), TPA, OWASP ASI01/ASI02 |
| Anti-forensics | history wiping, RAM-disk workspaces, hidden background jobs | SKILLS (stealth skills) |
| Reconnaissance | nmap, netstat, arp, whoami | SKILLS (E3, E4) |
| Network exposure | servers bound to `0.0.0.0` | MCP20 (exposed MCP endpoints, CVE-2025-49596) |
| Obfuscation | base64 and hex blobs, obfuscator.io names, zero-width characters | SKILLS (SC3, P2), NPM26 |
| Install-time hooks (inventory) | npm pre/post install, custom `setup.py`, Cargo `build.rs`, Python `.pth` files | NPM26 |
| Risky combinations | credentials + outbound upload; credentials + remote code; agent instructions + remote code | SKILLS (credential theft + exfiltration in 36.9% of malicious skills) |

## Where malicious content hides

Per SKILLS, 84% of malicious findings were in `SKILL.md` text, not code. So the scanner runs
every rule on `SKILL.md`, `CLAUDE.md`, `AGENTS.md`, skill `references/`, hook, plugin and MCP
files, and only injection and installer rules on plain READMEs.

## What a static scan cannot catch

These need the tool to run, so vet-this reports them as limits, not as checked:

- **Rug pulls:** a tool's description changes after you approve it (TPA).
- **Poisoned tool output:** a clean tool returns a fake error asking for secrets (MCP20, CyberArk ATPA).
- **Instructions planted in data** the tool reads later, such as GitHub issues, documents or database rows (MCP20).
- **Dormant triggers:** code that waits for a date, a codeword or several sessions. SKILLS found most unconfirmed suspects were dormant.
- **Release binaries** that differ from the source you reviewed.
