"""Build an offline gazetteer JSON from a GeoNames cities15000.txt file.

Usage:
    python scripts/build_gazetteer.py --input data/gazetteer/cities15000.txt \\
        --output data/gazetteer/cities.json

GeoNames cities15000: https://download.geonames.org/export/dump/cities15000.zip
License: CC BY 4.0 (http://www.geonames.org). Keep attribution.

Only cities with population >= 200000 (or capitals) are emitted, with ASCII
and native names. Output is consumed by domains/geo/gazetteer.py (manual merge).
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def build(inp: Path, outp: Path, min_pop: int) -> int:
    rows = []
    with inp.open(encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for r in reader:
            if len(r) < 19:
                continue
            name, asciiname, alternatenames = r[1], r[2], r[3]
            lat, lon = float(r[4]), float(r[5])
            country = r[8]
            population = int(r[14] or 0)
            feature_code = r[7]
            is_capital = feature_code == "PPLC"
            if not (is_capital or population >= min_pop):
                continue
            rows.append({
                "name": name,
                "ascii": asciiname,
                "aliases": [a for a in alternatenames.split(",") if a],
                "country": country,
                "lat": lat,
                "lon": lon,
                "population": population,
                "capital": is_capital,
            })
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(rows)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", default="data/gazetteer/cities.json")
    p.add_argument("--min-pop", type=int, default=200000)
    a = p.parse_args()
    n = build(Path(a.input), Path(a.output), a.min_pop)
    print("written", n, "places to", a.output)


if __name__ == "__main__":
    main()
