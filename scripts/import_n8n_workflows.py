"""Import n8n workflows from JSON files (Phase 4 helper).

اجرا:
    python scripts/import_n8n_workflows.py

فایل‌های workflow را از `integrations/n8n/workflows/` می‌خواند و با CLI داخل
کانتینر n8n آن‌ها را import و publish می‌کند.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF_DIR = ROOT / "integrations" / "n8n" / "workflows"


def _run(args: list[str]) -> int:
    print("$", " ".join(args))
    return subprocess.call(args, cwd=str(ROOT))


def main() -> int:
    if not WF_DIR.exists():
        print(f"no workflows dir: {WF_DIR}")
        return 1

    files = sorted(WF_DIR.glob("*.json"))
    if not files:
        print("no workflow json files found")
        return 0

    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        wf_id = data.get("id")
        if not wf_id:
            print(f"SKIP {f.name}: missing 'id' (n8n 2.x requires it)")
            continue

        # copy into container then import
        _run(["docker", "compose", "cp", str(f), "n8n:/tmp/wf.json"])
        _run(["docker", "compose", "exec", "-T", "n8n", "n8n", "import:workflow", "--input=/tmp/wf.json"])
        _run(["docker", "compose", "exec", "-T", "n8n", "n8n", "publish:workflow", f"--id={wf_id}"])
        print(f"imported+publishing: {wf_id}")

    print("restarting n8n to apply published workflows...")
    _run(["docker", "compose", "restart", "n8n"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
