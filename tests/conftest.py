import os
from pathlib import Path


def pytest_ignore_collect(collection_path: Path, config) -> bool | None:
    integration_enabled = (
        os.getenv("RUN_INTEGRATION_TESTS", "false").lower() == "true"
    )
    if not integration_enabled and "tests/integration" in collection_path.as_posix():
        return True
    return None
