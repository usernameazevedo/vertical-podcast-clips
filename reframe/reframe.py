#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multicam-aware 9:16 reframe.

A vertical clip cut straight from a multicam podcast has one problem: when the
edit cuts to a WIDE two-shot (both people at the table), a single-person crop
shows the empty center and neither speaker. This tool fixes that:

- single-person shots (close-ups)  -> a tall 9:16 crop centered on the speaker
- WIDE two-shots (both people)      -> a stacked SPLIT: person A on top, person B
                                       on the bottom, each filling half of the 9:16

You tell it which time ranges are wide (via scene detection, see find_wides.sh),
and the face centers. It renders each segment and joins them with a hard cut
(default) or a cross-dissolve (--crossfade).

Usage:
  reframe.py IN OUT --closeup 0.52 --split 0.30,0.82 --wide 16.9-23.5 [more...]

Options:
  --closeup CX        face center (0-1 of width) for single-person shots [0.5]
  --split A,B         face centers (0-1) of the two people in the wide shot;
                      A = top window, B = bottom window
  --wide S-E [S-E]    wide two-shot time ranges (seconds), which become the split
  --split-height F    each split window's source height, as a fraction of frame [0.31]
  --split-y F         top of the split crop, as a fraction of frame height [0.32]
  --crossfade D       cross-dissolve of D seconds at each transition [0 = hard cut]

Each split window is 1080x960 (the 9:16 is 1080x1920). Tighter split = smaller
--split-height. ffmpeg/ffprobe from $FFMPEG/$FFPROBE or PATH.
"""
import argparse, os, re, shutil, subprocess, sys, tempfile

FF = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
FP = os.environ.get("FFPROBE") or shutil.which("ffprobe") or "ffprobe"
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k"]

def dur(f):
    return float(subprocess.check_output(
        [FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]).strip())

def wh(f):
    out = subprocess.check_output(
        [FP, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "csv=p=0", f], text=True).strip()
    w, h = (int(x) for x in out.split(",")[:2])
    return w, h

def even(n):
    n = int(round(n)); return n - (n % 2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--closeup", type=float, default=0.5)
    ap.add_argument("--split", default="0.3,0.7")   # top,bottom face centers
    ap.add_argument("--wide", nargs="*", default=[])
    ap.add_argument("--split-height", type=float, default=0.31)
    ap.add_argument("--split-y", type=float, default=0.32)
    ap.add_argument("--crossfade", type=float, default=0.0)
    a = ap.parse_args()

    W, H = wh(a.inp)
    total = dur(a.inp)
    top_cx, bot_cx = (float(x) for x in a.split.split(","))

    # single-person crop: full height, 9:16 wide, centered at closeup
    cw = even(H * 9 / 16)
    cx0 = max(0, min(even(W * a.closeup - cw / 2), W - cw))
    CLOSEUP_VF = f"crop={cw}:{H}:{cx0}:0,scale=1080:1920,setsar=1"

    # split window: aspect 1080:960 = 1.125; height = split-height * frame height
    sh = even(H * a.split_height)
    sw = even(sh * 1.125)
    sy = even(H * a.split_y)
    def sx(cx):
        return max(0, min(even(W * cx - sw / 2), W - sw))
    SPLIT_FC = (
        f"[0:v]crop={sw}:{sh}:{sx(top_cx)}:{sy},scale=1080:960[t];"
        f"[0:v]crop={sw}:{sh}:{sx(bot_cx)}:{sy},scale=1080:960[b];"
        f"[t][b]vstack[vv];[vv]setsar=1,fps=30[v]")

    # build the segment list: crop for gaps, split for wide ranges
    wides = []
    for w in a.wide:
        s, e = w.split("-"); wides.append((float(s), float(e)))
    wides.sort()
    segs = []; cur = 0.0
    for s, e in wides:
        if cur < s - 0.05:
            segs.append((cur, s, "crop"))
        segs.append((s, e, "split")); cur = e
    if cur < total - 0.05:
        segs.append((cur, total, "crop"))
    if not segs:
        segs = [(0.0, total, "crop")]

    tmp = tempfile.mkdtemp(); paths = []
    try:
        for i, (s, e, kind) in enumerate(segs):
            o = os.path.join(tmp, f"s{i}.mp4")
            if kind == "crop":
                subprocess.run([FF, "-y", "-ss", str(s), "-to", str(e), "-i", a.inp,
                                "-vf", CLOSEUP_VF + ",fps=30"] + ENC + [o],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run([FF, "-y", "-ss", str(s), "-to", str(e), "-i", a.inp,
                                "-filter_complex", SPLIT_FC, "-map", "[v]", "-map", "0:a"]
                               + ENC + [o],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            paths.append(o)

        if len(paths) == 1:
            shutil.copy(paths[0], a.out)
        elif a.crossfade <= 0:
            # hard cut: concat demuxer (streams share codec/params)
            lst = os.path.join(tmp, "list.txt")
            with open(lst, "w") as fh:
                for p in paths:
                    fh.write(f"file '{p}'\n")
            subprocess.run([FF, "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", a.out],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # cross-dissolve: xfade (video) + acrossfade (audio); both shrink by D
            D = a.crossfade
            durs = [dur(p) for p in paths]
            ins = []
            for p in paths:
                ins += ["-i", p]
            vlab, alab, acc, fc = "0:v", "0:a", durs[0], ""
            for i in range(1, len(paths)):
                off = acc - D
                fc += f"[{vlab}][{i}:v]xfade=transition=fade:duration={D}:offset={off:.3f}[vx{i}];"
                fc += f"[{alab}][{i}:a]acrossfade=d={D}[ax{i}];"
                vlab, alab, acc = f"vx{i}", f"ax{i}", acc + durs[i] - D
            subprocess.run([FF, "-y"] + ins + ["-filter_complex", fc.rstrip(";"),
                            "-map", f"[{vlab}]", "-map", f"[{alab}]"] + ENC + [a.out],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"OK {os.path.basename(a.out)}  {dur(a.out):.1f}s  "
              f"({len(segs)} segments, {'hard cut' if a.crossfade<=0 else f'{a.crossfade}s dissolve'})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    main()
