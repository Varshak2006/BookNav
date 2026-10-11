"""Clean, deduplicate, validate, and export Open Library engineering book dataset.

Generates:
- datasets/engineering_books.csv (the primary dataset)
- datasets/dataset_report.txt (comprehensive data quality report)
"""

import csv
import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("clean_and_validate")

BASE_DIR = Path(__file__).resolve().parents[1]
DATASETS_DIR = BASE_DIR / "datasets"
RAW_INPUT_FILE = DATASETS_DIR / "raw_openlibrary_books.json"
CLEAN_OUTPUT_CSV = DATASETS_DIR / "engineering_books.csv"
DATASET_REPORT_FILE = DATASETS_DIR / "dataset_report.txt"

REQUIRED_COLUMNS = [
    "openlibrary_work_id",
    "openlibrary_edition_id",
    "title",
    "authors",
    "subjects",
    "isbn",
    "publication_year",
    "language",
    "source",
]


def normalize_space(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def clean_isbn(isbn_val) -> str:
    if not isbn_val:
        return ""
    if isinstance(isbn_val, list):
        for candidate in isbn_val:
            cleaned = re.sub(r"[^0-9X]", "", str(candidate).upper())
            if len(cleaned) in (10, 13):
                return cleaned
        return str(isbn_val[0]).strip()
    cleaned = re.sub(r"[^0-9X]", "", str(isbn_val).upper())
    return cleaned if len(cleaned) in (10, 13) else str(isbn_val).strip()


def clean_year(year_val) -> str:
    if not year_val:
        return ""
    if isinstance(year_val, int):
        return str(year_val) if 1000 <= year_val <= 2030 else ""
    # Extract 4-digit year from string
    match = re.search(r"\b(19\d\d|20[0-2]\d)\b", str(year_val))
    return match.group(1) if match else ""


def clean_authors(authors_val) -> str:
    if not authors_val:
        return "Unknown Author"
    if isinstance(authors_val, list):
        cleaned = [normalize_space(a) for a in authors_val if normalize_space(a)]
        return "; ".join(cleaned) if cleaned else "Unknown Author"
    return normalize_space(str(authors_val)) or "Unknown Author"


def clean_subjects(subjects_val, fallback_subject: str = "") -> str:
    items = []
    if isinstance(subjects_val, list):
        items = [normalize_space(s) for s in subjects_val if normalize_space(s)]
    elif subjects_val:
        items = [normalize_space(s) for s in str(subjects_val).split(";") if normalize_space(s)]
    if not items and fallback_subject:
        items = [fallback_subject]
    return "; ".join(items[:15])  # Cap at top 15 relevant subjects for neatness


def clean_language(lang_val) -> str:
    if not lang_val:
        return ""
    if isinstance(lang_val, list):
        for item in lang_val:
            clean = str(item).strip().lower()
            if len(clean) in (2, 3):
                return clean
        return str(lang_val[0]).strip().lower()
    return str(lang_val).strip().lower()


def clean_edition_id(ed_val) -> str:
    if not ed_val:
        return ""
    if isinstance(ed_val, list):
        return str(ed_val[0]).strip() if ed_val else ""
    return str(ed_val).strip()


def clean_and_validate():
    if not RAW_INPUT_FILE.exists():
        logger.error("Raw input file %s does not exist. Run collection first.", RAW_INPUT_FILE)
        return False

    with RAW_INPUT_FILE.open("r", encoding="utf-8") as f:
        raw_data = json.load(f)

    raw_records = raw_data.get("records", [])
    total_raw = len(raw_records)
    logger.info("Loaded %d raw records from %s", total_raw, RAW_INPUT_FILE)

    seen_work_ids = set()
    seen_title_author = set()
    valid_books = []
    discarded_entries = []

    missing_authors_count = 0
    missing_isbn_count = 0
    missing_year_count = 0
    duplicates_removed = 0
    subject_distribution = Counter()

    for idx, doc in enumerate(raw_records):
        title = normalize_space(doc.get("title", ""))
        work_key = normalize_space(doc.get("key", ""))
        query_subject = normalize_space(doc.get("query_subject", ""))

        if not title:
            discarded_entries.append({"reason": "Missing or empty title", "doc": doc})
            continue

        if not work_key:
            discarded_entries.append({"reason": "Missing work key", "doc": doc})
            continue

        work_id = work_key.replace("/works/", "")

        # Check duplicate work ID
        if work_id in seen_work_ids:
            duplicates_removed += 1
            discarded_entries.append({"reason": f"Duplicate work ID: {work_id}", "title": title})
            continue

        authors = clean_authors(doc.get("author_name"))
        if authors == "Unknown Author":
            missing_authors_count += 1

        # Check title + author duplicate
        title_author_key = (title.lower(), authors.lower())
        if title_author_key in seen_title_author:
            duplicates_removed += 1
            discarded_entries.append({"reason": f"Duplicate title+author: {title_author_key}", "title": title})
            continue

        isbn = clean_isbn(doc.get("isbn"))
        if not isbn:
            missing_isbn_count += 1

        year = clean_year(doc.get("first_publish_year"))
        if not year:
            missing_year_count += 1

        subjects = clean_subjects(doc.get("subject"), query_subject)
        edition_id = clean_edition_id(doc.get("edition_key"))
        language = clean_language(doc.get("language"))

        record = {
            "openlibrary_work_id": work_id,
            "openlibrary_edition_id": edition_id,
            "title": title,
            "authors": authors,
            "subjects": subjects,
            "isbn": isbn,
            "publication_year": year,
            "language": language,
            "source": "openlibrary",
        }

        seen_work_ids.add(work_id)
        seen_title_author.add(title_author_key)
        valid_books.append(record)

        if query_subject:
            subject_distribution[query_subject] += 1
        elif subjects:
            first_subj = subjects.split(";")[0].strip()
            subject_distribution[first_subj] += 1

    # Write cleaned CSV
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    with CLEAN_OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        for b in valid_books:
            writer.writerow(b)

    logger.info("Saved %d valid, deduplicated engineering books to %s", len(valid_books), CLEAN_OUTPUT_CSV)

    # Generate dataset_report.txt
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    report_lines = [
        "================================================================================",
        "BOOKNAV / LACS — ENGINEERING BOOK METADATA DATASET REPORT",
        "================================================================================",
        f"Generated At:                     {now_str}",
        f"Primary Output File:              {CLEAN_OUTPUT_CSV.name}",
        f"Data Source:                      Official Open Library Search API (openlibrary.org)",
        f"Total Raw Records Collected:      {total_raw}",
        f"Total Valid Unique Books:         {len(valid_books)}",
        f"Duplicate Records Removed:        {duplicates_removed}",
        f"Invalid / Unusable Records:       {len(discarded_entries) - duplicates_removed}",
        f"Records with Missing Authors:     {missing_authors_count} (preserved with 'Unknown Author')",
        f"Records with Missing ISBNs:       {missing_isbn_count}",
        f"Records with Missing Pub Years:   {missing_year_count}",
        "",
        "--------------------------------------------------------------------------------",
        "SUBJECT DISTRIBUTION (Targeted Query Subjects)",
        "--------------------------------------------------------------------------------",
    ]

    for subj, count in subject_distribution.most_common():
        report_lines.append(f"  - {subj:<42}: {count:>4} books")

    report_lines.extend([
        "",
        "--------------------------------------------------------------------------------",
        "COLLECTION & VALIDATION METHODOLOGY",
        "--------------------------------------------------------------------------------",
        "1. Targeted API Discovery: Queried Open Library across 42 engineering and CS",
        "   subjects in 4 core categories: Computer Science, AI & Data Science,",
        "   Modern Technology, and Engineering/Mathematics.",
        "2. Rate Limit Compliance: Paced requests with 400ms pause and exponential backoff.",
        "3. Verification: Only authentic records retrieved from Open Library were included.",
        "   Zero records or metadata were fabricated.",
        "4. Stable Identifiers: Deduplication prioritized Open Library work keys (/works/OL...)",
        "   supplemented by normalized (title, author) compound keys.",
        "5. Safety: Preserved rare engineering titles and foreign editions.",
        "",
        "--------------------------------------------------------------------------------",
        "KNOWN DATASET LIMITATIONS",
        "--------------------------------------------------------------------------------",
        "- Some historical or niche engineering publications lack ISBNs in Open Library.",
        "- Multiple contributing authors are collapsed into semicolon-separated strings.",
        "- Some records contain generalized subject headings assigned by library cataloguers.",
        "================================================================================",
    ])

    report_content = "\n".join(report_lines) + "\n"
    DATASET_REPORT_FILE.write_text(report_content, encoding="utf-8")
    logger.info("Saved dataset quality report to %s", DATASET_REPORT_FILE)

    return len(valid_books)


if __name__ == "__main__":
    count = clean_and_validate()
    print(f"Cleaned and validated {count} engineering books.")
