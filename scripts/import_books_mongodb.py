"""Python entrypoint for Safe MongoDB Book Import.

Executes BookNav MongoDB import in dry-run mode by default, or live import with --apply.
Respects schema, avoids duplicates, and reports inserted, skipped, and failed records.
"""

import argparse
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
NODE_SCRIPT = BASE_DIR / "booknav_inspect" / "BookNav-master" / "server" / "scripts" / "importEngineeringBooks.js"
SERVER_DIR = BASE_DIR / "booknav_inspect" / "BookNav-master" / "server"
DEFAULT_CSV = BASE_DIR / "datasets" / "engineering_books.csv"


def main():
    parser = argparse.ArgumentParser(description="BookNav Safe MongoDB Book Import")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Path to engineering books CSV")
    parser.add_argument("--apply", action="store_true", help="Execute live insertion (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate import without modifying MongoDB")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of records to process")

    args = parser.parse_args()

    cmd = ["node", str(NODE_SCRIPT), "--csv", args.csv]
    if args.apply and not args.dry_run:
        cmd.append("--apply")
    else:
        cmd.append("--dry-run")

    if args.limit:
        cmd.extend(["--limit", str(args.limit)])

    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(SERVER_DIR))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
