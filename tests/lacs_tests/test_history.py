"""History repository tests for LACS (Phase 10 & 11).

Tests:
- CSV repository CRUD, persistence, import, export
- SQLite repository CRUD, persistence, import, export
- Minimum frequency gating against feedback loops
- Time decay application
- Integration with LACSAlgorithm
"""

import time
from pathlib import Path
from lacs.config import LACSConfig
from lacs.history import (
    CSVCorrectionHistoryRepository,
    SQLiteCorrectionHistoryRepository,
    CorrectionHistory,
)
from lacs import LACSAlgorithm

BASE = Path(__file__).resolve().parents[1]


def test_csv_repository_lifecycle(tmp_path):
    csv_file = tmp_path / "history.csv"
    repo = CSVCorrectionHistoryRepository(csv_file)
    assert repo.get_frequency("machne", "machine") == 0
    assert repo.get_candidate_frequency("machne") == {}

    repo.record_correction("machne", "machine")
    assert repo.get_frequency("machne", "machine") == 1
    assert repo.get_candidate_frequency("machne") == {"machine": 1}

    repo.record_correction("machne", "machine")
    assert repo.get_frequency("machne", "machine") == 2

    # Reload from disk to verify persistence
    repo2 = CSVCorrectionHistoryRepository(csv_file)
    assert repo2.get_frequency("machne", "machine") == 2

    # Export / clear / import
    rows = repo2.export()
    assert len(rows) == 1
    assert rows[0]["frequency"] == 2

    repo2.clear()
    assert repo2.get_frequency("machne", "machine") == 0

    repo2.import_rows(rows)
    assert repo2.get_frequency("machne", "machine") == 2


def test_sqlite_repository_lifecycle(tmp_path):
    db_file = tmp_path / "history.db"
    repo = SQLiteCorrectionHistoryRepository(db_file)
    assert repo.get_frequency("machne", "machine") == 0
    assert repo.get_candidate_frequency("machne") == {}

    repo.record_correction("machne", "machine")
    assert repo.get_frequency("machne", "machine") == 1
    assert repo.get_candidate_frequency("machne") == {"machine": 1}

    repo.record_correction("machne", "machine")
    assert repo.get_frequency("machne", "machine") == 2

    # Verify reload from disk
    repo2 = SQLiteCorrectionHistoryRepository(db_file)
    assert repo2.get_frequency("machne", "machine") == 2

    # Export / clear / import
    rows = repo2.export()
    assert len(rows) == 1
    assert rows[0]["frequency"] == 2

    repo2.clear()
    assert repo2.get_frequency("machne", "machine") == 0

    repo2.import_rows(rows)
    assert repo2.get_frequency("machne", "machine") == 2


def test_sqlite_algorithm_integration(tmp_path):
    db_file = tmp_path / "corrections.sqlite"
    algo = LACSAlgorithm(
        BASE / "data" / "library_books.csv",
        history_csv=db_file,
    )
    assert isinstance(algo.history.repository, SQLiteCorrectionHistoryRepository)

    # Minimum frequency threshold blocks untrusted single feedback
    algo.accept_correction("databse", "database")
    assert algo.history.score("databse", "database") == 0.0

    algo.accept_correction("databse", "database")
    assert algo.history.score("databse", "database") == 1.0


def test_time_decay_application(tmp_path):
    db_file = tmp_path / "decay.sqlite"
    cfg = LACSConfig(minimum_history_frequency=1, history_decay_days=30.0)
    repo = SQLiteCorrectionHistoryRepository(db_file)
    history = CorrectionHistory(config=cfg, repository=repo)

    # Insert old record: 60 days ago (2 half-lives)
    old_timestamp = "2020-01-01T00:00:00+00:00"
    repo.import_rows([{
        "wrong_word": "machne",
        "correct_word": "machine",
        "frequency": 10,
        "first_seen": old_timestamp,
        "last_seen": old_timestamp,
    }])

    # Score should be significantly decayed (much less than 1.0)
    score = history.score("machne", "machine")
    assert 0.0 <= score < 0.1, f"Decayed score {score} should be close to 0 due to old age"
