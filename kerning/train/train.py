"""Train the learned method on the training set (dataset.py), check it against the other methods on
families it never saw, and export it for Auto Kerning.

    python kerning/train/train.py [--data <dataset.npz>] [--export]

Cross-validation is grouped by family: no family is ever in both the training and the test part.
Errors are in units of a 1000-unit em. --export writes kerning/learned_model.json (gradient-boosted
trees, evaluated by Auto Kerning in plain Python) when the model beats every other method.

Python 3 with numpy and scikit-learn.
"""

import argparse
import json
import os
import sys
import time

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir))
os.environ["FREELAB_NO_AUTOSTART"] = "1"
import freelab_auto_kerning as ak  # noqa: E402

MODEL_FILE = os.path.join(HERE, os.pardir, "learned_model.json")
PARAMS = dict(loss="absolute_error", max_iter=250, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=40,
              l2_regularization=1.0, random_state=0)
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
    columns = usable_columns(x)
    return HistGradientBoostingRegressor(**PARAMS).fit(x[:, columns], y), columns


def export(model, columns, info):
    trees = []
    for predictors in model._predictors:
        nodes = predictors[0].nodes
        trees.append([[columns[int(n["feature_idx"])], round(float(n["num_threshold"]), 6), int(n["missing_go_to_left"]),
                       int(n["left"]), int(n["right"]), int(n["is_leaf"]), round(float(n["value"]), 7)] for n in nodes])
    data = {"format": 1, "features": FEATURES, "baseline": float(np.ravel(model._baseline_prediction)[0]),
            "trees": trees, "info": info}
    with open(MODEL_FILE, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, separators=(",", ":"))
    return MODEL_FILE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=os.path.join(ak.state_dir(), "kerning-train", "dataset.npz"))
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args()
    data = np.load(args.data)
    x, y, groups = data["x"].astype(np.float64), data["y"].astype(np.float64), data["group"]

    print("%d pairs, %d fonts, %d families; %.0f%% kerned" % (len(y), len(data["fonts"]), len(set(groups)), 100 * (y != 0).mean()))
    folds = GroupKFold(n_splits=5)
    results = {name: [] for name in ("zero", "halfkern", "contour", "average", "learned")}
    started = time.time()
    for fold, (train, test) in enumerate(folds.split(x, y, groups)):
        model, columns = fit(x[train], y[train])
        predictions = dict(baselines(x[test]), learned=model.predict(x[test][:, columns]))
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
    best_other = min(summary[n]["mae"] for n in summary if n != "learned")
    if args.export:
        if summary["learned"]["mae"] >= best_other:
            print("not exported: the learned model does not beat the other methods")
            return
        model, columns = fit(x, y)
        info = {"trained": time.strftime("%Y-%m-%d"), "pairs": int(len(y)), "fonts": int(len(data["fonts"])),
                "families": int(len(set(groups))), "licenses": "SIL Open Font License and Apache License fonts only",
                "cross-validation": summary}
        print("exported", export(model, columns, info))


if __name__ == "__main__":
    main()
