import os
from collections.abc import Callable
from pathlib import Path

from fgmetric._paths import path_read_error
from fgmetric._paths import path_write_error

# ======================================================================================
# path_read_error
# ======================================================================================


def test_path_read_error_returns_none_for_readable_file(tmp_path: Path) -> None:
    """A regular file with read permission yields no error."""
    p = tmp_path / "metrics.tsv"
    p.write_text("name\tvalue\n")
    assert path_read_error(p) is None


def test_path_read_error_accepts_str(tmp_path: Path) -> None:
    """A path given as a str is accepted."""
    p = tmp_path / "metrics.tsv"
    p.write_text("name\tvalue\n")
    assert path_read_error(str(p)) is None


def test_path_read_error_returns_none_for_fifo(tmp_path: Path) -> None:
    """A non-regular file such as a FIFO (e.g. from process substitution) is readable."""
    p = tmp_path / "fifo"
    os.mkfifo(p)
    assert path_read_error(p) is None


def test_path_read_error_for_missing_path(tmp_path: Path) -> None:
    """A path that does not exist yields FileNotFoundError."""
    error = path_read_error(tmp_path / "missing.tsv")
    assert isinstance(error, FileNotFoundError)
    assert "does not exist" in str(error)


def test_path_read_error_for_broken_symlink(tmp_path: Path) -> None:
    """A symlink to a nonexistent target yields FileNotFoundError naming both ends of the link."""
    target = tmp_path / "missing.tsv"
    link = tmp_path / "link.tsv"
    link.symlink_to(target)
    error = path_read_error(link)
    assert isinstance(error, FileNotFoundError)
    assert "symlink" in str(error)
    assert str(target) in str(error)


def test_path_read_error_for_directory(tmp_path: Path) -> None:
    """A directory yields IsADirectoryError."""
    error = path_read_error(tmp_path)
    assert isinstance(error, IsADirectoryError)
    assert "is a directory" in str(error)


def test_path_read_error_without_read_permission(
    tmp_path: Path, chmod: Callable[[Path, int], None]
) -> None:
    """A file whose read permission bits are unset yields PermissionError."""
    p = tmp_path / "metrics.tsv"
    p.write_text("name\tvalue\n")
    chmod(p, 0o000)
    error = path_read_error(p)
    assert isinstance(error, PermissionError)
    assert "not readable" in str(error)


# ======================================================================================
# path_write_error
# ======================================================================================


def test_path_write_error_returns_none_for_writable_file(tmp_path: Path) -> None:
    """An existing file with write permission yields no error."""
    p = tmp_path / "out.tsv"
    p.write_text("existing\n")
    assert path_write_error(p) is None


def test_path_write_error_accepts_str(tmp_path: Path) -> None:
    """A path given as a str is accepted."""
    assert path_write_error(str(tmp_path / "out.tsv")) is None


def test_path_write_error_returns_none_for_new_file_in_writable_directory(
    tmp_path: Path,
) -> None:
    """A nonexistent file in a writable directory yields no error."""
    assert path_write_error(tmp_path / "out.tsv") is None


def test_path_write_error_for_missing_parent(tmp_path: Path) -> None:
    """A nonexistent file in a nonexistent directory yields FileNotFoundError."""
    error = path_write_error(tmp_path / "missing" / "out.tsv")
    assert isinstance(error, FileNotFoundError)
    assert "does not exist" in str(error)


def test_path_write_error_for_parent_that_is_a_file(tmp_path: Path) -> None:
    """A path whose parent exists but is a file yields NotADirectoryError."""
    p = tmp_path / "afile.txt"
    p.write_text("x\n")
    error = path_write_error(p / "out.tsv")
    assert isinstance(error, NotADirectoryError)
    assert "not a directory" in str(error)


def test_path_write_error_returns_none_for_symlink_to_new_file_in_writable_directory(
    tmp_path: Path,
) -> None:
    """
    A symlink to a nonexistent file in a writable directory yields no error.

    Opening such a symlink for writing creates the target file.
    """
    link = tmp_path / "link.tsv"
    link.symlink_to(tmp_path / "target.tsv")
    assert path_write_error(link) is None


