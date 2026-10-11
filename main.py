from pathlib import Path
import json
from lacs import LACSAlgorithm

BASE = Path(__file__).resolve().parent

engine = LACSAlgorithm(
    BASE / "data" / "library_books.csv",
    BASE / "data" / "correction_history.csv"
)

def main():
    print("Library-Aware Contextual Spell Correction Algorithm (LACS)")
    print("Type a library query, or type 'exit'.\n")

    while True:
        try:
            query = input("Search query: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if query.lower() == "exit":
            break
        result = engine.correct(query)
        print(json.dumps(result, indent=2))
        print()


if __name__ == "__main__":
    main()
