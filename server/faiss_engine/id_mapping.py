"""
FAISS Vector Search Module — Book Identifier & Metadata Mapping.

Maintains a robust, synchronized, bidirectional mapping between 64-bit integer
FAISS IDs and MongoDB string ObjectIds, along with cached book metadata
for fast in-memory filtering.

Includes a generation_id for cross-validation with index artifacts.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class IdMappingManager:
    """
    Manages vector ID to MongoDB ObjectId mappings and book metadata cache.
    Persists data atomically to disk as JSON.
    """

    def __init__(self, mapping_path: Path):
        self.mapping_path = Path(mapping_path)
        # faiss_id (int) -> mongo_id (str)
        self._faiss_to_mongo: Dict[int, str] = {}
        # mongo_id (str) -> faiss_id (int)
        self._mongo_to_faiss: Dict[str, int] = {}
        # faiss_id (int) -> dict of metadata
        self._metadata_cache: Dict[int, Dict[str, Any]] = {}
        # Next sequential ID
        self._next_id: int = 0
        # Generation identifier for cross-validation with index
        self._generation_id: Optional[str] = None

    @property
    def generation_id(self) -> Optional[str]:
        return self._generation_id

    @generation_id.setter
    def generation_id(self, value: Optional[str]):
        self._generation_id = value

    @property
    def faiss_to_mongo(self) -> Dict[int, str]:
        """Read-only view of FAISS ID to MongoDB ID dictionary."""
        return dict(self._faiss_to_mongo)

    @property
    def faiss_ids(self) -> List[int]:
        """List of all registered FAISS vector IDs."""
        return list(self._faiss_to_mongo.keys())

    def __len__(self) -> int:
        return len(self._faiss_to_mongo)

    def get_book_id(self, faiss_id: int) -> Optional[str]:
        """Lookup MongoDB ObjectId by FAISS vector index ID."""
        return self._faiss_to_mongo.get(int(faiss_id))

    def get_faiss_id(self, mongo_id: str) -> Optional[int]:
        """Lookup FAISS vector index ID by MongoDB ObjectId."""
        return self._mongo_to_faiss.get(str(mongo_id))

    def get_metadata(self, faiss_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve cached metadata for a given FAISS vector ID."""
        return self._metadata_cache.get(int(faiss_id))

    def add_entry(self, mongo_id: str, metadata: Dict[str, Any], faiss_id: Optional[int] = None) -> int:
        """
        Register a book in the mapping. If faiss_id is None, assigns the next sequential integer.
        Returns the assigned faiss_id.
        """
        mongo_id_str = str(mongo_id)
        # If already exists, reuse or update
        if mongo_id_str in self._mongo_to_faiss:
            existing_id = self._mongo_to_faiss[mongo_id_str]
            self._metadata_cache[existing_id] = metadata
            return existing_id

        if faiss_id is None:
            fid = self._next_id
            self._next_id += 1
        else:
            fid = int(faiss_id)
            if fid >= self._next_id:
                self._next_id = fid + 1

        self._faiss_to_mongo[fid] = mongo_id_str
        self._mongo_to_faiss[mongo_id_str] = fid
        self._metadata_cache[fid] = metadata
        return fid

    def remove_by_mongo_id(self, mongo_id: str) -> Optional[int]:
        """Remove mapping for a book by MongoDB ObjectId. Returns removed FAISS ID if found."""
        mongo_id_str = str(mongo_id)
        fid = self._mongo_to_faiss.pop(mongo_id_str, None)
        if fid is not None:
            self._faiss_to_mongo.pop(fid, None)
            self._metadata_cache.pop(fid, None)
        return fid

    def clear(self):
        """Reset all in-memory mappings."""
        self._faiss_to_mongo.clear()
        self._mongo_to_faiss.clear()
        self._metadata_cache.clear()
        self._next_id = 0
        self._generation_id = None

    def get_all_entries(self) -> List[Tuple[int, str, Dict[str, Any]]]:
        """Return list of (faiss_id, mongo_id, metadata) tuples."""
        entries = []
        for fid, mid in sorted(self._faiss_to_mongo.items(), key=lambda x: x[0]):
            entries.append((fid, mid, self._metadata_cache.get(fid, {})))
        return entries

    def save(self):
        """Atomically persist mapping to JSON file."""
        self.mapping_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.mapping_path.with_suffix(".tmp")

        data = {
            "version": 2,
            "generation_id": self._generation_id,
            "next_id": self._next_id,
            "mappings": [
                {
                    "faiss_id": fid,
                    "mongo_id": mid,
                    "metadata": self._metadata_cache.get(fid, {})
                }
                for fid, mid in sorted(self._faiss_to_mongo.items(), key=lambda x: x[0])
            ]
        }

        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Atomic file replacement
        if os.path.exists(self.mapping_path):
            os.replace(temp_path, self.mapping_path)
        else:
            temp_path.rename(self.mapping_path)

    def load(self) -> bool:
        """
        Load mappings from JSON file. Returns True if successfully loaded,
        False if file does not exist.
        """
        if not self.mapping_path.exists():
            return False

        try:
            with open(self.mapping_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.clear()
            self._next_id = int(data.get("next_id", 0))
            self._generation_id = data.get("generation_id")

            for item in data.get("mappings", []):
                fid = int(item["faiss_id"])
                mid = str(item["mongo_id"])
                meta = item.get("metadata", {})
                self._faiss_to_mongo[fid] = mid
                self._mongo_to_faiss[mid] = fid
                self._metadata_cache[fid] = meta

            if self._faiss_to_mongo and max(self._faiss_to_mongo.keys()) >= self._next_id:
                self._next_id = max(self._faiss_to_mongo.keys()) + 1

            return True
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load or parse mapping file at {self.mapping_path}: {exc}"
            ) from exc
