"""Start each scenario many times as a fresh process, with lazy imports off and on.

usage: python bench/startup.py [RUNS]   (run with the Python 3.15 interpreter)
"""
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 20
WARMUP = 2
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1", "COLUMNS": "100", "PYTHONPATH": str(ROOT / "apps")}

# (name, script args). Each runs in three modes:
#   normal   - lazy imports off (Python's default; `lazy` keywords still apply)
#   all      - -X lazy_imports=all: every module-level import becomes lazy, no code changes
#   keyword  - cli_lazy.py / api_lazy.py: `lazy import` on the heavy, rarely used imports only
SCENARIOS = [
    ("cli --help", ["apps/cli.py", "--help"]),
    ("cli fetch (needs requests)", ["apps/cli.py", "fetch", "https://example.com"]),
    ("cli report (needs pandas)", ["apps/cli.py", "report", "--rows", "3"]),
    ("api boot", ["-c", "import api; api.app"]),  # touch api.app, or a lazy `import api` never runs
    ("api boot + GET /health", ["apps/first_request.py", "GET", "/health"]),
    ("api boot + GET /report (needs pandas)", ["apps/first_request.py", "GET", "/report"]),
]


def command(mode, args):
    if mode == "keyword":
        if args[0] == "apps/cli.py":
            args = ["apps/cli_lazy.py", *args[1:]]
        elif args[0] == "apps/first_request.py":
            args = [*args, "api_lazy"]
        else:
            args = [a.replace("api", "api_lazy") for a in args]
        mode = "normal"
    return [sys.executable, "-X", f"lazy_imports={mode}", *args]


class Failed(Exception):
    pass


def time_once(cmd):
    start = time.perf_counter()
    proc = subprocess.run(cmd, cwd=ROOT, env=ENV, capture_output=True)
    elapsed = (time.perf_counter() - start) * 1000
    if proc.returncode != 0:
        lines = [l for l in proc.stderr.decode(errors="replace").splitlines() if l.strip()]
        errors = [l for l in lines if l.split(":")[0].endswith("Error")]
        raise Failed((errors or lines)[-1].strip())
    return elapsed


def modules_imported(cmd):
    """Count modules that actually executed, from -X importtime output."""
    proc = subprocess.run([cmd[0], "-X", "importtime", *cmd[1:]], cwd=ROOT, env=ENV, capture_output=True)
    return sum(1 for line in proc.stderr.decode(errors="replace").splitlines() if line.startswith("import time:") and "|" in line and "cumulative" not in line)


rows = []
for name, args in SCENARIOS:
    for mode in ("normal", "all", "keyword"):
        cmd = command(mode, args)
        if cmd is None:
            continue
        try:
            for _ in range(WARMUP):
                time_once(cmd)
            times = sorted(time_once(cmd) for _ in range(RUNS))
        except Failed as e:
            row = {"scenario": name, "mode": mode, "failed": str(e)}
            rows.append(row)
            print(json.dumps(row), flush=True)
            continue
        row = {
            "scenario": name,
            "mode": mode,
            "median_ms": round(statistics.median(times)),
            "p90_ms": round(times[int(0.9 * (len(times) - 1))]),
            "min_ms": round(times[0]),
            "modules": modules_imported(cmd),
            "runs_ms": [round(t, 1) for t in times],
        }
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k != "runs_ms"}), flush=True)

meta = {
    "python": sys.version.split()[0],
    "platform": platform.platform(),
    "cpu": platform.processor(),
    "runs": RUNS,
    "warmup": WARMUP,
    "packages": {p: __import__("importlib.metadata").metadata.version(p) for p in ["fastapi", "pydantic", "sqlalchemy", "pandas", "numpy", "boto3", "openai", "requests", "typer", "rich", "httpx"]},
}
(ROOT / "results").mkdir(exist_ok=True)
(ROOT / "results" / "startup.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=2))
