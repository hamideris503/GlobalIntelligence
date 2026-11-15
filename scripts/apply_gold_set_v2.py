"""Build Gold Set v2 (43 audit corrections) and re-evaluate Kev/Laya.

Reads:
  data/labeling/labeled-merged-stage50-stage53.jsonl   (382 rows, human labels)
  H:/GIRuntime/labeling/reviewed/all_382_label_audit.csv (43 "change needed")
  data/labeling/kev_full_results.jsonl, laya_full_results.jsonl

Writes:
  data/labeling/gold-set-v2.jsonl
  data/labeling/gold-set-manifest-v2.json
  docs/execution_reports/GOLD_SET_V2_EVALUATION.md
"""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(".")
MERGED = ROOT / "data/labeling/labeled-merged-stage50-stage53.jsonl"
AUDIT = Path("H:/GIRuntime/labeling/reviewed/all_382_label_audit.csv")
OUT = ROOT / "data/labeling/gold-set-v2.jsonl"
MANIFEST = ROOT / "data/labeling/gold-set-manifest-v2.json"
REPORT = ROOT / "docs/execution_reports/GOLD_SET_V2_EVALUATION.md"
V2_VERSION = "gold-set-v2-2026-11-16"
SEED = "wp08-heldout-v1"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


rows = load_jsonl(MERGED)
by_id = {r["id"]: r for r in rows}

with AUDIT.open(encoding="utf-8-sig", newline="") as fh:
    audit = list(csv.DictReader(fh))
changes = [a for a in audit if a["وضعیت"] == "تغییر لازم"]
assert len(changes) == 43, len(changes)
assert all(a["شناسه مقاله"] in by_id for a in changes), "unmatched audit ids"

corrections = []
for row in rows:
    row["source_dataset_version"] = row["dataset_version"]
    row["dataset_version"] = V2_VERSION
for a in changes:
    row = by_id[a["شناسه مقاله"]]
    old = bool(row["labels"]["relevant"])
    new = a["برچسب پیشنهادی اصلاح‌شده"].strip().lower() == "true"
    row["label_v1"] = old
    row["labels"]["relevant"] = new
    row["label_correction"] = {
        "source": "H:/GIRuntime/labeling/reviewed/all_382_label_audit.csv",
        "audit_status": a["وضعیت"],
        "audit_confidence": a["اطمینان"],
        "audit_reason": a["دلیل بازبینی"],
        "from": old,
        "to": new,
    }
    corrections.append((row["id"], old, new))

true_n = sum(1 for r in rows if r["labels"]["relevant"])
false_n = len(rows) - true_n
flips = sum(1 for _, old, new in corrections if old != new)

OUT.write_text(
    "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
)

# Deterministic hold-out split (documented rule, recomputed).
holdout_ids = {
    r["id"]
    for r in rows
    if int(hashlib.sha256(f"{SEED}:{r['id']}".encode()).hexdigest(), 16) % 100 < 20
}


def metrics(results: list[dict], labels: dict[str, bool]) -> dict:
    tp = tn = fp = fn = 0
    lat: list[float] = []
    abstain = 0
    for r in results:
        if r["id"] not in labels:
            continue
        truth = labels[r["id"]]
        if r.get("status") != "ok" or r.get("decision") is None:
            abstain += 1
            continue
        pred = bool(r["decision"])
        if r.get("latency_ms") is not None:
            lat.append(float(r["latency_ms"]))
        if pred and truth:
            tp += 1
        elif pred and not truth:
            fp += 1
        elif not pred and truth:
            fn += 1
        else:
            tn += 1
    n = tp + tn + fp + fn
    acc = (tp + tn) / n if n else 0.0
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    f1_t = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    spec = tn / (tn + fp) if tn + fp else 0.0
    f1_f = 2 * spec * (tn / (tn + fn)) / (spec + tn / (tn + fn)) if (spec + tn / (tn + fn)) else 0.0
    return {
        "n": n,
        "confusion": {"TP": tp, "TN": tn, "FP": fp, "FN": fn},
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "macro_f1": round((f1_t + f1_f) / 2, 4),
        "latency_ms_mean": round(statistics.mean(lat), 1) if lat else None,
        "latency_ms_p95": round(sorted(lat)[max(0, int(len(lat) * 0.95) - 1)], 1) if lat else None,
        "abstain": abstain,
    }


labels_all = {r["id"]: bool(r["labels"]["relevant"]) for r in rows}
labels_hold = {k: v for k, v in labels_all.items() if k in holdout_ids}
dev_ids = set(labels_all) - holdout_ids

results = {}
for name in ("kev", "laya"):
    path = ROOT / f"data/labeling/{name}_full_results.jsonl"
    res = [r for r in load_jsonl(path) if r["id"] in labels_all]
    results[name] = {
        "file": str(path),
        "sha256": sha256(path),
        "all": metrics(res, labels_all),
        "holdout": metrics(res, labels_hold),
    }

