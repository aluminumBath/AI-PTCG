"""Train the value net on the self-play dataset and export deployable weights.

Fits a logistic-regression value net (the model that drops into the agent as a
pure-numpy dot product) plus a small MLP for comparison. Splits by GAME so no
position from a validation game is ever trained on. Reports val accuracy, log-loss,
and AUC (0.5 = coin flip), prints the learned feature weights for a sanity read,
and writes weights.json for inference.

    python3 train_value.py [data.npz] [weights.json]
"""
import json
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "data.npz"
    out = sys.argv[2] if len(sys.argv) > 2 else "weights.json"
    d = np.load(data, allow_pickle=True)
    X, y, groups = d["X"], d["y"], d["groups"]
    names = [str(n) for n in d["names"]]
    print(f"data: X={X.shape} pos-rate={y.mean():.3f} games={len(set(groups.tolist()))}")

    tr, va = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=0)
                  .split(X, y, groups))
    sc = StandardScaler().fit(X[tr])
    Xtr, Xva = sc.transform(X[tr]), sc.transform(X[va])

    lr = LogisticRegression(max_iter=2000, C=1.0).fit(Xtr, y[tr])
    p_lr = lr.predict_proba(Xva)[:, 1]
    print(f"\nLOGISTIC value net (deployable):")
    print(f"  val acc {accuracy_score(y[va], p_lr>0.5):.3f}  "
          f"log-loss {log_loss(y[va], p_lr):.3f}  AUC {roc_auc_score(y[va], p_lr):.3f}")

    mlp = MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=400, alpha=1e-3,
                        random_state=0).fit(Xtr, y[tr])
    p_mlp = mlp.predict_proba(Xva)[:, 1]
    print(f"MLP value net (comparison, not exported):")
    print(f"  val acc {accuracy_score(y[va], p_mlp>0.5):.3f}  "
          f"log-loss {log_loss(y[va], p_mlp):.3f}  AUC {roc_auc_score(y[va], p_mlp):.3f}")
    print("  (coin-flip baseline: acc 0.500, log-loss 0.693, AUC 0.500)")

    coef = lr.coef_[0]
    order = np.argsort(-np.abs(coef))
    print("\nlearned linear weights (top signals, standardized):")
    for i in order[:12]:
        print(f"  {names[i]:22} {coef[i]:+.3f}")

    json.dump({
        "mean": sc.mean_.tolist(), "scale": sc.scale_.tolist(),
        "coef": coef.tolist(), "intercept": float(lr.intercept_[0]),
        "names": names,
    }, open(out, "w"))
    print(f"\nexported {out}  (linear value net -> pure-numpy inference)")


if __name__ == "__main__":
    main()
