import csv
from pathlib import Path


BASE = Path(__file__).resolve().parent


def tokens(text):
    return [token.strip(".,:;!?\"'()").lower() for token in text.split() if token.strip(".,:;!?\"'()")]


def noisy_token(token):
    replacements = {
        "rabindranath": "ravindranath",
        "tagore": "tagor",
        "harry": "hary",
        "potter": "pottr",
        "machine": "machne",
        "learning": "larning",
        "python": "pyhton",
        "database": "databse",
        "system": "systm",
        "systems": "systms",
        "networks": "netwroks",
        "algorithm": "algoritm",
        "algorithms": "algoritms",
        "intelligence": "inteligence",
        "artificial": "artifical",
        "programming": "programing",
        "structures": "structres",
        "computer": "compter",
        "science": "scince",
        "fantasy": "fantacy",
        "poetry": "poety",
        "indian": "indan",
        "literature": "litrature",
        "coding": "codding",
        "clean": "clen",
        "concepts": "concpts",
    }
    if token in replacements:
        return replacements[token]
    if len(token) > 6:
        return token[:-2] + token[-1]
    if len(token) > 4:
        return token[0] + token[2] + token[1] + token[3:]
    return token


def load_base_queries():
    queries = []
    with (BASE / "data" / "library_books.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            title = row["title"].lower()
            author = row["author"].lower()
            category = row["category"].lower()
            keywords = row["keywords"].lower().split()
            queries.extend([
                title,
                author,
                category,
                f"{title} {author}",
                f"{category} books",
                " ".join(keywords[:3]),
                f"{keywords[0]} {keywords[-1]}" if keywords else title,
            ])
    extras = [
        "machine learning algorithms",
        "artificial intelligence algorithms",
        "deep learning neural networks",
        "python programming",
        "database system concepts",
        "operating system concepts",
        "computer networks tcp ip",
        "indian literature poetry",
        "fantasy magic wizard",
        "data structures algorithms python",
    ]
    queries.extend(extras)
    unique = []
    seen = set()
    for query in queries:
        query = " ".join(query.split())
        if query and query not in seen:
            seen.add(query)
            unique.append(query)
    return unique


def make_noisy(query, offset):
    parts = query.split()
    if not parts:
        return query
    positions = [i for i, part in enumerate(parts) if any(ch.isalpha() for ch in part)]
    if not positions:
        return query
    first = positions[offset % len(positions)]
    parts[first] = noisy_token(parts[first])
    if len(positions) > 2:
        second = positions[(offset + 2) % len(positions)]
        if second != first:
            parts[second] = noisy_token(parts[second])
    return " ".join(parts)


def main():
    base = load_base_queries()
    correct = []
    while len(correct) < 110:
        for query in base:
            correct.append(query)
            if len(correct) >= 110:
                break
    noisy = []
    i = 0
    while len(noisy) < 110:
        expected = correct[i % len(correct)]
        original = make_noisy(expected, i)
        if original != expected:
            noisy.append((original, expected))
        i += 1

    out = BASE / "data" / "evaluation_dataset.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["type", "original", "expected", "error_type"])
        for query in correct:
            writer.writerow(["correct", query, query, "none"])
        for original, expected in noisy:
            writer.writerow(["mistake", original, expected, "generated"])
    print(f"Wrote {len(correct)} correct and {len(noisy)} noisy queries to {out}")


if __name__ == "__main__":
    main()
