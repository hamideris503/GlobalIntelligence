"""Gold set tooling for F04 (offline, stdlib only).

Usage:
  python scripts/gold_set.py export --out data/gold_template.jsonl [--limit 200]
  python scripts/gold_set.py score --labels data/gold_labels.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def export_template(out: str, limit: int) -> int:
    from sqlalchemy import select

    from backend.database.models.article import Article
    from backend.database.session import get_session_factory

    session = get_session_factory()()
    rows = session.execute(select(Article).limit(limit)).scalars().all()
    session.close()
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        for a in rows:
            rec = {
                "article_id": str(a.id),
                "title": a.title,
                "summary": a.summary,
                "topics": a.topics,
                "predicted_relevant": None,
                "predicted_priority": a.importance,
                "label_relevant": None,   # human: true/false
                "label_priority": None,   # human: 0-4
                "label_notes": "",
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    print(f"exported {n} rows to {out}")
    return 0


def score(labels_path: str) -> int:
    rows = []
    with open(labels_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    # screening: relevant label vs predicted_relevant
    tp = fp = fn = tn = 0
    for r in rows:
        lab = r.get("label_relevant")
        pred = r.get("predicted_relevant")
        if lab is None or pred is None:
            continue
        if lab and pred:
            tp += 1
        elif (not lab) and pred:
            fp += 1
        elif lab and (not pred):
            fn += 1
        else:
            tn += 1
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    print(f"screening: tp={tp} fp={fp} fn={fn} tn={tn} precision={prec:.3f} recall={rec:.3f} f1={f1:.3f}")

    # priority: exact match accuracy
    correct = total = 0
    for r in rows:
        lab = r.get("label_priority")
        pred = r.get("predicted_priority")
        if lab is None or pred is None:
            continue
        total += 1
        if int(lab) == int(pred):
            correct += 1
    acc = correct / total if total else 0.0
    print(f"priority: exact_match={correct}/{total} accuracy={acc:.3f}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("export")
    p.add_argument("--out", required=True)
    p.add_argument("--limit", type=int, default=200)
    p.set_defaults(func=lambda a: export_template(a.out, a.limit))
    p = sub.add_parser("score")
    p.add_argument("--labels", required=True)
    p.set_defaults(func=lambda a: score(a.labels))
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
