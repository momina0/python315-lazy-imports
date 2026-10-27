"""Print the saved results: startup with and without `lazy import`, and which libraries
survive -X lazy_imports=all."""
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"
startup = json.loads((RESULTS / "startup.json").read_text())
compat = json.loads((RESULTS / "compat.json").read_text())

rows = {(r["scenario"], r["mode"]): r for r in startup["rows"]}
print(f"Python {startup['meta']['python']}: `lazy import` on 4 heavy imports vs normal imports (fastest of {startup['meta']['runs']} runs)\n")
print(f"{'':40}{'modules':>18}{'fastest run':>22}")
for scenario in dict.fromkeys(r["scenario"] for r in startup["rows"]):
    normal, lazy = rows[(scenario, "normal")], rows[(scenario, "keyword")]
    print(f"{scenario:40}{normal['modules']:>8} -> {lazy['modules']:<6}{normal['min_ms'] / 1000:>10.1f}s -> {lazy['min_ms'] / 1000:.1f}s")

broken = [r for r in compat["rows"] if r["lazy_all"] != "ok"]
print(f"\n-X lazy_imports=all (every import lazy): {len(compat['rows']) - len(broken)}/{len(compat['rows'])} libraries still work")
for r in broken:
    # Drop object reprs and long tails so each error fits on one line.
    error = r["lazy_all"].split(" for target ")[0].split(" and no __dict__")[0].replace("sqlalchemy.exc.", "")
    print(f"  {r['library']:<11} {error}")
