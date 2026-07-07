# Cut rubric — what makes a short-form clip work

Proven short-form criteria (Reels / Shorts / TikTok). Each cut gets a 0–10 score when
you pick it, and **must come with a reason** (the `why` column in cuts.tsv): the winning
criterion can differ from cut to cut, but the reason is mandatory.

> _(Portuguese version: [criteria.pt.md](criteria.pt.md).)_

## Gate (pass/fail — before scoring)
- **Theme:** matches the theme you're targeting for this batch (decide up front how many
  cuts and which theme). If it's off-theme, drop it — the score doesn't matter.

## The 5 criteria (0–2 each → 0–10 total)

1. **Hook in the first 1–3s** — opens with something that grabs: a question, a concrete
   number, a counter-intuitive claim, or tension. No "so, um, like…" ramp-up.
2. **Standalone** — understandable without having heard the episode. One clear idea, not
   leaning on context that already went by.
3. **Payoff / tension** — there's a turn, an insight, a conclusion or emotion. It builds
   and delivers. A lukewarm cut with no climax won't hold.
4. **Quotable** — has a strong line that sums the cut up and becomes the caption/thumbnail.
5. **Whole start and end + pace** — the cut should **start at the beginning of a sentence
   and end at the end of a sentence** (never mid-idea), with no ramble at the top.
   **Length is free:** if the content justifies it, the cut can be long — don't penalize
   size. What matters is that it's a complete thought with no filler.

## Full context and stitched cuts
- **Prefer full context:** cuts of **1–2 minutes are welcome** when they deliver the whole
  idea (setup + development + payoff), not just the one-liner.
- **Stitch pieces:** if two or more **nearby, complementary** pieces tell a better story
  together, join them into a single cut via the `segments` column in cuts.tsv
  (`start->end;start->end`). `render.py` concatenates the pieces into one video and the
  `.srt` follows the stitch. Use it when the pieces complete each other (e.g. the thesis +
  the analogy that illustrates it), not to splice unrelated topics.

## Using the score
- **8–10:** strong cut, publish.
- **6–7:** good, improves by nudging the start/end timestamps.
- **< 6:** probably drop it or re-pick the passage.

## The reason (required)
In the `why` column, write in one line why THIS cut was picked — which criterion it nails.
E.g. "strong hook + quotable line"; "emotional payoff of the loss story"; "concrete number
grabs and it's standalone".

## Mechanical check (validate.py)
`validate.py` checks what can be measured without judgement — whether the cut **starts and
ends on a whole sentence**, speech density (dead air), and silence at the start. Duration
is shown for info only (not a penalty). It **does not replace** the rubric; it's a seatbelt
against obvious mistakes. With ASR transcripts that lack punctuation, the whole-sentence
flags are noisy — treat them as a reminder to check the boundary, not a verdict.
