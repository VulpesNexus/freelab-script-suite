"""Which scripts the learned method may be offered in: the rule train.py --export applies to the scores
of designs the model never saw. Plain Python (no numpy), so that the tests read the rule itself.

summaries: {script: {method: {"mae": ..., "mae kerned": ...}, ...}}, the methods being "zero" (no
kerning), "halfkern", "contour", "average" (of halfkern and contour: Auto Kerning's default
suggestion), and "learned"; designs: {script: the designs scored} (families that kern a script alike
count as one).

- Latin, which the model is trained and checked on first, must beat every other method, no kerning
  included, over all pairs and on the pairs the fonts kern.
- Another script needs at least MIN_DESIGNS designs (one design cannot show that a method holds for
  designs it never saw), and the model must beat the default suggestion over all pairs and on kerned
  pairs.
- With BEAT_NO_KERNING (off: the owner's decision, pending), another script must also beat no kerning
  on kerned pairs: on the pairs fonts do kern, a suggestion no closer than leaving them alone tells the
  designer nothing (Devanagari, 2026-11-14: 26.0 against 25.7, where every method was further from the
  fonts than no kerning at all). Over all pairs no kerning is never asked to be beaten: most pairs are
  not kerned, so leaving every pair alone wins that measure against every measured method in every
  script (the default too), and Auto Kerning lists only the pairs a method would move.
"""

MIN_DESIGNS = 2
BEAT_NO_KERNING = False  # True: the stricter rule above (it would take the suggestion out of Devanagari)
MEASURES = ("mae", "mae kerned")
OTHERS = ("zero", "halfkern", "contour", "average")


def reasons(script, summary, designs, beat_no_kerning=None):
    """Why the learned method may not be offered in a script ([] when it may): each reason a short text.
    beat_no_kerning: the stricter rule on or off (None: BEAT_NO_KERNING)."""
    if beat_no_kerning is None:
        beat_no_kerning = BEAT_NO_KERNING
    learned = summary.get("learned")
    if learned is None:
        return ["not scored"]
    found = []
    if script == "latin":
        for measure in MEASURES:
            for method in OTHERS:
                if method in summary and learned[measure] >= summary[method][measure]:
                    found.append("%s %s not below %s's" % (measure, "%.1f" % learned[measure], method))
        return found
    if designs < MIN_DESIGNS:
        found.append("%d design%s scored, %d needed" % (designs, "" if designs == 1 else "s", MIN_DESIGNS))
    for measure in MEASURES:
        if learned[measure] >= summary["average"][measure]:
            found.append("%s %.1f not below the default's %.1f" % (measure, learned[measure], summary["average"][measure]))
    if beat_no_kerning and learned["mae kerned"] >= summary["zero"]["mae kerned"]:
        found.append("mae kerned %.1f not below no kerning's %.1f" % (learned["mae kerned"], summary["zero"]["mae kerned"]))
    return found


def refused(scripts, summaries, designs, beat_no_kerning=None):
    """{script: reasons} for each script asked for that the learned method may not be offered in (one
    not scored at all included)."""
    found = {}
    for script in scripts:
        if script not in summaries:
            found[script] = ["not scored"]
            continue
        why = reasons(script, summaries[script], designs.get(script, 0), beat_no_kerning)
        if why:
            found[script] = why
    return found
