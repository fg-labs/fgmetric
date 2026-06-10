from pathlib import Path

# Suffixes xopen treats as compression and strips for format detection.
_COMPRESSION_SUFFIXES = frozenset({".gz", ".bz2", ".xz"})

_DELIMITER_BY_SUFFIX: dict[str, str] = {".csv": ",", ".tsv": "\t", ".txt": "\t", ".tab": "\t"}

# Picard-style extensions (e.g. `.insert_size_metrics`) are tab-delimited.
_METRICS_SUFFIX = "metrics"


def infer_delimiter(path: Path | str) -> str:
    """
    Infer the field delimiter from a path's file extension.

    A single trailing compression suffix (`.gz`, `.bz2`, `.xz`) is stripped first, mirroring
    `xopen`'s compression detection, so `.tsv.gz`, `.csv.bz2`, etc. resolve from the underlying
    data extension. Matching is case-insensitive.

    `.csv` resolves to a comma; `.tsv`, `.txt`, `.tab`, and any extension ending in `metrics`
    (e.g. Picard-style `.insert_size_metrics`) resolve to a tab.

    Args:
        path: The file path whose extension determines the delimiter.

    Returns:
        The single-character field delimiter.

    Raises:
        ValueError: If the extension is not recognized. Pass `delimiter=` explicitly for such
            files.
    """
    p = Path(path)
    suffixes = [suffix.lower() for suffix in p.suffixes]
    if suffixes and suffixes[-1] in _COMPRESSION_SUFFIXES:
        suffixes.pop()
    data_suffix = suffixes[-1] if suffixes else ""
    if data_suffix in _DELIMITER_BY_SUFFIX:
        return _DELIMITER_BY_SUFFIX[data_suffix]
    if data_suffix.endswith(_METRICS_SUFFIX):
        return "\t"
    recognized = ", ".join(_DELIMITER_BY_SUFFIX)
    raise ValueError(
        f"Could not infer a delimiter from path {p.name!r}. Recognized extensions are "
        f"{recognized}, and any extension ending in 'metrics', optionally followed by a "
        "compression suffix (.gz, .bz2, .xz). Pass `delimiter=` explicitly for other files."
    )
