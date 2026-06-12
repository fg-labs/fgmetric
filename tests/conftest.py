from collections.abc import Callable
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def chmod() -> Iterator[Callable[[Path, int], None]]:
    """
    Set a path's permission bits for the duration of a test.

    Yields a function with the signature of `Path.chmod`. All paths modified through it are
    restored to their original modes (in reverse order) at teardown so pytest can clean up
    `tmp_path`.
    """
    changed: list[tuple[Path, int]] = []

    def _chmod(path: Path, mode: int) -> None:
        changed.append((path, path.stat().st_mode))
        path.chmod(mode)

    yield _chmod

    for path, mode in reversed(changed):
        try:
            path.chmod(mode)
        except FileNotFoundError:
            # Path was removed or renamed during the test; nothing to restore.
            continue
