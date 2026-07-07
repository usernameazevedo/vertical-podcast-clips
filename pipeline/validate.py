#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mechanical sanity check for cuts. Reads cuts.tsv + each episode .vtt and scores,
without judgement, what can be measured: duration, whether the cut starts/ends on
a complete sentence, and speech density (dead air). It does NOT replace the content
rubric (criteria.md) -- it's a seatbelt against obvious mistakes (starting/ending
mid-sentence, silence at the start).

Usage:
  python3 validate.py [--dir DIR] [--cuts cuts.tsv] [--only EP07]

Note: with ASR transcripts that lack punctuation, the "starts/ends whole sentence"
flags are noisy -- treat them as a reminder to check the boundary, not a verdict.
"""
import argparse, os, sys
from render import parse_vtt, ts_to_sec, load_cuts, resolve_source, cut_segments

def first_last_cues(cues, start, end):
    return [(a, b, t) for (a, b, t) in cues if b > start and a < end and t.strip()]

SENT_END = (".", "!", "?", "…")

def ends_complete(text):
    return text.strip().endswith(SENT_END)

def starts_complete(cues, start):
    # Whole start if the cue ending right before 'start' closed a sentence
    # (or there is nothing before). Heuristic over the .vtt cues.
    before = [c for c in cues if c[1] <= start + 0.4]
    if not before:
        return True
    return before[-1][2].strip().endswith(SENT_END)

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.dirname(here) or os.getcwd())
    ap.add_argument("--cuts", default=os.path.join(here, "cuts.tsv"))
    ap.add_argument("--only", default=None)
    a = ap.parse_args()

    rows = load_cuts(a.cuts)
    if a.only:
        rows = [r for r in rows if r["ep"] == a.only]
    if not rows:
        sys.exit("No cuts in cuts.tsv.")

    vtt_cache = {}
    by_ep = {}
    for r in rows:
        by_ep.setdefault(r["ep"], []).append(r)

    print(f"{'CUT':<12}{'DUR':>6}  {'START':<7}{'END':<6}"
          f"{'WPS':<7}{'WHOLE/2':<9}  ALERTS")
    print("-" * 78)

    for ep, eprows in by_ep.items():
        for n, r in enumerate(eprows, 1):
            segs = cut_segments(r)
            first_start = segs[0][0]
            dur = sum(b - aa for (aa, b) in segs)
            src = resolve_source(a.dir, ep, r["source"])
            vtt = os.path.splitext(src)[0] + ".vtt"
            if vtt not in vtt_cache:
                vtt_cache[vtt] = parse_vtt(vtt)
            allcues = vtt_cache[vtt]
            sel = []
            for (sa, sb) in segs:
                sel += first_last_cues(allcues, sa, sb)

            alerts = []
            if not sel:
                alerts.append("no subtitle in range (vtt?)")
                last_txt = ""
                words = 0
            else:
                last_txt = sel[-1][2]
                words = sum(len(c[2].split()) for c in sel)
                if sel[0][0] - first_start > 1.5:
                    alerts.append("silence at start")

            startok = starts_complete(allcues, first_start)
            endok = ends_complete(last_txt)
            wps = (words / dur) if dur > 0 else 0

            if not startok:
                alerts.append("doesn't start on a whole sentence")
            if not endok:
                alerts.append("doesn't end on a whole sentence")
            if wps and wps < 1.5:
                alerts.append("low speech (dead air)")
            if len(segs) > 1:
                alerts.append(f"{len(segs)} stitched pieces")

            whole = (1 if startok else 0) + (1 if endok else 0)
            tag = f"{ep}_cut{n}"
            print(f"{tag:<12}{int(dur):>4}s   "
                  f"{'yes' if startok else 'no':<7}{'yes' if endok else 'no':<6}"
                  f"{wps:<7.1f}{whole:<9}  {'; '.join(alerts) if alerts else 'ok'}")
        print()

    print("Note: DUR is informational (length is free). WHOLE/2 = starts and ends on a "
          "full sentence. The content score (0-10) is the criteria.md rubric.")

if __name__ == "__main__":
    main()
