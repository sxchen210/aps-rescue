"""Unblind a judge's output for the third-party QA re-grade.

Takes the saved judge transcript (see third_party/PROTOCOL.md), pulls the
nine per-question JSON verdict blocks, maps Response 1/2 back to arms via
blinding_key.json, and prints the per-question results and the A/tie/B
tally.

Usage: python3 unblind.py third_party/judge_<model>_<date>.md
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    text = Path(sys.argv[1]).read_text()
    key = {m["package_q"]: m for m in
           json.loads((HERE / "third_party" / "blinding_key.json").read_text())["map"]}

    verdicts = {}
    for block in re.findall(r"\{[^{}]*\"question\"[^{}]*\}", text, re.S):
        try:
            d = json.loads(block)
        except json.JSONDecodeError:
            continue
        if "question" in d and "verdict" in d:
            verdicts[int(d["question"])] = d

    tally = {"A": 0, "B": 0, "tie": 0, "other": 0}
    print(f"{'q':>3} {'qid':>4} {'verdict':>18} {'arm':>4}  scores(1/2)")
    for n in sorted(key):
        d = verdicts.get(n)
        if d is None:
            print(f"{n:>3} {key[n]['qid']:>4} {'MISSING':>18}")
            tally["other"] += 1
            continue
        v = str(d["verdict"]).strip().lower()
        if v in ("1", "2"):
            arm = key[n][f"response_{v}"]
            tally[arm] += 1
        elif v == "tie":
            arm = "tie"
            tally["tie"] += 1
        else:
            arm = "?"
            tally["other"] += 1
        print(f"{n:>3} {key[n]['qid']:>4} {('Response ' + v) if v in ('1','2') else v:>18} "
              f"{arm:>4}  {d.get('score_1', '-')}/{d.get('score_2', '-')}")
    print(f"\nUNBLINDED TALLY — A: {tally['A']} | tie: {tally['tie']} | "
          f"B: {tally['B']}" + (f" | unresolved: {tally['other']}" if tally["other"] else ""))
    print("(self-graded result for comparison: B 3 | tie 6 | A 0)")


if __name__ == "__main__":
    main()
