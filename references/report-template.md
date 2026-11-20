# vet-this: {Subject name}

<p class="meta">Reviewed {YYYY-MM-DD} · Source: {link} · Repo: {owner/repo or "none found"}</p>

> **Hype (A):** {Lives up to it / Partly / Doesn't hold / Can't verify}. {One sentence why.}
> **Safety (B):** {Safe / Safe with caveats / Don't install / Can't assess}. {One sentence why.}
> **Fit (C):** {Good fit for X / Maybe, for X / No fit / Skipped (no profile)}. {One sentence why.}

## Bottom line

{2 to 3 sentences. What it is, whether to bother, and the single most important reason.}

## (A) Do the claims hold up?

Each claim made in the video, post or README, checked against what the code can actually do.

| # | Claim | Where it was said | Verdict | Evidence |
|---|---|---|---|---|
| 1 | {claim, in plain words; one claim per row} | {0:42 in video / caption / on screen at 1:10 / README "Features"} | {Holds / Partly / Doesn't hold / Can't verify} | {file path with line or function, or URL; for Partly, the gap; for Can't verify, what would settle it} |

**Overall (A):** {Lives up to it / Partly / Doesn't hold / Can't verify}, because {the headline claim's row and the one or two rows that decided it}.

**Context (not evidence):** {n} stars, {n} forks, {n} contributors, last push {date}; {organic growth, or a spike that matches the post date}. Popularity does not change any verdict above.

**Project health details (context only)**

| Signal | Value | Read |
|---|---|---|
| Stars / forks | {n} / {n} | {organic, or a spike that matches the video's post date} |
| Age, last push | {days} / {days ago} | |
| Contributors, commits | {n} / {n} | {one-person weekend project vs maintained} |
| Releases | {latest tag, date} | |
| Most discussed issues | {top 2 to 3 titles} | {what users complain about} |
| Owner | {account age, repos, followers} | |

## (B) Is it safe to install and use?

**What installing would do:** {exact steps from the README, and what each one touches}

**What it does once running:** {files it reads and writes, network calls and where they go, hooks it registers, permissions it asks for}

| Severity | Finding | Location | Read in context |
|---|---|---|---|
| {high/med/low} | {finding} | `{path:line}` | {benign because... / real concern because...} |

**Safer way to try it (if any):** {e.g. read-only mode, pin a version, run in a throwaway folder, skip the hook}

## (C) Is it for you?

**Overlaps with what you already have:** {installed skills, tools or apps that already do this}

**Where it could help:** {named projects or workflows, and the concrete job it would do}

**Cost:** {money, API keys, accounts, setup time, ongoing upkeep}

## Recommendation

{One of: Install / Install with these limits / Watch and recheck in N weeks / Skip. Then the next step, as text only. vet-this never installs.}

## Sources

- {every URL, file path and command output relied on}

<div class="frames">
<!-- Optional: 4 to 8 key frames copied to ./frames/ for video or reel sources -->
</div>
