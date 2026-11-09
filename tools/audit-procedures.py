import json
from pathlib import Path
from collections import defaultdict

PROJECT = Path.home() / "Workshop-Manual-Mobile"
PUBLICATION = "X001724"

folder = PROJECT / "viewer/data/procedures" / PUBLICATION
index = json.loads(
    (PROJECT / "build/content-index.json").read_text()
)

records = {
    r["id"]: r
    for r in index["records"]
    if r["publication_id"] == PUBLICATION
}

files = {p.stem for p in folder.glob("*.json")}
missing = defaultdict(list)
no_target = []
checked = 0
total_links = 0

def find_links(items):
    for item in items:
        if item.get("type") == "included_procedure":
            yield item
        yield from find_links(item.get("children", []))

for path in sorted(folder.glob("*.json")):
    checked += 1
    procedure = json.loads(path.read_text())

    for step in procedure.get("steps", []):
        for link in find_links(step.get("content", [])):
            total_links += 1
            target = link.get("target_id")
            title = link.get("target_title") or link.get("label") or ""

            if not target:
                no_target.append((path.stem, title))
            elif target not in files:
                record = records.get(target)
                status = record["status"] if record else "not in publication index"
                missing[target].append((path.stem, title, status))

print("\n--- RELATED PROCEDURE AUDIT ---")
print("Publication:", PUBLICATION)
print("Procedure files scanned:", checked)
print("Related-procedure links:", total_links)
print("Unique viewer procedure files:", len(files))
print("Links without target IDs:", len(no_target))
print("Unique missing target IDs:", len(missing))

if no_target:
    print("\n--- REFERENCES WITHOUT TARGET IDs ---")
    for source, title in no_target:
        print(source, "->", title)

if missing:
    print("\n--- TARGET FILES MISSING FROM VIEWER ---")
    for target, references in sorted(missing.items()):
        print("\n", target, "-", references[0][2])
        for source, title, status in references:
            print("  Referenced by:", source, "->", title)

print("\nAudit complete.")
