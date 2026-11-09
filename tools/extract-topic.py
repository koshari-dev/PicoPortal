import argparse
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag

PROJECT = Path.home() / "Workshop-Manual-Mobile"
TOPICS = Path("/home/holto/ntfsFolder/workshopManualGren/topics")

SYMBOLS = {
    "Symbol_warning.svg": "⚠",
    "Symbol_caution.svg": "⚠",
    "Symbol_information.svg": "ℹ",
    "Symbol_info.svg": "ℹ",
}

def clean_text(value):
    return re.sub(r"\s+", " ", value).strip()

def count_type(items, wanted):
    total = 0
    for item in items:
        if item.get("type") == wanted:
            total += 1
        total += count_type(item.get("children", []), wanted)
    return total


def extract_node(node, includes, title_to_id):
    if isinstance(node, NavigableString):
        value = clean_text(str(node))
        return {"type": "text", "text": value} if value else None

    if not isinstance(node, Tag):
        return None

    classes = node.get("class", [])

    # Warning and caution blocks
    if "warning" in classes:
        message = node.select_one(".warningMessage")
        heading = message.select_one(".heading") if message else None

        severity = (
            clean_text(heading.get_text(" ", strip=True))
            .rstrip(":").lower()
            if heading else "warning"
        )

        body = ""
        if message:
            parts = [
                clean_text(str(item))
                for item in message.find_all(string=True)
                if not heading or item.parent != heading
            ]
            body = clean_text(" ".join(parts))

        symbol = "ℹ" if severity in ("information", "note") else "⚠"

        return {
            "type": "warning",
            "severity": severity,
            "symbol": symbol,
            "heading": severity.upper(),
            "text": body
        }

    # Included procedure links
    if node.name == "a" and "included" in classes:
        parent_step = node.find_parent(
            "div", class_="step"
        )
        data_id = parent_step.get("data-id") if parent_step else None
        reference = includes.get(data_id, {})

        target_title = (
            reference.get("targetTitle")
            or clean_text(node.get_text(" ", strip=True))
        )
        target_id = reference.get("targetId")

        if not target_id:
            lookup_title = re.sub(
                r"^Refer To:\s*", "", target_title,
                flags=re.IGNORECASE
            ).strip()
            target_id = title_to_id.get(lookup_title.casefold())

        return {
            "type": "included_procedure",
            "target_id": target_id,
            "target_title": target_title,
            "label": reference.get("label")
                or clean_text(node.get_text(" ", strip=True))
        }

    # Images: replace standard symbols, retain other references
    if node.name == "img":
        filename = Path(node.get("src", "")).name

        if filename in SYMBOLS:
            return {
                "type": "symbol",
                "symbol": SYMBOLS[filename],
                "alt": node.get("alt", "")
            }

        return {
            "type": "image",
            "source": node.get("src", ""),
            "alt": node.get("alt", "")
        }

    children = [
        item for child in node.children
        if (item := extract_node(child, includes, title_to_id)) is not None
    ]

    if not children:
        return None

    result = {
        "type": "element",
        "tag": node.name,
        "children": children
    }

    if classes:
        result["classes"] = classes

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--publication", required=True)
    args = parser.parse_args()

    index = json.loads(
        (PROJECT / "build/content-index.json").read_text()
    )

    publication_records = [
        r for r in index["records"]
        if r["publication_id"] == args.publication
        and r["status"] == "available"
    ]

    title_matches = {}
    ambiguous_titles = set()

    for item in publication_records:
        key = item["title"].strip().casefold()
        if key in title_matches:
            ambiguous_titles.add(key)
        else:
            title_matches[key] = item["id"]

    for key in ambiguous_titles:
        title_matches.pop(key, None)

    title_to_id = title_matches

    record = next(
        (
            r for r in index["records"]
            if r["id"] == args.id
            and r["publication_id"] == args.publication
        ),
        None
    )

    if not record:
        raise SystemExit("Content record not found.")

    if record["status"] != "available":
        raise SystemExit(f"Content status: {record['status']}")

    folder = TOPICS / record["source_folder"]

    html_path = folder / record["files"]["html"]
    soup = BeautifulSoup(
        html_path.read_text(encoding="utf-8", errors="replace"),
        "html.parser"
    )

    includes = {}
    includes_file = record["files"].get("includes")

    if includes_file and (folder / includes_file).exists():
        raw = json.loads(
            (folder / includes_file).read_text(encoding="utf-8")
        )
        includes = {
            item["dataId"]: item for item in raw
        }

    procedure = {
        "publication_id": record["publication_id"],
        "id": record["id"],
        "type": record["type"],
        "title": record["title"],
        "steps": []
    }

    steps = soup.find_all(
        lambda tag: tag.name == "div"
        and "step" in tag.get("class", [])
    )

    for step in steps:
        number = step.select_one(".step-number")
        content = step.select_one(".step-content")

        if not content:
            continue

        blocks = [
            item for child in content.children
            if (item := extract_node(child, includes, title_to_id)) is not None
        ]

        procedure["steps"].append({
            "step_id": step.get("data-id", ""),
            "number": clean_text(number.get_text(" ", strip=True))
                if number else "",
            "content": blocks
        })

    output = (
        PROJECT / "build" / "procedures"
        / record["publication_id"]
    )
    output.mkdir(parents=True, exist_ok=True)

    destination = output / f"{record['id']}.json"
    destination.write_text(
        json.dumps(procedure, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("EXTRACTED:", record["title"])
    print("STEPS:", len(procedure["steps"]))
    print("INCLUDED LINKS:", sum(
        count_type(step["content"], "included_procedure")
        for step in procedure["steps"]
    ))
    print("OUTPUT:", destination)
    print("SIZE:", destination.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
