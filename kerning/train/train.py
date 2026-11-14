"""Train the learned method on the training set (dataset.py), check it against the other methods on
families it never saw, and export it for Auto Kerning.

    python kerning/train/train.py [--data <dataset.npz>] [--export] [--scripts latin] [--apply-to latin,armenian,georgian]

Cross-validation is grouped by family: no family is ever in both the training and the test part.
The scores are given for every script on its own (the same folds), so that adding a script's pairs
can be checked not to make Latin's worse: --scripts latin trains on Latin's pairs alone, and --apply-to
names the scripts Auto Kerning then uses the model for (its "scripts").
Errors are in units of a 1000-unit em. The model has two stages, gradient-boosted trees each: a
classifier says whether a pair is kerned at all, and a regressor, trained on kerned pairs only, how
much. (One regressor learned to say 0: most common pairs are not kerned.) --export writes
kerning/learned_model.json, evaluated by Auto Kerning in plain Python, when the model beats every
other method both overall and on the pairs the fonts kern.

Python 3 with numpy and scikit-learn.
"""

import argparse
import json
import os
import sys
import time

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir))
os.environ["FREELAB_NO_AUTOSTART"] = "1"
import freelab_auto_kerning as ak  # noqa: E402

MODEL_FILE = os.path.join(HERE, os.pardir, "learned_model.json")
PARAMS = dict(max_iter=150, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=40, l2_regularization=1.0,
              random_state=0, early_stopping=False)  # (its own validation split would mix families: every tree kept)
KERNED = 5 / 1000.0  # a pair kerned by at least this share of the em counts as kerned
CUT = 0.4  # the classifier's probability from which a pair is kerned (0.4 beat 0.5 and 0.6 on kerned pairs)
FEATURES = (["halfkern", "contour", "left kind", "right kind"] + ["spacing " + p for p in ak.SPACING_PAIRS]
            + ["left advance", "right advance"] + ["gap %d" % b for b in range(ak.PROFILE_BANDS)])


SAME_DESIGN_UNITS = 2 / 1000.0  # two fonts kern a pair alike within this share of the em
SAME_DESIGN_SHARE = 0.8  # fonts of one script that kern this share of their kerned pairs alike are one design
SAME_DESIGN_MIN = 20  # (compared on at least this many pairs either of them kerns)


def design_groups(y, script, font, groups, pairs):
    """The family groups, those whose fonts kern one script alike merged: one design under several
    family names (Source Han Sans as Noto Sans JP, SC, and HK; Inter and Inter V) falls in one fold,
    so that no family is scored on its own design seen in training. (number of merges, groups)"""
    parent = dict((g, g) for g in np.unique(groups))

    def root(g):
        while parent[g] != g:
            parent[g] = parent[parent[g]]
            g = parent[g]
        return g

    merges = 0
    for number in np.unique(script):
        rows = np.flatnonzero(script == number)
        names = sorted(set(pairs[rows]))
        column = dict((name, c) for c, name in enumerate(names))
        fonts = sorted(set(font[rows]))
        index = dict((f, i) for i, f in enumerate(fonts))
        table = np.full((len(fonts), len(names)), np.nan)
        family = np.zeros(len(fonts), dtype=np.int64)
        for r in rows:
            table[index[font[r]], column[pairs[r]]] = y[r]
            family[index[font[r]]] = groups[r]
        kerned = np.abs(np.nan_to_num(table)) >= KERNED
        for i in range(len(fonts)):
            both = ~np.isnan(table[i]) & ~np.isnan(table)  # (every font against font i)
            compared = both & (kerned[i] | kerned)
            alike = compared & (np.abs(np.nan_to_num(table) - np.nan_to_num(table[i])) <= SAME_DESIGN_UNITS)
            counts = compared.sum(axis=1)
            for j in np.flatnonzero((counts >= SAME_DESIGN_MIN) & (alike.sum(axis=1) >= SAME_DESIGN_SHARE * np.maximum(counts, 1))):
                a, b = root(family[i]), root(family[j])
                if a != b:
                    parent[max(a, b)] = min(a, b)
                    merges += 1
    return merges, np.array([root(g) for g in groups])


def baselines(x):
    halo, contour = np.nan_to_num(x[:, 0]), np.nan_to_num(x[:, 1])
    tighten, loosen = ak.DEFAULT_FACTORS["halfkern"]
    halfkern = np.where(halo < 0, halo * tighten, halo * loosen)
    average = np.where(np.isnan(x[:, 0]), contour, np.where(np.isnan(x[:, 1]), halfkern, (halfkern + contour) / 2))
    return {"zero": np.zeros(len(x)), "halfkern": halfkern, "contour": contour, "average": average}


