import json
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter

PROJECT = Path.home() / "Workshop-Manual-Mobile"
SOURCE = PROJECT / "source/hierarchy"
OUTPUT = PROJECT / "build/hierarchy.json"

def tag_name(tag):
    return tag.split("}")[-1]

def convert(node):
    if tag_name(node.tag) != "file":
        return None

    title = ""
    children = []

    for child in node:
        name = tag_name(child.tag)

        if name == "title":
            title = "".join(child.itertext()).strip()

        elif name == "file":
            converted = convert(child)
            if converted:
                children.append(converted)

    result = {
        "id": node.get("id", ""),
        "type": node.get("type", "unknown"),
        "title": title,
        "uri": node.get("uri", ""),
        "children": children
    }

    return result

publications = []
counts = Counter()
missing = []

for path in sorted(SOURCE.glob("*.xml")):
    root = ET.parse(path).getroot()

    if tag_name(root.tag) != "file":
        print("WARNING: Unexpected root:", path.name)
        continue

    publication = convert(root)
    publication["source"] = path.name
    publications.append(publication)

    def count_nodes(node):
        counts[node["type"]] += 1

        if not node["id"] or not node["title"]:
            missing.append((path.name, node["id"], node["title"]))

        for child in node["children"]:
            count_nodes(child)

    count_nodes(publication)

data = {
    "version": 1,
    "publications": publications
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("\nHIERARCHY BUILD COMPLETE")
print("========================")
print("Publications:", len(publications))
print("Entries:", sum(counts.values()))

for kind, count in sorted(counts.items()):
    print(f"{kind:12} {count}")

print("Missing IDs or titles:", len(missing))
print("Output:", OUTPUT)
print("File size:", round(OUTPUT.stat().st_size / 1024 / 1024, 2), "MB")

if missing:
    print("\nWARNING - entries requiring inspection:")
    for item in missing[:20]:
        print(item)
