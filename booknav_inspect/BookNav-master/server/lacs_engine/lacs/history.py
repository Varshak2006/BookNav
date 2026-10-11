import csv
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


class CorrectionHistoryRepository:
    """Abstract interface for storing and retrieving accepted query corrections."""

    def record_correction(self, wrong: str, correct: str) -> None:
        raise NotImplementedError

    def get_frequency(self, wrong: str, correct: str) -> int:
        raise NotImplementedError

    def get_candidate_frequency(self, wrong: str) -> dict[str, int]:
        raise NotImplementedError

    def get_last_seen(self, wrong: str, correct: str) -> str:
        return ""

    def clear(self) -> None:
        raise NotImplementedError

    def export(self) -> list[dict]:
        raise NotImplementedError

    def import_rows(self, rows: Sequence[Mapping[str, str | int]]) -> None:
        raise NotImplementedError


class CSVCorrectionHistoryRepository(CorrectionHistoryRepository):
    """File-backed CSV implementation for development and testing."""

    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)
        self.counts: Counter[tuple[str, str]] = Counter()
        self.first_seen: dict[tuple[str, str], str] = {}
        self.last_seen: dict[tuple[str, str], str] = {}
        self._load()

    def _load(self) -> None:
        if not self.csv_path.exists():
            return
        with self.csv_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                wrong = row.get("wrong_word", "").lower().strip()
                correct = row.get("correct_word", "").lower().strip()
                if not wrong or not correct:
                    continue
                key = (wrong, correct)
                self.counts[key] = int(row.get("frequency", "0") or 0)
                self.first_seen[key] = row.get("first_seen") or ""
                self.last_seen[key] = row.get("last_seen") or ""

    def get_frequency(self, wrong: str, correct: str) -> int:
        return self.counts.get((wrong.lower().strip(), correct.lower().strip()), 0)

    def get_candidate_frequency(self, wrong: str) -> dict[str, int]:
        w = wrong.lower().strip()
        return {
            correct: freq
            for (stored_wrong, correct), freq in self.counts.items()
            if stored_wrong == w
        }

    def get_last_seen(self, wrong: str, correct: str) -> str:
        return self.last_seen.get((wrong.lower().strip(), correct.lower().strip()), "")

    def record_correction(self, wrong: str, correct: str) -> None:
        w = wrong.lower().strip()
        c = correct.lower().strip()
        if not w or not c:
            return
        key = (w, c)
        now = datetime.now(timezone.utc).isoformat()
        self.counts[key] += 1
        self.first_seen.setdefault(key, now)
        self.last_seen[key] = now
        self._save()

    def clear(self) -> None:
        self.counts.clear()
        self.first_seen.clear()
        self.last_seen.clear()
        self._save()

    def export(self) -> list[dict]:
        rows = []
        for (wrong, correct), freq in sorted(self.counts.items()):
            rows.append({
                "wrong_word": wrong,
                "correct_word": correct,
                "frequency": freq,
                "first_seen": self.first_seen.get((wrong, correct), ""),
                "last_seen": self.last_seen.get((wrong, correct), ""),
            })
        return rows

    def import_rows(self, rows: Sequence[Mapping[str, str | int]]) -> None:
        self.counts.clear()
        self.first_seen.clear()
        self.last_seen.clear()
        for row in rows:
            w = str(row["wrong_word"]).lower().strip()
            c = str(row["correct_word"]).lower().strip()
            if not w or not c:
                continue
            key = (w, c)
            self.counts[key] = int(row["frequency"])
            self.first_seen[key] = str(row.get("first_seen", ""))
            self.last_seen[key] = str(row.get("last_seen", ""))
        self._save()

    def _save(self) -> None:
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.csv_path.with_suffix(self.csv_path.suffix + ".tmp")
        with tmp_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["wrong_word", "correct_word", "frequency", "first_seen", "last_seen"])
            for row in self.export():
                writer.writerow([
                    row["wrong_word"],
                    row["correct_word"],
                    row["frequency"],
                    row["first_seen"],
                    row["last_seen"],
                ])
        tmp_path.replace(self.csv_path)


