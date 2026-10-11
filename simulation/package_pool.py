"""Package the firing pool: rendered text + spec answer keys + deterministic
Message-IDs, in strict chronological order, in the shape
app/pipeline._pool_next expects.

Writes out/extension/pool.jsonl.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXT = HERE / "out" / "extension"

specs = {json.loads(l)["id"]: json.loads(l)
         for l in (EXT / "specs_pool.jsonl").read_text().splitlines() if l.strip()}
rows = [json.loads(l) for l in (EXT / "corpus_pool.jsonl").read_text().splitlines()
        if l.strip()]
rows.sort(key=lambda r: r["ts"])

out = []
for r in rows:
    sp = specs[r["id"]]
    t = re.sub(r"[^A-Za-z0-9]+", "-", r["thread"])
    out.append({
        "id": r["id"], "ts": r["ts"], "thread": r["thread"],
        "from": r["from"], "subject": r["subject"], "body": r["body"],
        "message_id": f"<{r['id']}.{t}@apsdemo.sim>",
        "labels": r["labels"],
        "type": r["facts"].get("type") or r["facts"].get("template"),
        "expected_ops": sp.get("expected_ops"),
    })
(EXT / "pool.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in out))
import collections
print(f"pool packaged: {len(out)} fireable emails, "
      f"{sum(1 for x in out if x['expected_ops'])} with answer keys")
print("by type:", collections.Counter(x["type"] for x in out).most_common(8))
print("first three:", [(x["ts"][:16], x["subject"][:45]) for x in out[:3]])
