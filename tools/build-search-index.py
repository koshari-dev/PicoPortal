import json
from pathlib import Path

SOURCE = Path("build/catalogues")
OUTPUT = Path("viewer/data/search-index.json")

records = []

for path in sorted(SOURCE.glob("*/*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    metadata = data.get("topic_metadata", {})

    for table in data.get("tables", []):
        for row in table.get("rows", []):
            part_number = row.get("Part No.", "").strip()
            description = row.get("Description", "").strip()

            if not part_number and not description:
                continue

            records.append({
                "publication_id": data["publication_id"],
                "topic_id": data["id"],
                "topic_title": data.get("title", ""),
                "section": metadata.get("Section", ""),
                "operation": metadata.get("Operation", ""),
                "item": row.get("Item", ""),
                "part_number": part_number,
                "description": description,
                "quantity": row.get("Qty", ""),
                "remarks": row.get("Remarks", "")
            })

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(
    json.dumps(records, ensure_ascii=False, separators=(",", ":")),
    encoding="utf-8"
)

print("Search records:", len(records))
print("Output:", OUTPUT)
print("File size:", round(OUTPUT.stat().st_size / 1024 / 1024, 2), "MB")