def scores(truth, predicted):
    error = np.abs(truth - predicted) * 1000
    kerned = np.abs(truth) * 1000 >= 10
    return {"mae": float(error.mean()), "mae kerned": float(error[kerned].mean()),
            "within 10": float((error <= 10).mean()), "within 20": float((error <= 20).mean())}


def usable_columns(x):
    """Columns with two values or more: scikit-learn cannot bin a feature of one value (or none)."""
    return [c for c in range(x.shape[1]) if len(np.unique(x[~np.isnan(x[:, c]), c])) >= 2]


def fit(x, y):
    """(classifier, regressor, columns): whether a pair is kerned, and how much where it is; columns is
    each stage's (the regressor's from the kerned pairs alone: in a small script's set, a column can
    have one value among them, the pair kinds of a unicameral script)."""
    columns = usable_columns(x)
    kerned = np.abs(y) >= KERNED
    classifier = HistGradientBoostingClassifier(**PARAMS).fit(x[:, columns], kerned)
    amount_columns = usable_columns(x[kerned])
    regressor = HistGradientBoostingRegressor(loss="squared_error", **PARAMS).fit(x[kerned][:, amount_columns], y[kerned])
    return classifier, regressor, (columns, amount_columns)


def predict(classifier, regressor, columns, x):
    chance = classifier.predict_proba(x[:, columns[0]])[:, 1]
    return np.where(chance >= CUT, regressor.predict(x[:, columns[1]]), 0.0)


def stage(model, columns):
    trees = []
    for predictors in model._predictors:
        nodes = predictors[0].nodes
        trees.append([[columns[int(n["feature_idx"])], float(n["num_threshold"]), int(n["missing_go_to_left"]),
                       int(n["left"]), int(n["right"]), int(n["is_leaf"]), round(float(n["value"]), 7)] for n in nodes])
    return {"baseline": float(np.ravel(model._baseline_prediction)[0]), "trees": trees}


