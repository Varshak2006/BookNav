import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "server"))
sys.path.insert(0, str(ROOT_DIR / "server" / "lacs_engine"))
sys.path.insert(0, str(ROOT_DIR / "server" / "faiss_engine"))
