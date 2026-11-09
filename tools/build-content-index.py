import json
import re
from pathlib import Path
from collections import Counter

PROJECT = Path.home() / "Workshop-Manual-Mobile"
TOPICS = Path("/home/holto/ntfsFolder/workshopManualGren/topics")
HIERARCHY = PROJECT / "build/hierarchy.json"
OUTPUT = PROJECT / "build/content-index.json"

hierarchy = json.loads(HIERARCHY.read_text(encoding="utf-8"))

# Find source folders using publication ID + entry ID.
folders = {}

for folder in TOPICS.iterdir():
    if not folder.is_dir() or not folder.name.startswith("X"):
        continue

    entry_id = folder.name.split("_", 1)[0]
    match = re.search(r'_(X\d+)_', folder.name)

    if match:
        folders[(match.group(1), entry_id)] = folder

# Count each occurrence in the hierarchy.
occurrences = Counter()
entry_types = {}

def walk(node, publication_id):
    if node["type"] in ("task", "topic"):
        key = (publication_id, node["id"])
        occurrences[key] += 1
        entry_types[key] = node["type"]

    for child in node["children"]:
        walk(child, publication_id)

for publication in hierarchy["publications"]:
    walk(publication, publication["id"])

records = []
counts = Counter()

for (publication_id, entry_id), occurrence_count in sorted(occurrences.items()):
    folder = folders.get((publication_id, entry_id))
    short_id = entry_id.removeprefix("X")

    candidates = {
        "html": f"{entry_id}.topic.html",
        "includes": f"{entry_id}.includes.json",
        "interactivity": f"TOPIC_{short_id}.interactivity.xml",
        "model": f"TOPIC_{short_id}.wrl"
    }

    files = {}
    for kind, filename in candidates.items():
        files[kind] = (
            filename if folder and (folder / filename).is_file()
            else None
        )

    if not folder:
        status = "folder_unavailable"
    elif not files["html"]:
        status = "html_unavailable"
    else:
        status = "available"

    record = {
        "publication_id": publication_id,
        "id": entry_id,
        "type": entry_types[(publication_id, entry_id)],
        "occurrences": occurrence_count,
        "title": "",
        "status": status,
        "source_folder": folder.name if folder else None,
        "files": files
    }

    records.append(record)
    counts[status] += 1

    for kind in candidates:
        if files[kind]:
            counts[kind] += 1

data = {
    "version": 2,
    "source": "workshop-assets/topics",
    "records": records
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("\nCORRECTED CONTENT INDEX")
print("=======================")
print("Hierarchy occurrences:", sum(occurrences.values()))
print("Unique content records:", len(records))
print("Repeated occurrences:", sum(n - 1 for n in occurrences.values() if n > 1))
print("\nRECORD STATUS:")
for key in ("available", "folder_unavailable", "html_unavailable"):
    print(f"{key:22} {counts[key]}")

print("\nFILES FOUND:")
for key in ("html", "includes", "interactivity", "model"):
    print(f"{key:22} {counts[key]}")

print("\nOutput:", OUTPUT)
print("File size:", round(OUTPUT.stat().st_size / 1024 / 1024, 2), "MB")