def test_path_write_error_for_symlink_into_missing_directory(tmp_path: Path) -> None:
    """A symlink whose target's parent directory does not exist yields FileNotFoundError."""
    link = tmp_path / "link.tsv"
    link.symlink_to(tmp_path / "missing" / "target.tsv")
    error = path_write_error(link)
    assert isinstance(error, FileNotFoundError)
    assert "does not exist" in str(error)


def test_path_write_error_for_directory(tmp_path: Path) -> None:
    """A directory yields IsADirectoryError."""
    error = path_write_error(tmp_path)
    assert isinstance(error, IsADirectoryError)
    assert "is a directory" in str(error)


def test_path_write_error_for_readonly_file(
    tmp_path: Path, chmod: Callable[[Path, int], None]
) -> None:
    """An existing file without write permission yields PermissionError."""
    p = tmp_path / "out.tsv"
    p.write_text("locked\n")
    chmod(p, 0o444)
    error = path_write_error(p)
    assert isinstance(error, PermissionError)
    assert "not writable" in str(error)


def test_path_write_error_for_readonly_parent(
    tmp_path: Path, chmod: Callable[[Path, int], None]
) -> None:
    """A nonexistent file in a read-only directory yields PermissionError."""
    d = tmp_path / "readonly"
    d.mkdir()
    chmod(d, 0o555)
    error = path_write_error(d / "out.tsv")
    assert isinstance(error, PermissionError)
    assert "not writable" in str(error)


def test_path_write_error_overwrite_false_for_existing_file(tmp_path: Path) -> None:
    """With `overwrite=False`, an existing regular file yields FileExistsError."""
    p = tmp_path / "out.tsv"
    p.write_text("existing\n")
    error = path_write_error(p, overwrite=False)
    assert isinstance(error, FileExistsError)
    assert "already exists" in str(error)


def test_path_write_error_overwrite_false_allows_new_file(tmp_path: Path) -> None:
    """With `overwrite=False`, a nonexistent file in a writable directory yields no error."""
    assert path_write_error(tmp_path / "out.tsv", overwrite=False) is None


def test_path_write_error_overwrite_false_for_symlink_to_existing_file(tmp_path: Path) -> None:
    """With `overwrite=False`, a symlink resolving to an existing file yields FileExistsError."""
    target = tmp_path / "target.tsv"
    target.write_text("existing\n")
    link = tmp_path / "link.tsv"
    link.symlink_to(target)
    error = path_write_error(link, overwrite=False)
    assert isinstance(error, FileExistsError)
    assert "already exists" in str(error)


def test_path_write_error_overwrite_false_allows_broken_symlink(tmp_path: Path) -> None:
    """With `overwrite=False`, a symlink to a nonexistent target is not a clobber and is allowed."""
    link = tmp_path / "link.tsv"
    link.symlink_to(tmp_path / "target.tsv")
    # Writing through the link creates the target, so there is nothing to overwrite.
    assert path_write_error(link, overwrite=False) is None


def test_path_write_error_overwrite_false_allows_fifo(tmp_path: Path) -> None:
    """With `overwrite=False`, a non-regular file such as a FIFO is not a clobber and is allowed."""
    p = tmp_path / "fifo"
    os.mkfifo(p)
    assert path_write_error(p, overwrite=False) is None


def test_path_write_error_overwrite_false_for_directory(tmp_path: Path) -> None:
    """With `overwrite=False`, a directory still yields the more specific IsADirectoryError."""
    error = path_write_error(tmp_path, overwrite=False)
    assert isinstance(error, IsADirectoryError)
    assert "is a directory" in str(error)


def test_path_write_error_overwrite_false_for_readonly_file(
    tmp_path: Path, chmod: Callable[[Path, int], None]
) -> None:
    """With `overwrite=False`, a read-only existing file still yields PermissionError first."""
    p = tmp_path / "out.tsv"
    p.write_text("locked\n")
    chmod(p, 0o444)
    error = path_write_error(p, overwrite=False)
    assert isinstance(error, PermissionError)
    assert "not writable" in str(error)
