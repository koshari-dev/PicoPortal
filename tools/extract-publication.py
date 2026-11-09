import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path.home() / "Workshop-Manual-Mobile"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    index = json.loads(
        (PROJECT / "build/content-index.json").read_text()
    )

    records = [
        r for r in index["records"]
        if r["publication_id"] == args.publication
        and r["status"] == "available"
    ]

    batch = records[args.start:args.start + args.limit]

    build_dir = PROJECT / "build/procedures" / args.publication
    viewer_dir = PROJECT / "viewer/data/procedures" / args.publication
    build_dir.mkdir(parents=True, exist_ok=True)
    viewer_dir.mkdir(parents=True, exist_ok=True)

    extracted = 0
    copied = 0
    skipped = 0
    failed = []

    print(f"Publication: {args.publication}")
    print(f"Available pages: {len(records)}")
    print(f"Batch: {args.start} to {args.start + len(batch) - 1}")
    print()

    for number, record in enumerate(batch, args.start + 1):
        source = build_dir / f'{record["id"]}.json'
        destination = viewer_dir / source.name

        if source.exists():
            shutil.copy2(source, destination)
            copied += 1
            skipped += 1
            continue

        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT / "tools/extract-topic.py"),
                "--publication", args.publication,
                "--id", record["id"]
            ],
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and source.exists():
            shutil.copy2(source, destination)
            extracted += 1
            print(f"{number}/{len(records)} EXTRACTED: {record['title']}")
        else:
            message = result.stderr.strip() or result.stdout.strip()
            failed.append((record["id"], record["title"], message))
            print(f"{number}/{len(records)} FAILED: {record['title']}")

    print("\\n--- BATCH SUMMARY ---")
    print("Newly extracted:", extracted)
    print("Already extracted and copied:", skipped)
    print("Failed:", len(failed))

    if failed:
        failure_file = build_dir / "batch-failures.txt"
        with failure_file.open("a", encoding="utf-8") as f:
            for item_id, title, message in failed:
                f.write(f"{item_id} | {title} | {message}\\n")
        print("Failure details:", failure_file)

    print("Viewer procedure files:", len(list(viewer_dir.glob("*.json"))))

if __name__ == "__main__":
    main()
