"""Collect engineering and computer science book metadata from Open Library API.

Complies with Open Library Search API documentation and rate limits:
- Custom User-Agent header
- Paced requests with exponential backoff on transient errors
- Targeted queries covering 42 engineering/CS subjects
- Target: ~1,000 unique records
"""

import json
import logging
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("collect_openlibrary")

BASE_DIR = Path(__file__).resolve().parents[1]
DATASETS_DIR = BASE_DIR / "datasets"
RAW_OUTPUT_FILE = DATASETS_DIR / "raw_openlibrary_books.json"

USER_AGENT = "BookNavLACS-Research/1.0 (Contact: research@booknav.local; Academic/Open-Source Engineering Search)"
API_ENDPOINT = "https://openlibrary.org/search.json"

TARGET_SUBJECTS = [
    # Computer Science
    "Data Structures and Algorithms",
    "Design and Analysis of Algorithms",
    "Programming Languages",
    "Object-Oriented Programming",
    "Database Management Systems",
    "Computer Networks",
    "Operating Systems",
    "Computer Architecture",
    "Software Engineering",
    "Theory of Computation",
    "Compiler Design",
    "Distributed Systems",
    "Web Development",
    "Information Technology",
    # Artificial Intelligence and Data Science
    "Artificial Intelligence",
    "Machine Learning",
    "Deep Learning",
    "Natural Language Processing",
    "Computer Vision",
    "Data Science",
    "Data Mining",
    "Neural Networks",
    "Statistics for Data Science",
    "Big Data Analytics",
    # Modern Technology
    "Cloud Computing",
    "Cybersecurity",
    "Ethical Hacking",
    "Cryptography",
    "Internet of Things",
    "Blockchain",
    "Mobile Application Development",
    "DevOps",
    "Information Retrieval",
    # Engineering and Mathematics
    "Mathematics for Computer Science",
    "Linear Algebra",
    "Probability and Statistics",
    "Electronics Engineering",
    "Electrical Engineering",
    "Mechanical Engineering",
    "Civil Engineering",
    "Communication Engineering",
    "Control Systems",
]


def fetch_subject_books(subject: str, limit: int = 30, max_retries: int = 3):
    """Query Open Library API for a subject with polite pacing and retries."""
    params = {
        "q": f'subject:"{subject}"' if " " in subject else f"subject:{subject}",
        "limit": str(limit),
        "fields": "key,title,author_name,subject,isbn,first_publish_year,language,edition_key",
    }
    url = f"{API_ENDPOINT}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("docs", [])
        except Exception as exc:
            wait_sec = 2.0 * attempt
            logger.warning(
                "Attempt %d/%d for '%s' failed: %s. Backing off for %.1fs...",
                attempt,
                max_retries,
                subject,
                exc,
                wait_sec,
            )
            time.sleep(wait_sec)

    # Fallback to general query if subject filter returned nothing or errored
    try:
        params_fallback = {
            "q": subject,
            "limit": str(limit),
            "fields": "key,title,author_name,subject,isbn,first_publish_year,language,edition_key",
        }
        url_fallback = f"{API_ENDPOINT}?{urllib.parse.urlencode(params_fallback)}"
        req_fallback = urllib.request.Request(url_fallback, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req_fallback, timeout=15) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("docs", [])
    except Exception as exc:
        logger.error("Fallback query for '%s' failed: %s", subject, exc)

    return []


def collect_dataset(target_count: int = 1000):
    """Iterate through target subjects and collect unique books."""
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    collected_records = []
    seen_keys = set()
    subject_stats = {}

    logger.info("Starting collection targeting ~%d unique engineering books across %d subjects...", target_count, len(TARGET_SUBJECTS))

    for idx, subject in enumerate(TARGET_SUBJECTS, 1):
        if len(seen_keys) >= target_count + 150:
            logger.info("Target threshold reached (%d unique records). Finishing collection early.", len(seen_keys))
            break

        logger.info("[%d/%d] Fetching books for subject: '%s'...", idx, len(TARGET_SUBJECTS), subject)
        docs = fetch_subject_books(subject, limit=35)
        new_in_subject = 0

        for doc in docs:
            work_key = doc.get("key", "").strip()
            title = doc.get("title", "").strip()
            if not title or not work_key:
                continue

            doc_entry = dict(doc)
            doc_entry["query_subject"] = subject
            collected_records.append(doc_entry)

            if work_key not in seen_keys:
                seen_keys.add(work_key)
                new_in_subject += 1

        subject_stats[subject] = new_in_subject
        logger.info("  -> Got %d docs (%d new unique). Total unique so far: %d", len(docs), new_in_subject, len(seen_keys))

        # Polite delay to strictly respect Open Library rate limits
        time.sleep(0.4)

    logger.info("Collection complete. Saving %d raw records (%d unique keys) to %s", len(collected_records), len(seen_keys), RAW_OUTPUT_FILE)
    with RAW_OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "source": "Open Library Search API",
                "total_records": len(collected_records),
                "unique_work_keys": len(seen_keys),
                "subject_stats": subject_stats,
                "records": collected_records,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.info("Raw dataset saved successfully.")
    return len(seen_keys)


if __name__ == "__main__":
    count = collect_dataset()
    print(f"Collected {count} unique books from Open Library.")