class SQLiteCorrectionHistoryRepository(CorrectionHistoryRepository):
    """SQLite-backed persistent correction history repository for production integration."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS correction_history (
                    wrong_word TEXT NOT NULL,
                    correct_word TEXT NOT NULL,
                    frequency INTEGER NOT NULL DEFAULT 1,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    PRIMARY KEY (wrong_word, correct_word)
                )
            """)
            conn.commit()

    def record_correction(self, wrong: str, correct: str) -> None:
        wrong_clean = (wrong or "").lower().strip()
        correct_clean = (correct or "").lower().strip()
        if not wrong_clean or not correct_clean:
            return
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO correction_history (wrong_word, correct_word, frequency, first_seen, last_seen)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(wrong_word, correct_word) DO UPDATE SET
                    frequency = frequency + 1,
                    last_seen = excluded.last_seen
            """, (wrong_clean, correct_clean, now, now))
            conn.commit()

    def get_frequency(self, wrong: str, correct: str) -> int:
        wrong_clean = (wrong or "").lower().strip()
        correct_clean = (correct or "").lower().strip()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT frequency FROM correction_history WHERE wrong_word = ? AND correct_word = ?",
                (wrong_clean, correct_clean)
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def get_candidate_frequency(self, wrong: str) -> dict[str, int]:
        wrong_clean = (wrong or "").lower().strip()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT correct_word, frequency FROM correction_history WHERE wrong_word = ?",
                (wrong_clean,)
            )
            return {row[0]: int(row[1]) for row in cur.fetchall()}

    def get_last_seen(self, wrong: str, correct: str) -> str:
        wrong_clean = (wrong or "").lower().strip()
        correct_clean = (correct or "").lower().strip()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT last_seen FROM correction_history WHERE wrong_word = ? AND correct_word = ?",
                (wrong_clean, correct_clean)
            )
            row = cur.fetchone()
            return str(row[0]) if row else ""

    def clear(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM correction_history")
            conn.commit()

    def export(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT wrong_word, correct_word, frequency, first_seen, last_seen FROM correction_history ORDER BY wrong_word, correct_word"
            )
            return [
                {
                    "wrong_word": row[0],
                    "correct_word": row[1],
                    "frequency": int(row[2]),
                    "first_seen": row[3],
                    "last_seen": row[4],
                }
                for row in cur.fetchall()
            ]

    def import_rows(self, rows: Sequence[Mapping[str, str | int]]) -> None:
        self.clear()
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO correction_history (wrong_word, correct_word, frequency, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?)
            """, [
                (
                    str(r["wrong_word"]).lower().strip(),
                    str(r["correct_word"]).lower().strip(),
                    int(r["frequency"]),
                    str(r.get("first_seen", "")),
                    str(r.get("last_seen", "")),
                )
                for r in rows
            ])
            conn.commit()


