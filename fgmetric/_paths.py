import os
from pathlib import Path


def path_read_error(path: Path | str) -> OSError | None:
    """
    Return the error that would result from opening `path` for reading.

    A path is readable when it exists, is not a directory, and the current user has read
    permission. Non-regular files, e.g. FIFOs from process substitution and character devices
    such as `/dev/stdin`, are readable. A symlink whose target does not exist is reported as a
    broken symlink rather than a missing file.

    Args:
        path: Filesystem path to check.

    Returns:
        None if `path` is readable; otherwise an unraised exception whose type and message
        describe the problem (`FileNotFoundError`, `IsADirectoryError`, or `PermissionError`).
    """
    path = Path(path)

    if not path.exists():
        # `exists()` follows symlinks, so a broken symlink reaches this branch even though the
        # link itself is present; name both ends of the link to point at the actual problem.
        message = (
            f"Path is a symlink to a target that does not exist: {path} -> {path.readlink()}"
            if path.is_symlink()
            else f"File does not exist: {path}"
        )
        return FileNotFoundError(message)
    if path.is_dir():
        return IsADirectoryError(f"Path is a directory: {path}")
    if not os.access(path, os.R_OK):
        return PermissionError(f"File is not readable: {path}")

    return None


def path_write_error(path: Path | str, overwrite: bool = True) -> OSError | None:
    """
    Return the error that would result from opening `path` for writing.

    An existing path is writable when it is not a directory and the current user has write
    permission. A nonexistent path is writable when its parent directory exists and the current
    user can create files in it (write and traverse permission on the directory). Symlinks are
    resolved first, so the checks apply where the write would actually land: a symlink to a
    nonexistent file is writable when the target's parent directory is.

    When `overwrite` is `False`, an existing writable regular file is reported as an error rather
    than silently clobbered. Only regular files are guarded: directories already report the more
    specific `IsADirectoryError`, and non-regular files (FIFOs, devices such as `/dev/stdout`)
    are not destroyed by a write, so they remain writable. A read-only existing file reports
    `PermissionError` regardless of `overwrite`, since `overwrite=True` could not write it either.

    Args:
        path: Filesystem path to check.
        overwrite: When `False`, refuse to clobber an existing regular file. Defaults to `True`.

    Returns:
        None if `path` is writable; otherwise an unraised exception whose type and message
        describe the problem (`FileNotFoundError`, `NotADirectoryError`, `IsADirectoryError`,
        `PermissionError`, or `FileExistsError`).
    """
    path = Path(path)

    # Resolve symlinks before taking the parent
    parent = path.resolve().parent

    # Parent must be an extant directory
    if not parent.exists():
        return FileNotFoundError(f"Parent directory does not exist: {parent}")
    if not parent.is_dir():
        return NotADirectoryError(f"Parent is not a directory: {parent}")

    if path.is_dir():
        return IsADirectoryError(f"Path is a directory: {path}")
    if path.exists():
        if not os.access(path, os.W_OK):
            return PermissionError(f"File is not writable: {path}")
        if not overwrite and path.is_file():
            return FileExistsError(f"File already exists: {path}")
    elif not os.access(parent, os.W_OK | os.X_OK):
        return PermissionError(f"Parent directory is not writable: {parent}")

    return None
