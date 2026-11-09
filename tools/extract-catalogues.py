import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT = Path.home() / "Workshop-Manual-Mobile"
TOPICS = Path("/home/holto/ntfsFolder/workshopManualGren/topics")
INDEX = PROJECT / "build/content-index.json"
OUTPUT = PROJECT / "build/catalogues"


def tag(element):
    return element.tag.split("}")[-1]


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def text(element):
    if element is None:
        return ""
    return clean(" ".join(element.itertext()))


def children(element, name):
    return [e for e in element if tag(e) == name]


def first(element, name):
    return next((e for e in element.iter() if tag(e) == name), None)


def metadata(element):
    result = {}
    for block in children(element, "metadata"):
        for value in children(block, "value"):
            name = value.get("name")
            if name:
                result[name] = text(value)
    return result


def extract_catalogue(record):
    folder = TOPICS / record["source_folder"]
    xml_path = folder / record["files"]["interactivity"]

    root = ET.parse(xml_path).getroot()

    if tag(root) != "ipc":
        return None

    # Publication/topic-level metadata
    topic_metadata = metadata(first(root, "figure"))

    # Match each parts-list item to its part record.
    part_records = {}
    parts_element = first(root, "parts")

    if parts_element is not None:
        for part in children(parts_element, "part"):
            part_records[part.get("id")] = metadata(part)

    item_records = {}
    dplist = first(root, "dplist")

    if dplist is not None:
        for item in children(dplist, "item"):
            item_id = item.get("id")
            part_id = item.get("refPart")

            item_records[item_id] = {
                "item_id": item_id,
                "part_id": part_id,
                "item_metadata": metadata(item),
                "part_metadata": part_records.get(part_id, {})
            }

    # Read the actual parts table.
    tables = []
    ipc_table = first(root, "ipc-table")

    if ipc_table is not None:
        for table in children(ipc_table, "table"):
            headers = []
            thead = first(table, "thead")

            if thead is not None:
                header_row = first(thead, "row")
                if header_row is not None:
                    headers = [text(e) for e in children(header_row, "entry")]
                    if headers and not headers[0]:
                        headers = headers[1:]

            rows = []
            tbody = first(table, "tbody")

            if tbody is not None:
                for row in children(tbody, "row"):
                    values = [
                        text(e) for e in children(row, "entry")
                    ]
                    if len(values) > len(headers) and not values[0]:
                        values = values[1:]
                    if "Description" in headers:
                        description_index = headers.index("Description")
                        if description_index < len(values):
                            values[description_index] = values[description_index].lstrip("•").strip()

                    row_data = {
                        headers[i] if i < len(headers) else f"column_{i+1}": value
                        for i, value in enumerate(values)
                    }

                    item_id = row.get("refItem")

                    row_data["item_id"] = item_id
                    row_data["item_details"] = item_records.get(item_id, {})

                    rows.append(row_data)

            tables.append({
                "headers": headers,
                "rows": rows
            })

    # Preserve view names and their associated item references.
    views = []
    views_element = first(root, "views")

    if views_element is not None:
        for view in children(views_element, "view"):
            description = text(first(view, "description"))

            item_refs = [
                e.get("ref")
                for e in view.iter()
                if tag(e) == "refItem" and e.get("ref")
            ]

            views.append({
                "description": description,
                "item_refs": item_refs
            })

    # Record 2D illustration references only.
    # No WRL files are processed or copied.
    illustrations = []

    for media in root.iter():
        if tag(media) != "media":
            continue

        if media.get("type") == "image/svg":
            illustrations.append({
                "id": media.get("id"),
                "source": media.get("src"),
                "type": "svg"
            })

    return {
        "publication_id": record["publication_id"],
        "id": record["id"],
        "title": record["title"],
        "topic_metadata": topic_metadata,
        "parts": item_records,
        "tables": tables,
        "views": views,
        "illustrations": illustrations
    }


def main():
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)

    extracted = 0
    skipped = 0
    total_rows = 0

    for record in index["records"]:
        if record["status"] != "available":
            continue

        filename = record.get("files", {}).get("interactivity")

        if not filename:
            continue

        xml_path = TOPICS / record["source_folder"] / filename

        if not xml_path.is_file():
            continue

        try:
            catalogue = extract_catalogue(record)
        except ET.ParseError as error:
            print("XML ERROR:", record["id"], error)
            skipped += 1
            continue

        if catalogue is None:
            continue

        destination = (
            OUTPUT
            / record["publication_id"]
            / f"{record['id']}.json"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)

        destination.write_text(
            json.dumps(catalogue, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        row_count = sum(len(t["rows"]) for t in catalogue["tables"])
        total_rows += row_count
        extracted += 1

        if extracted <= 10:
            print(
                record["publication_id"],
                record["id"],
                record["title"],
                "| parts:", row_count
            )

    print("\nCATALOGUE EXTRACTION COMPLETE")
    print("Catalogues extracted:", extracted)
    print("Table rows extracted:", total_rows)
    print("XML errors:", skipped)
    print("Output:", OUTPUT)


if __name__ == "__main__":
    main()
