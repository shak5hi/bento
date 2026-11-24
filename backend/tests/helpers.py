"""Test helpers shared by unit and integration tests."""

import importlib.util
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def load_service(service: str, module: str = "main"):
    """Import services/<service>/<module>.py under a unique name (every service has a main.py)."""
    path = BACKEND / "services" / service / f"{module}.py"
    if str(path.parent) not in sys.path:  # sibling modules (e.g. notifier/digest.py) import by name
        sys.path.append(str(path.parent))
    spec = importlib.util.spec_from_file_location(f"{service}_{module}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod
