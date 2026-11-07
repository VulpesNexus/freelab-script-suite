"""Train the learned method on the training set (dataset.py), check it against the other methods on
families it never saw, and export it for Auto Kerning.

    python kerning/train/train.py [--data <dataset.npz>] [--export]

Cross-validation is grouped by family: no family is ever in both the training and the test part.
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
              random_state=0)
KERNED = 5 / 1000.0  # a pair kerned by at least this share of the em counts as kerned
CUT = 0.4  # the classifier's probability from which a pair is kerned (0.4 beat 0.5 and 0.6 on kerned pairs)
FEATURES = (["halfkern", "contour", "left kind", "right kind"] + ["spacing " + p for p in ak.SPACING_PAIRS]
            + ["left advance", "right advance"] + ["gap %d" % b for b in range(ak.PROFILE_BANDS)])


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
    """(classifier, regressor, columns): whether a pair is kerned, and how much where it is."""
    columns = usable_columns(x)
    kerned = np.abs(y) >= KERNED
    classifier = HistGradientBoostingClassifier(**PARAMS).fit(x[:, columns], kerned)
    regressor = HistGradientBoostingRegressor(loss="squared_error", **PARAMS).fit(x[kerned][:, columns], y[kerned])
    return classifier, regressor, columns


def predict(classifier, regressor, columns, x):
    chance = classifier.predict_proba(x[:, columns])[:, 1]
    return np.where(chance >= CUT, regressor.predict(x[:, columns]), 0.0)


def stage(model, columns):
    trees = []
    for predictors in model._predictors:
        nodes = predictors[0].nodes
        trees.append([[columns[int(n["feature_idx"])], float(n["num_threshold"]), int(n["missing_go_to_left"]),
                       int(n["left"]), int(n["right"]), int(n["is_leaf"]), round(float(n["value"]), 7)] for n in nodes])
    return {"baseline": float(np.ravel(model._baseline_prediction)[0]), "trees": trees}


def export(classifier, regressor, columns, info, path=None):
    data = {"format": 2, "features": FEATURES, "cut": CUT, "classifier": stage(classifier, columns),
            "regressor": stage(regressor, columns), "info": info}
    with open(path or MODEL_FILE, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, separators=(",", ":"))
    return path or MODEL_FILE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=os.path.join(ak.state_dir(), "kerning-train", "dataset.npz"))
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--exclude", default="", help="leave out the fonts whose file name contains this (a held-out test)")
    parser.add_argument("--model", default=MODEL_FILE, help="where --export writes the model")
    args = parser.parse_args()
    data = np.load(args.data)
    x, y, groups, fonts = data["x"].astype(np.float64), data["y"].astype(np.float64), data["group"], data["font"]
    if args.exclude:
        left_out = [i for i, name in enumerate(data["fonts"]) if args.exclude.lower() in str(name).lower()]
        keep = ~np.isin(fonts, left_out)
        x, y, groups, fonts = x[keep], y[keep], groups[keep], fonts[keep]
        print("left out %d fonts matching %r" % (len(left_out), args.exclude))
    font_count = len(np.unique(fonts))

    print("%d pairs, %d fonts, %d families; %.0f%% kerned" % (len(y), font_count, len(set(groups)), 100 * (y != 0).mean()))
    folds = GroupKFold(n_splits=5)
    results = {name: [] for name in ("zero", "halfkern", "contour", "average", "learned")}
    started = time.time()
    for fold, (train, test) in enumerate(folds.split(x, y, groups)):
        classifier, regressor, columns = fit(x[train], y[train])
        predictions = dict(baselines(x[test]), learned=predict(classifier, regressor, columns, x[test]))
        for name, predicted in predictions.items():
            results[name].append(scores(y[test], predicted))
        print("fold %d done (%.0f s)" % (fold + 1, time.time() - started), flush=True)
    summary = {}
    print("\n%-9s %8s %12s %10s %10s" % ("method", "MAE", "MAE kerned", "within 10", "within 20"))
    for name, runs in results.items():
        mean = dict((key, float(np.mean([r[key] for r in runs]))) for key in runs[0])
        summary[name] = mean
        print("%-9s %8.1f %12.1f %9.0f%% %9.0f%%" % (name, mean["mae"], mean["mae kerned"], 100 * mean["within 10"],
                                                     100 * mean["within 20"]))
    others = [n for n in summary if n != "learned"]
    if args.export:
        if (summary["learned"]["mae"] >= min(summary[n]["mae"] for n in others)
                or summary["learned"]["mae kerned"] >= min(summary[n]["mae kerned"] for n in others)):
            print("not exported: the learned model does not beat the other methods on both measures")
            return
        classifier, regressor, columns = fit(x, y)
        info = {"trained": time.strftime("%Y-%m-%d"), "pairs": int(len(y)), "fonts": int(font_count),
                "families": int(len(set(groups))), "licenses": "SIL Open Font License and Apache License fonts only",
                "cross-validation": summary}
        export(classifier, regressor, columns, info, args.model)
        print("exported the model")


if __name__ == "__main__":
    main()
