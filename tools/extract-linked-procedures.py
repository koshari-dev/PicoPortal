import argparse
import json
import subprocess
import shutil
import sys
from collections import deque
from pathlib import Path

PROJECT = Path.home() / "Workshop-Manual-Mobile"


def find_links(items):
    for item in items:
        if item.get("type") == "included_procedure":
            yield item
        yield from find_links(item.get("children", []))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    index = json.loads(
        (PROJECT / "build/content-index.json").read_text()
    )

    records = {
        r["id"]: r
        for r in index["records"]
        if r["publication_id"] == args.publication
    }

    output = PROJECT / "build/procedures" / args.publication
    output.mkdir(parents=True, exist_ok=True)

    viewer_output = (
        PROJECT / "viewer/data/procedures" / args.publication
    )
    viewer_output.mkdir(parents=True, exist_ok=True)

    queue = deque([args.start])
    visited = set()
    extracted = []
    skipped = []
    unavailable = []
    unresolved = []

    while queue and len(visited) < args.limit:
        topic_id = queue.popleft()

        if topic_id in visited:
            continue

        visited.add(topic_id)
        record = records.get(topic_id)

        if not record:
            unavailable.append((topic_id, "Not in publication index"))
            continue

        if record["status"] != "available":
            unavailable.append((topic_id, record["status"]))
            continue

        destination = output / f"{topic_id}.json"

        if not destination.exists():
            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "tools/extract-topic.py"),
                    "--publication", args.publication,
                    "--id", topic_id
                ],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print("EXTRACTION FAILED:", topic_id)
                print(result.stderr)
                continue

            extracted.append(topic_id)
            print("EXTRACTED:", record["title"])
        else:
            skipped.append(topic_id)

        shutil.copy2(destination, viewer_output / destination.name)

        procedure = json.loads(destination.read_text())

        for step in procedure.get("steps", []):
            for link in find_links(step.get("content", [])):
                target = link.get("target_id")

                if target:
                    if target not in visited:
                        queue.append(target)
                else:
                    unresolved.append((
                        topic_id,
                        link.get("target_title") or link.get("label")
                    ))

    print("\n--- CRAWL SUMMARY ---")
    print("Publication:", args.publication)
    print("Procedures visited:", len(visited))
    print("Newly extracted:", len(extracted))
    print("Already extracted:", len(skipped))
    print("Unavailable:", len(unavailable))
    print("References without target IDs:", len(unresolved))

    for topic_id, reason in unavailable:
        print("UNAVAILABLE:", topic_id, reason)

    for source, title in unresolved:
        print("UNRESOLVED:", source, "->", title)

    if queue:
        print("LIMIT REACHED. Remaining queued links:", len(queue))


if __name__ == "__main__":
    main()