hold_true = sum(1 for v in labels_hold.values() if v)
manifest = {
    "manifest_version": "wp08-v2",
    "created": "2026-11-16",
    "dataset_version": V2_VERSION,
    "status": "OWNER_ACCEPTED_CORRECTIONS_APPLIED",
    "record_count": len(rows),
    "label_distribution": {"relevant_true": true_n, "relevant_false": false_n},
    "corrections": {
        "source": str(AUDIT),
        "source_sha256": sha256(AUDIT),
        "flagged": len(corrections),
        "net_label_flips": flips,
        "owner_decision": "applied per owner instruction (2026-11-16)",
    },
    "source": {
        "merged_file": str(MERGED),
        "merged_sha256": sha256(MERGED),
        "v1_manifest": "data/labeling/gold-set-manifest.json",
    },
    "held_out_split": {
        "seed": SEED,
        "frac": 0.2,
        "rule": "sha256(seed:id) % 100 < 20 (recomputed; v1 split file absent)",
        "dev_count": len(dev_ids),
        "holdout_count": len(holdout_ids),
        "holdout_label_distribution": {
            "relevant_true": hold_true,
            "relevant_false": len(holdout_ids) - hold_true,
        },
    },
    "evaluation": results,
    "promotion_decision": "Kev/Laya remain ADVISORY; Gold Set v2 is the accepted label baseline.",
}
MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

k, la = results["kev"], results["laya"]
dev_true = sum(1 for i in dev_ids if labels_all[i])
lines = [
    "# Gold Set v2 — اعمال ۴۳ اصلاح و ارزیابی مجدد Kev/Laya",
    "",
    "- **تاریخ:** ۱۶ نوامبر ۲۰۲۶ · **HEAD:** (working tree پس از commit `f428260`)",
    f"- **نسخه داده:** `{V2_VERSION}` · **SHA256 فایل:** `{sha256(OUT)}`",
    f"- **منبع اصلاحات:** `{AUDIT}` · SHA256 `{sha256(AUDIT)}`",
    "- **تصمیم مالک:** «انجام بده» → اصلاحات پیشنهادی audit اعمال شد (شامل ۱۶ ردیف با اطمینان متوسط).",
    "",
    "## 1. تغییرات برچسب",
    "",
    "| سنجه | v1 | v2 |",
    "|---|---:|---:|",
    f"| relevant=true | 295 | **{true_n}** |",
    f"| relevant=false | 87 | **{false_n}** |",
    f"| ردیف‌های اصلاح‌شده | — | **{len(corrections)}** |",
    f"| تغییر خالص برچسب | — | **{flips}** |",
    "",
    "هر ردیف اصلاح‌شده فیلدهای `label_v1` و `label_correction` (منبع، اطمینان، دلیل) را نگه می‌دارد؛",
    "هیچ برچسب قدیمی حذف نشده است.",
    "",
    "## 2. تقسیم dev/holdout (بازتولیدشده)",
    "",
    "| split | n | true | false |",
    "|---|---:|---:|---:|",
    f"| dev | {len(dev_ids)} | {dev_true} | {len(dev_ids) - dev_true} |",
    f"| holdout | {len(holdout_ids)} | {hold_true} | {len(holdout_ids) - hold_true} |",
    "",
    "> فایل split نسخهٔ v1 در دسترس نبود؛ قاعدهٔ مستند (`sha256(seed:id) % 100 < 20`) بازتولید شد.",
    "",
    "## 3. ارزیابی (برچسب‌های v2، تصمیم‌های اجرای موجود)",
    "",
    "| مدل | n | TP | TN | FP | FN | Acc | Prec | Rec | F1 | Macro-F1 |",
    "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
]
for name, label in (("kev", "Kev"), ("laya", "Laya")):
    m = results[name]["all"]
    c = m["confusion"]
    lines.append(
        f"| {label} | {m['n']} | {c['TP']} | {c['TN']} | {c['FP']} | {c['FN']} | "
        f"{m['accuracy']:.4f} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} | {m['macro_f1']:.4f} |"
    )
lines += [
    "",
    "Holdout:",
    "",
    "| مدل | n | TP | TN | FP | FN | Acc | F1 | Macro-F1 |",
    "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
]
for name, label in (("kev", "Kev"), ("laya", "Laya")):
    m = results[name]["holdout"]
    c = m["confusion"]
    lines.append(
        f"| {label} | {m['n']} | {c['TP']} | {c['TN']} | {c['FP']} | {c['FN']} | "
        f"{m['accuracy']:.4f} | {m['f1']:.4f} | {m['macro_f1']:.4f} |"
    )
lines += [
    "",
    "## 4. تصمیم promotion",
    "",
    "**Kev/Laya همچنان Advisory می‌مانند.** با وجود بهبود قابل انتظار در برچسب‌ها، recall هر دو مدل پایین است",
    "و Gold Set تک‌annotator است؛ فعال‌سازی به‌عنوان تصمیم‌گیرنده نیازمند اجرای مجدد مدل روی v2 و پذیرش مستقل است.",
    "",
    "## 5. محدودیت‌ها",
    "",
    "- تصمیم‌های مدل از اجرای ۲۰۲۶-۱۱-۰۴/۰۸ هستند (runtime در دسترس نبود)؛ فقط برچسب‌ها عوض شده‌اند.",
    "- ۱۶ ردیف از ۴۳ اصلاح با اطمینان «متوسط» بودند.",
    "- inter-annotator agreement قابل محاسبه نیست (تک annotator).",
    "- split بازتولیدشده است، نه همان فایل گمشدهٔ v1.",
]
REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("v2 rows", len(rows), "true", true_n, "false", false_n, "flips", flips)
print("kev", results["kev"]["all"])
print("laya", results["laya"]["all"])
print("holdout", results["kev"]["holdout"], results["laya"]["holdout"])
