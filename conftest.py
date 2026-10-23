"""Makes the project root importable so tests can share helpers."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
