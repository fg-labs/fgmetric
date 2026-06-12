from pathlib import Path

# Suffixes xopen treats as compression and strips for format detection.
_COMPRESSION_SUFFIXES = frozenset({".gz", ".bz2", ".xz"})

_DELIMITER_BY_SUFFIX: dict[str, str] = {
    ".csv": ",",
    ".tsv": "\t",
    ".txt": "\t",
    ".tab": "\t",
}

# Picard-style extensions (e.g. `.insert_size_metrics`) are tab-delimited.
_METRICS_SUFFIX = "metrics"


def infer_delimiter(path: Path | str) -> str:
    """
    Infer the field delimiter from a path's file extension.

    A single trailing compression suffix (`.gz`, `.bz2`, `.xz`) is stripped if present, so
    `.tsv.gz`, `.csv.bz2`, etc. resolve from the underlying file format extension.

    `.csv` resolves to a comma; `.tsv`, `.txt`, `.tab`, and any extension ending in `metrics`
    (e.g. Picard-style `.insert_size_metrics`) resolve to a tab.

    Suffix matching is case-insensitive.

    Args:
        path: The file path whose extension determines the delimiter.

    Returns:
        The single-character field delimiter.

    Raises:
        ValueError: If the extension is not recognized. Pass `delimiter=` explicitly for such files.
    """
    p = Path(path)

    if p.suffix.lower() in _COMPRESSION_SUFFIXES:
        # strip compression suffix, if it exists
        p = p.with_suffix("")

    suffix = p.suffix.lower()

    if suffix in _DELIMITER_BY_SUFFIX:
        delimiter = _DELIMITER_BY_SUFFIX[suffix]
    elif suffix.endswith(_METRICS_SUFFIX):
        delimiter = "\t"
    else:
        recognized = ", ".join(_DELIMITER_BY_SUFFIX)
        raise ValueError(
            f"Could not infer a delimiter from path {p.name!r}. Recognized extensions are "
            f"{recognized}, and any extension ending in 'metrics', optionally followed by a "
            "compression suffix (.gz, .bz2, .xz). Pass `delimiter=` explicitly for other files."
        )

    return delimiter
