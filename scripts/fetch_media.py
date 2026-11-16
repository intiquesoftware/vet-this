#!/usr/bin/env python3
"""Fetch a video, reel or short (any yt-dlp site) or read a local video file, then
write: info, caption text, transcript, and a small set of frames for Claude to look at.

Usage:
  python3 fetch_media.py <url-or-path> --out <work-dir> [--max-frames 16]

Writes <work-dir>/summary.json and prints its path. Nothing from the media is executed.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

URL_RE = re.compile(r"https?://[^\s)>\]\"']+")
REPO_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
GATE_RE = re.compile(
    r"(comment\s+[\"'“”]?\w+[\"'“”]?|link in (my )?bio|dm me|drop a comment|"
    r"type\s+[\"'“”]\w+[\"'“”]|send me a message|join (my|the) (discord|community|skool))",
    re.I,
)


def run(cmd, timeout=600):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def vtt_to_text(path):
    lines, last = [], None
    for raw in open(path, encoding="utf-8", errors="ignore"):
        line = raw.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or "-->" in line:
            continue
        if line.isdigit():
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line and line != last:
            lines.append(line)
            last = line
    return " ".join(lines)


def duration_of(path):
    if not shutil.which("ffprobe"):
        return None
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def transcribe(video, out):
    """Local transcription. Returns (text, engine) or ("", reason)."""
    if shutil.which("mlx_whisper"):
        run(["mlx_whisper", video, "--model", "mlx-community/whisper-large-v3-turbo",
             "-f", "txt", "-o", out, "--output-name", "transcript"], timeout=1800)
        engine = "mlx_whisper"
    elif shutil.which("whisper"):
        run(["whisper", video, "--model", "base", "--output_format", "txt", "--output_dir", out], timeout=1800)
        base = os.path.splitext(os.path.basename(video))[0]
        if os.path.exists(os.path.join(out, base + ".txt")):
            os.replace(os.path.join(out, base + ".txt"), os.path.join(out, "transcript.txt"))
        engine = "openai-whisper"
    else:
        return "", "no local whisper installed"
    p = os.path.join(out, "transcript.txt")
    return (open(p, encoding="utf-8").read().strip() if os.path.exists(p) else ""), engine


def grab_frames(video, out, max_frames):
    if not shutil.which("ffmpeg"):
        return []
    fdir = os.path.join(out, "frames")
    os.makedirs(fdir, exist_ok=True)
    # Scene changes first.
    run(["ffmpeg", "-v", "error", "-i", video, "-vf", "select='gt(scene,0.3)',scale=768:-2",
         "-vsync", "vfr", "-frames:v", str(max_frames), os.path.join(fdir, "scene_%03d.jpg")])
    frames = sorted(glob.glob(os.path.join(fdir, "scene_*.jpg")))
    if len(frames) < 4:
        dur = duration_of(video) or 30
        n = max(4, min(max_frames, int(dur // 3) or 4))
        fps = n / max(dur, 1)
        run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"fps={fps:.4f},scale=768:-2",
             "-frames:v", str(n), os.path.join(fdir, "even_%03d.jpg")])
        frames = sorted(glob.glob(os.path.join(fdir, "*.jpg")))
    frames = frames[:max_frames]
    # One contact sheet so Claude can see every frame in a single image read.
    if frames:
        cols = 5 if len(frames) > 8 else 4
        rows = (len(frames) + cols - 1) // cols
        lst = os.path.join(fdir, "list.txt")
        with open(lst, "w") as f:
            f.writelines(f"file '{p}'\n" for p in frames)
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
             "-vf", f"scale=300:-2,tile={cols}x{rows}", "-frames:v", "1",
             os.path.join(out, "contact-sheet.jpg")])
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-frames", type=int, default=16)
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    summary = {"source": a.source, "work_dir": out, "notes": []}

    if os.path.exists(a.source):
        video = os.path.abspath(a.source)
        info = {}
    else:
        if not shutil.which("yt-dlp"):
            sys.exit("yt-dlp is not installed. Install it (brew install yt-dlp) or download the video and pass the file path.")
        r = run(["yt-dlp", "--no-warnings", "--no-playlist", "--write-info-json",
                 "--write-subs", "--write-auto-subs", "--sub-langs", "en.*,en", "--sub-format", "vtt",
                 "-f", "bv*[height<=720]+ba/b[height<=720]/b", "--merge-output-format", "mp4",
                 "-o", os.path.join(out, "media.%(ext)s"), a.source], timeout=900)
        vids = [p for p in glob.glob(os.path.join(out, "media.*"))
                if p.rsplit(".", 1)[-1] in ("mp4", "mkv", "webm", "mov")]
        if not vids:
            summary["notes"].append("download failed: " + (r.stderr.strip().splitlines() or ["unknown error"])[-1])
            json.dump(summary, open(os.path.join(out, "summary.json"), "w"), indent=2)
            print(os.path.join(out, "summary.json"))
            sys.exit(2)
        video = vids[0]
        ij = os.path.join(out, "media.info.json")
        info = json.load(open(ij)) if os.path.exists(ij) else {}

    desc = info.get("description") or ""
    summary.update({
        "video": video,
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "channel": info.get("channel") or info.get("uploader_id"),
        "upload_date": info.get("upload_date"),
        "duration_s": info.get("duration") or duration_of(video),
        "views": info.get("view_count"),
        "likes": info.get("like_count"),
        "comments": info.get("comment_count"),
        "page_url": info.get("webpage_url"),
        "description": desc,
    })
    with open(os.path.join(out, "description.txt"), "w", encoding="utf-8") as f:
        f.write(desc)

    # Transcript: captions first, then local whisper.
    subs = sorted(glob.glob(os.path.join(out, "media*.vtt")))
    text, engine = "", ""
    if subs:
        text, engine = vtt_to_text(subs[0]), "captions"
        with open(os.path.join(out, "transcript.txt"), "w", encoding="utf-8") as f:
            f.write(text)
    else:
        text, engine = transcribe(video, out)
    words = len(text.split())
    summary["transcript_engine"] = engine
    summary["transcript_words"] = words
    summary["transcript_path"] = os.path.join(out, "transcript.txt") if text else None
    if words < 15:
        summary["notes"].append("little or no speech (likely music only); rely on caption and on-screen text in frames")

    summary["frames"] = grab_frames(video, out, a.max_frames)
    sheet = os.path.join(out, "contact-sheet.jpg")
    summary["contact_sheet"] = sheet if os.path.exists(sheet) else None
    if re.search(r"full (video|tutorial|breakdown)|link in (my )?bio|on (my )?youtube", blob := desc + " " + text, re.I):
        summary["notes"].append("creator points to a longer video or bio link; find it, since it usually names the real tool")

    blob = desc + "\n" + text
    summary["urls_found"] = sorted(set(u.rstrip(".,") for u in URL_RE.findall(blob)))
    summary["github_repos_found"] = sorted({f"{o}/{r.removesuffix('.git')}" for o, r in REPO_RE.findall(blob)})
    gates = sorted({m.group(0) for m in GATE_RE.finditer(blob)})
    summary["engagement_gates"] = gates
    if gates:
        summary["notes"].append("source is gated behind engagement (comment/DM/bio link); no public repo named")

    p = os.path.join(out, "summary.json")
    json.dump(summary, open(p, "w"), indent=2)
    print(p)


if __name__ == "__main__":
    main()