def export(classifier, regressor, columns, info, path=None):
    data = {"format": 2, "features": FEATURES, "cut": CUT, "classifier": stage(classifier, columns[0]),
            "regressor": stage(regressor, columns[1]), "info": info}
    with open(path or MODEL_FILE, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, separators=(",", ":"))
    return path or MODEL_FILE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=os.path.join(ak.state_dir(), "kerning-train", "dataset.npz"))
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--exclude", default="", help="leave out the fonts whose file name contains this (a held-out test)")
    parser.add_argument("--model", default=MODEL_FILE, help="where --export writes the model")
    parser.add_argument("--scripts", default="latin", help="train on these scripts' pairs only (Latin's by default: the "
                                                              "others' did not help, see docs/KERNING.md)")
    parser.add_argument("--apply-to", default="latin,armenian,georgian",
                        help="the scripts Auto Kerning uses the model for: trained on Latin alone and held out on "
                             "Armenian and Georgian families, it beat the other methods there")
    parser.add_argument("--compare", default="", help="other training sets to score on the same folds, ';' between "
                                                      "them (latin,cyrillic;latin,greek): their own learned columns")
    parser.add_argument("--keep-families", action="store_true", help="fold by family name alone, without merging the "
                                                                       "families that kern alike (design_groups)")
    args = parser.parse_args()
    data = np.load(args.data)
    x, y, groups, fonts = data["x"].astype(np.float64), data["y"].astype(np.float64), data["group"], data["font"]
    names = [str(name) for name in data["scripts"]] if "scripts" in data else ["latin"]
    script = data["script"] if "script" in data else np.zeros(len(y), dtype=np.int32)
    trained_on = [name for name in (args.scripts.split(",") if args.scripts else names) if name in names]
    if args.exclude:
        left_out = [i for i, name in enumerate(data["fonts"]) if args.exclude.lower() in str(name).lower()]
        keep = ~np.isin(fonts, left_out)
        x, y, groups, fonts, script = x[keep], y[keep], groups[keep], fonts[keep], script[keep]
        print("left out %d fonts matching %r" % (len(left_out), args.exclude))
    font_count = len(np.unique(fonts))
    if "pair" in data and not args.keep_families:
        merges, groups = design_groups(y, script, fonts, groups, data["pair"][keep] if args.exclude else data["pair"])
        print("%d families merged with another that kerns a script alike (one design under two names)" % merges)

    print("%d pairs, %d fonts, %d families; %.0f%% kerned" % (len(y), font_count, len(set(groups)), 100 * (y != 0).mean()))
    use = np.isin(script, [names.index(name) for name in trained_on])
    print("training on %s: %d pairs" % (", ".join(trained_on), use.sum()))
    # Each training set scored: "learned" is --scripts', "learned <set>" each of --compare's.
    trainings = [("learned", use)]
    for part in [p for p in args.compare.split(";") if p]:
        chosen = [name for name in part.split(",") if name in names]
        trainings.append(("learned " + "+".join(chosen), np.isin(script, [names.index(name) for name in chosen])))
    # Every pair is predicted once, in the fold that holds its design out, and each script is scored
    # over all its pairs at once. (Averaging each fold's score instead let a script of few designs,
    # Armenian's four, swing with which fold each design fell in: a fold holding only a pixel font
    # weighed as much as one holding Google Sans.)
    folds = GroupKFold(n_splits=5)
    held_out = {}  # method: each pair's prediction, from the fold that held its design out
    started = time.time()
    for fold, (train, test) in enumerate(folds.split(x, y, groups)):
        predictions = baselines(x[test])
        for label, rows_used in trainings:
            fold_train = train[rows_used[train]]
            classifier, regressor, columns = fit(x[fold_train], y[fold_train])
            predictions[label] = predict(classifier, regressor, columns, x[test])
        for method, predicted in predictions.items():
            held_out.setdefault(method, np.zeros(len(y)))[test] = predicted
        print("fold %d done (%.0f s)" % (fold + 1, time.time() - started), flush=True)
    summaries = {}
    for number, name in enumerate(names):
        rows = script == number
        if rows.sum() < 50 or not (np.abs(y[rows]) * 1000 >= 10).any():
            continue
        summary = summaries[name] = {}
        print("\n%s (%d pairs, %d designs)\n%-24s %8s %12s %10s %10s" % (
            name, rows.sum(), len(set(groups[rows])), "method", "MAE", "MAE kerned", "within 10", "within 20"))
        for method, predicted in held_out.items():
            summary[method] = scores(y[rows], predicted[rows])
            print("%-24s %8.1f %12.1f %9.0f%% %9.0f%%" % (method, summary[method]["mae"], summary[method]["mae kerned"],
                                                          100 * summary[method]["within 10"], 100 * summary[method]["within 20"]))
    summary = summaries.get("latin") or summaries[trained_on[0]]
    others = [n for n in ("zero", "halfkern", "contour", "average") if n in summary]
    if args.export:
        if (summary["learned"]["mae"] >= min(summary[n]["mae"] for n in others)
                or summary["learned"]["mae kerned"] >= min(summary[n]["mae kerned"] for n in others)):
            print("not exported: the learned model does not beat the other methods on both measures")
            return
        applied = args.apply_to.split(",") if args.apply_to else trained_on
        # Another script takes the model only where it beats the default suggestion, the average of
        # halfkern and contour distance, on families it never saw, on all pairs and on kerned pairs.
        losing = [name for name in applied if name != "latin" and name in summaries
                  and (summaries[name]["learned"]["mae"] >= summaries[name]["average"]["mae"]
                       or summaries[name]["learned"]["mae kerned"] >= summaries[name]["average"]["mae kerned"])]
        if losing or any(name not in summaries for name in applied if name != "latin"):
            print("not exported: the learned model does not beat the average of halfkern and contour in %s"
                  % ", ".join(losing or [name for name in applied if name not in summaries]))
            return
        classifier, regressor, columns = fit(x[use], y[use])
        info = {"trained": time.strftime("%Y-%m-%d"), "pairs": int(use.sum()), "fonts": int(len(np.unique(fonts[use]))),
                "families": int(len(set(groups[use]))), "licenses": "SIL Open Font License and Apache License fonts only",
                "scripts": args.apply_to.split(",") if args.apply_to else trained_on, "trained on": trained_on,
                "cross-validation": dict((m, s) for m, s in summary.items() if m in others + ["learned"]),
                "cross-validation by script": dict((name, dict((m, s) for m, s in by.items() if m in others + ["learned"]))
                                                   for name, by in summaries.items())}
        export(classifier, regressor, columns, info, args.model)
        print("exported the model")


if __name__ == "__main__":
    main()
