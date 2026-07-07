#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render every clip in one shot from a cut-definition file (cuts.tsv).

For each cut it produces: a 16:9 horizontal clip, an .srt (re-based from the
episode .vtt), and a 9:16 vertical clip. For each episode it writes a curation
.docx. This collapses dozens of manual ffmpeg calls + docs into one command.

Usage:
  python3 render.py [--dir DIR] [--burn] [--dry-run] [--only EP07]
    --dir     project folder (default: parent of pipeline/, or cwd)
    --burn    burn the .srt subtitles into the 9:16 (Shorts style)
    --dry-run print what it would do, write only .srt/.docx (no video ffmpeg)
    --only    render a single episode (e.g. --only EP07)
    --no-vertical    only 16:9 + .srt (skip the 9:16)
    --only-vertical  only the 9:16 from existing 16:9 (don't re-render 16:9)
    --vertical-mode  crop (default, 9:16 centered on the speaker) | blur (blurred bg)

cuts.tsv format (TAB-separated, with a header). Recognized columns:
  ep  source  start  end  title  quote  theme  why  score  cx  segments
- ep       episode label (also the per-episode output folder name)
- source   video filename (looked up in <dir>/<source> or <dir>/<ep>/<source>)
- start/end  timestamps (HH:MM:SS[.mmm]); ignored if 'segments' is set
- cx       optional 0-1 horizontal face center for the 9:16 crop (else DEFAULT)
- segments optional 'ini->fim;ini->fim' to stitch complementary pieces into one cut
Blank lines and lines starting with # are ignored.

ffmpeg/ffprobe are taken from $FFMPEG/$FFPROBE or from PATH.
"""
import argparse, os, re, shutil, subprocess, sys

FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = os.environ.get("FFPROBE") or shutil.which("ffprobe") or "ffprobe"

ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
       "-c:a", "aac", "-b:a", "192k"]

# 9:16 'crop': full-height 9:16 window centered on the speaker (locked camera).
# Horizontal face center per episode, as a 0-1 fraction of width. Override per
# cut with the 'cx' column, or per episode here. Falls back to DEFAULT.
CROP_CENTER = {}          # e.g. {"EP01": 0.52, "EP02": 0.60}
DEFAULT_CROP_CENTER = 0.5

# 9:16 'blur' (legacy): blurred 1080x1920 background + centered video.
VERTICAL_BLUR_FILTER = (
    "[0:v]split=2[bg][fg];"
    "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
    "crop=1080:1920,boxblur=luma_radius=40:luma_power=2[bgb];"
    "[fg]scale=1080:-2[fgs];"
    "[bgb][fgs]overlay=(W-w)/2:(H-h)/2"
)

# Curation .docx labels (keep short; edit here to localize).
DOCX = {
    "heading": "{ep} — cuts",
    "cut": "Cut {n}: {title}",
    "score": "  (score {score}/10)",
    "timestamp": "Timestamp: ",
    "theme": "Theme: ",
    "why": "Why this cut: ",
}

def resolve_source(proj, ep, source):
    """Find the source video: accepts <proj>/<source> or <proj>/<ep>/<source>,
    so it works whether the full video sits in the project root or already in
    the episode folder."""
    for cand in (os.path.join(proj, source), os.path.join(proj, ep, source)):
        if os.path.exists(cand):
            return cand
    return os.path.join(proj, source)

def ts_to_sec(t):
    t = t.strip().replace(",", ".")
    parts = [float(p) for p in t.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts
    return h * 3600 + m * 60 + s

def sec_to_srt(s):
    if s < 0:
        s = 0
    h = int(s // 3600); s -= h * 3600
    m = int(s // 60);   s -= m * 60
    whole = int(s); ms = int(round((s - whole) * 1000))
    if ms == 1000:
        whole += 1; ms = 0
    return f"{h:02d}:{m:02d}:{whole:02d},{ms:03d}"

# ---- parse the episode VTT to build a per-cut .srt ------------------------
_CUE_TIME = re.compile(
    r"(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{3})"
)

def parse_vtt(path):
    """Return a list of (start_sec, end_sec, text)."""
    cues = []
    if not os.path.exists(path):
        return cues
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    i = 0
    while i < len(lines):
        m = _CUE_TIME.search(lines[i])
        if m:
            ini = ts_to_sec(m.group(1)); fim = ts_to_sec(m.group(2))
            i += 1
            txt = []
            while i < len(lines) and lines[i].strip() and not _CUE_TIME.search(lines[i]):
                txt.append(lines[i].strip())
                i += 1
            cues.append((ini, fim, " ".join(txt)))
        else:
            i += 1
    return cues

def write_srt_for_cut(vtt_cues, start, end, out_path):
    return write_srt_multi(vtt_cues, [(start, end)], out_path)

def write_srt_multi(vtt_cues, segs, out_path):
    """Write an .srt for a cut of 1+ segments, re-basing each segment by the
    sum of the previous segment durations (subtitles follow the stitch)."""
    n = 0
    offset = 0.0
    blocks = []
    for (a, b) in segs:
        sel = [(max(x, a), min(y, b), t)
               for (x, y, t) in vtt_cues if y > a and x < b and t]
        for (x, y, t) in sel:
            n += 1
            blocks.append(f"{n}\n{sec_to_srt(x-a+offset)} --> "
                          f"{sec_to_srt(y-a+offset)}\n{t}\n")
        offset += (b - a)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(blocks) + ("\n" if blocks else ""))
    return n

# ---- ffmpeg ---------------------------------------------------------------
def run(cmd, dry):
    if dry:
        print("   [dry-run]", " ".join(f'"{c}"' if " " in c else c for c in cmd))
        return
    subprocess.run(cmd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def cut_segments(r):
    """List of (start,end) in seconds. If the 'segments' column is set it wins
    (1+ pieces separated by ';', each 'ini->fim'); this stitches neighbouring
    pieces that complete one story. Otherwise falls back to start/end."""
    seg = (r.get("segments") or "").strip()
    if seg:
        out = []
        for part in seg.split(";"):
            part = part.strip()
            if not part:
                continue
            a, b = re.split(r"->", part, maxsplit=1)
            out.append((ts_to_sec(a), ts_to_sec(b)))
        if out:
            return out
    return [(ts_to_sec(r["start"]), ts_to_sec(r["end"]))]

def render_horizontal(src, segs, out, dry):
    """Render 1+ segments concatenated into a single 16:9 (one encode pass)."""
    if len(segs) == 1:
        a, b = segs[0]
        run([FFMPEG, "-y", "-ss", str(a), "-to", str(b), "-i", src] + ENC + [out], dry)
        return
    cmd = [FFMPEG, "-y"]
    for (a, b) in segs:
        cmd += ["-ss", str(a), "-to", str(b), "-i", src]
    n = len(segs)
    fc = "".join(f"[{i}:v:0][{i}:a:0]" for i in range(n)) + \
         f"concat=n={n}:v=1:a=1[v][a]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]"] + ENC + [out]
    run(cmd, dry)

def probe_wh(path, default=(3840, 2160)):
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
            capture_output=True, text=True, check=True)
        w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
        return w, h
    except Exception:
        return default

def _burn_suffix(srt):
    style = "FontName=Arial,FontSize=14,Outline=2,Shadow=0,MarginV=120"
    esc = srt.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return f"subtitles='{esc}':force_style='{style}'"

def render_vertical(cut16x9, out, srt, burn, dry, mode="crop", cx=DEFAULT_CROP_CENTER):
    burn_ok = burn and srt and os.path.exists(srt)
    if mode == "crop":
        # full-height 9:16 window centered on the speaker, then scale to 1080x1920.
        iw, ih = (3840, 2160) if dry else probe_wh(cut16x9)
        cw = int(round(ih * 9 / 16)); cw -= cw % 2
        x = int(round(iw * cx - cw / 2))
        x = max(0, min(x, iw - cw)); x -= x % 2
        vf = f"crop={cw}:{ih}:{x}:0,scale=1080:1920,setsar=1"
        if burn_ok:
            vf += "," + _burn_suffix(srt)
        cmd = [FFMPEG, "-y", "-i", cut16x9, "-vf", vf] + ENC + [out]
    else:  # blur (legacy): complex filtergraph, map audio explicitly
        vf = VERTICAL_BLUR_FILTER
        if burn_ok:
            vf += "[v];[v]" + _burn_suffix(srt)
        cmd = ([FFMPEG, "-y", "-i", cut16x9, "-filter_complex", vf, "-map", "0:a?"]
               + ENC + [out])
    run(cmd, dry)

# ---- per-episode curation .docx -------------------------------------------
def ensure_docx():
    try:
        import docx  # noqa
        return True
    except ImportError:
        print("-> installing python-docx...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                        "--user", "--break-system-packages", "python-docx"],
                       check=False)
        try:
            import docx  # noqa
            return True
        except ImportError:
            print("!! python-docx unavailable; skipping .docx")
            return False

def write_docx(ep, rows, out_path):
    import docx
    d = docx.Document()
    d.add_heading(DOCX["heading"].format(ep=ep), level=0)
    for n, r in enumerate(rows, 1):
        title = DOCX["cut"].format(n=n, title=r.get("title", ""))
        if r.get("score"):
            title += DOCX["score"].format(score=r["score"])
        d.add_heading(title, level=1)
        p = d.add_paragraph()
        p.add_run(DOCX["timestamp"]).bold = True
        p.add_run(f"{r['start']} → {r['end']}")
        if r.get("theme"):
            p = d.add_paragraph()
            p.add_run(DOCX["theme"]).bold = True
            p.add_run(r["theme"])
        if r.get("why"):
            p = d.add_paragraph()
            p.add_run(DOCX["why"]).bold = True
            p.add_run(r["why"])
        if r.get("quote"):
            q = d.add_paragraph(); q.style = "Intense Quote"
            q.add_run(r["quote"])
    d.save(out_path)

# ---- main -----------------------------------------------------------------
def load_cuts(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        header = None
        for line in fh:
            s = line.rstrip("\n")
            if not s.strip() or s.lstrip().startswith("#"):
                continue
            cols = s.split("\t")
            if header is None:
                header = [c.strip() for c in cols]
                continue
            row = {header[i]: (cols[i].strip() if i < len(cols) else "")
                   for i in range(len(header))}
            rows.append(row)
    return rows

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.dirname(here) or os.getcwd())
    ap.add_argument("--cuts", default=None)
    ap.add_argument("--burn", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default=None)
    ap.add_argument("--no-vertical", action="store_true",
                    help="skip the 9:16 (only 16:9 + .srt)")
    ap.add_argument("--only-vertical", action="store_true",
                    help="only the 9:16 from existing 16:9 (don't re-render 16:9)")
    ap.add_argument("--vertical-mode", choices=["crop", "blur"], default="crop",
                    help="crop = 9:16 centered on the speaker (default); blur = blurred bg")
    a = ap.parse_args()

    proj = a.dir
    cuts_file = a.cuts or os.path.join(here, "cuts.tsv")
    if not os.path.exists(cuts_file):
        sys.exit(f"ERROR: cuts.tsv not found at {cuts_file}")

    # Output layout: one folder per episode inside <dir>, holding the full
    # video (+ transcript) and two subfolders:
    #   <dir>/<EP>/horizontal/  (16:9 + .srt)
    #   <dir>/<EP>/vertical/    (9:16)
    #   <dir>/<EP>/<EP>_cuts.docx
    rows = load_cuts(cuts_file)
    if a.only:
        rows = [r for r in rows if r["ep"] == a.only]
    if not rows:
        sys.exit("No cuts to render.")

    have_docx = ensure_docx()

    by_ep = {}
    for r in rows:
        by_ep.setdefault(r["ep"], []).append(r)

    vtt_cache = {}
    total = 0
    for ep, eprows in by_ep.items():
        ep_dir = os.path.join(proj, ep)
        h_dir = os.path.join(ep_dir, "horizontal")
        v_dir = os.path.join(ep_dir, "vertical")
        os.makedirs(h_dir, exist_ok=True)
        if not a.no_vertical:
            os.makedirs(v_dir, exist_ok=True)
        for n, r in enumerate(eprows, 1):
            src = resolve_source(proj, ep, r["source"])
            if not os.path.exists(src):
                print(f"!! missing source: {src} (skipping {ep} cut {n})")
                continue
            segs = cut_segments(r)
            dur = sum(b - aa for (aa, b) in segs)
            h_out = os.path.join(h_dir, f"{ep}_cut{n}.mp4")
            srt   = os.path.join(h_dir, f"{ep}_cut{n}.srt")
            v_out = os.path.join(v_dir, f"{ep}_cut{n}_9x16.mp4")

            vtt = os.path.splitext(src)[0] + ".vtt"
            if vtt not in vtt_cache:
                vtt_cache[vtt] = parse_vtt(vtt)
            ncues = write_srt_multi(vtt_cache[vtt], segs, srt)

            pieces = f"{len(segs)} pieces, " if len(segs) > 1 else ""
            print(f"[{ep} cut {n}] {pieces}{int(dur)}s  ({ncues} subs)")
            if not a.only_vertical:
                render_horizontal(src, segs, h_out, a.dry_run)
            elif not os.path.exists(h_out) and not a.dry_run:
                print(f"!! missing 16:9 base: {h_out} (skipping)")
                continue
            if not a.no_vertical:
                cx = float(r["cx"]) if r.get("cx") else \
                    CROP_CENTER.get(ep, DEFAULT_CROP_CENTER)
                render_vertical(h_out, v_out, srt, a.burn, a.dry_run,
                                mode=a.vertical_mode, cx=cx)
            total += 1

        if have_docx:
            doc_out = os.path.join(ep_dir, f"{ep}_cuts.docx")
            if a.dry_run:
                print(f"   [dry-run] would write {doc_out}")
            else:
                write_docx(ep, eprows, doc_out)
                print(f"-> doc: {os.path.basename(doc_out)}")

    print(f"\nDone: {total} cuts ({'DRY-RUN' if a.dry_run else 'rendered'}).")

if __name__ == "__main__":
    main()
