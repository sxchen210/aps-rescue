"""Structural sanity gate on discovery output (PLAN.md Phase 2).

Checks STRUCTURE only — never content-vs-universe. Degenerate output means
re-running discovery with a clarified mission, never hand-editing.

Usage: python3 sanity_gate.py   (exit 0 = pass)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
fails, warns = [], []

p = HERE / "schema.json"
if not p.exists():
    print("FAIL: schema.json missing")
    sys.exit(1)
try:
    schema = json.loads(p.read_text())
except json.JSONDecodeError as e:
    print(f"FAIL: schema.json does not parse: {e}")
    sys.exit(1)

tables = schema.get("tables", {})
if isinstance(tables, list):
    tables = {t.get("name", f"t{i}"): t for i, t in enumerate(tables)}
if not (3 <= len(tables) <= 12):
    fails.append(f"table count {len(tables)} outside sane range 3-12")
for name, t in tables.items():
    if not t.get("canonical_keys"):
        fails.append(f"table '{name}' has no canonical_keys")
    cols = t.get("columns", {})
    if len(cols) < 2:
        fails.append(f"table '{name}' has {len(cols)} columns")
    if not any(("date" in c.lower() or (isinstance(v, dict) and v.get("type") == "date"))
               for c, v in (cols.items() if isinstance(cols, dict) else [])):
        warns.append(f"table '{name}' has no dated field")
if not schema.get("catchall_tags"):
    fails.append("no catchall_tags taxonomy")

instr = (HERE / "instructions.md")
if not instr.exists():
    fails.append("instructions.md missing")
else:
    txt = instr.read_text()
    for needle, why in [('"ops"', "envelope ops key"), ('"match"', "match key"),
                        ('"set"', "set key"), ("catchall", "catchall handling")]:
        if needle not in txt:
            fails.append(f"instructions.md never mentions {why} ({needle})")
    if txt.count("```") < 6:
        warns.append("instructions.md has few fenced examples (<3 blocks)")
    if len(txt) < 2000:
        warns.append(f"instructions.md is short ({len(txt)} chars)")

if not (HERE / "DISCOVERY_NOTES.md").exists():
    fails.append("DISCOVERY_NOTES.md missing")

print(f"tables: {len(tables)} -> {list(tables)}")
for name, t in tables.items():
    cols = t.get("columns", {})
    print(f"  {name}: keys={t.get('canonical_keys')} | {len(cols)} columns")
print(f"catchall_tags: {schema.get('catchall_tags')}")
for w in warns:
    print("WARN:", w)
for f in fails:
    print("FAIL:", f)
print("GATE:", "PASS" if not fails else "FAIL")
sys.exit(0 if not fails else 1)