class InMemoryCorrectionHistoryRepository(CorrectionHistoryRepository):
    """In-memory history repository for testing or when no CSV/DB is provided."""

    def __init__(self):
        self.counts: Counter[tuple[str, str]] = Counter()
        self.first_seen: dict[tuple[str, str], str] = {}
        self.last_seen: dict[tuple[str, str], str] = {}

    def record_correction(self, wrong: str, correct: str) -> None:
        wrong_clean = (wrong or "").lower().strip()
        correct_clean = (correct or "").lower().strip()
        if not wrong_clean or not correct_clean:
            return
        key = (wrong_clean, correct_clean)
        self.counts[key] += 1
        now = datetime.now(timezone.utc).isoformat()
        if key not in self.first_seen:
            self.first_seen[key] = now
        self.last_seen[key] = now

    def get_frequency(self, wrong: str, correct: str) -> int:
        return self.counts.get(((wrong or "").lower().strip(), (correct or "").lower().strip()), 0)

    def get_candidate_frequency(self, wrong: str) -> dict[str, int]:
        wrong_clean = (wrong or "").lower().strip()
        return {c: cnt for (w, c), cnt in self.counts.items() if w == wrong_clean}

    def get_last_seen(self, wrong: str, correct: str) -> str:
        return self.last_seen.get(((wrong or "").lower().strip(), (correct or "").lower().strip()), "")

    def clear(self) -> None:
        self.counts.clear()
        self.first_seen.clear()
        self.last_seen.clear()

    def export(self) -> list[dict]:
        return [
            {
                "wrong_word": w,
                "correct_word": c,
                "frequency": count,
                "first_seen": self.first_seen.get((w, c), ""),
                "last_seen": self.last_seen.get((w, c), ""),
            }
            for (w, c), count in self.counts.items()
        ]

    def import_rows(self, rows: Sequence[Mapping[str, str | int]]) -> None:
        self.clear()
        for r in rows:
            w = str(r["wrong_word"]).lower().strip()
            c = str(r["correct_word"]).lower().strip()
            if w and c:
                key = (w, c)
                self.counts[key] = int(r["frequency"])
                self.first_seen[key] = str(r.get("first_seen", ""))
                self.last_seen[key] = str(r.get("last_seen", ""))


class CorrectionHistory:
    """Domain service wrapping a repository and applying frequency thresholds and time decay."""

    def __init__(self, csv_path: str | Path | None = None, config=None, repository: CorrectionHistoryRepository | None = None):
        self.config = config
        if repository is not None:
            self.repository = repository
        elif csv_path is not None:
            p_str = str(csv_path)
            if p_str.endswith((".db", ".sqlite", ".sqlite3")):
                self.repository = SQLiteCorrectionHistoryRepository(csv_path)
            else:
                self.repository = CSVCorrectionHistoryRepository(csv_path)
        else:
            self.repository = InMemoryCorrectionHistoryRepository()

    def _decay_factor(self, last_seen: str) -> float:
        if not last_seen or not self.config:
            return 1.0
        decay_days = getattr(self.config, "history_decay_days", None)
        if not decay_days or decay_days <= 0:
            return 1.0
        try:
            last_dt = datetime.fromisoformat(last_seen)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            age_days = max(0.0, (now - last_dt).total_seconds() / 86400.0)
            if age_days < 0.001:
                return 1.0
            return math.exp(-0.69314718 * (age_days / decay_days))
        except (ValueError, TypeError):
            return 1.0

    def score(self, wrong: str, correct: str) -> float:
        frequencies = self.repository.get_candidate_frequency(wrong)
        if not frequencies:
            return 0.0
        raw_value = self.repository.get_frequency(wrong, correct)
        minimum = getattr(self.config, "minimum_history_frequency", 1)
        if raw_value < minimum:
            return 0.0

        get_last = getattr(self.repository, "get_last_seen", None)
        last_seen = get_last(wrong, correct) if get_last else ""
        decay = self._decay_factor(last_seen)
        effective_value = raw_value * decay

        max_for_wrong = max(frequencies.values(), default=0)
        if max_for_wrong <= 0:
            return 0.0
        return min(1.0, effective_value / max_for_wrong)

    def record(self, wrong: str, correct: str) -> None:
        self.repository.record_correction(wrong, correct)

    def record_correction(self, wrong: str, correct: str) -> None:
        self.record(wrong, correct)

    def get_frequency(self, wrong: str, correct: str) -> int:
        return self.repository.get_frequency(wrong, correct)

    def get_candidate_frequency(self, wrong: str) -> dict[str, int]:
        return self.repository.get_candidate_frequency(wrong)

    def clear(self) -> None:
        self.repository.clear()

    def export(self) -> list[dict]:
        return self.repository.export()

    def import_rows(self, rows: Sequence[Mapping[str, str | int]]) -> None:
        self.repository.import_rows(rows)
