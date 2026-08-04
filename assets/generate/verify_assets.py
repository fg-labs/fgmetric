"""
Verify the generated `assets/example.{PicardTool}` files.

Run from the repo root with the project environment so `fgmetric` is importable:

    uv run python assets/generate/verify_assets.py

Checks that every expected tool has exactly one example file, that each file is
non-empty and has the structure Picard produces (a `## METRICS CLASS` or
`## HISTOGRAM` table, an MD5 line, or a comparison report), and demonstrates that the
metrics table of one file round-trips through `fgmetric.MetricReader`.

Exits non-zero if any asset is missing or malformed.
"""

import re
import sys
from collections.abc import Iterator
from pathlib import Path

from fgmetric import Metric
from fgmetric import MetricReader

ASSETS = Path("assets")

# Tools whose example file is not a Picard metrics/histogram table.
MD5_TOOLS = {"CalculateReadGroupChecksum"}
REPORT_TOOLS = {"CompareMetrics"}

# Every tool that must have an example file.
EXPECTED_TOOLS = [
    "CollectAlignmentSummaryMetrics",
    "CollectInsertSizeMetrics",
    "CollectBaseDistributionByCycle",
    "CollectQualityYieldMetrics",
    "MeanQualityByCycle",
    "QualityScoreDistribution",
    "CollectJumpingLibraryMetrics",
    "CalculateReadGroupChecksum",
    "CollectMultipleMetrics",
    "MarkDuplicates",
    "MarkDuplicatesWithMateCigar",
    "UmiAwareMarkDuplicatesWithMateCigar",
    "EstimateLibraryComplexity",
    "CollectGcBiasMetrics",
    "CollectWgsMetrics",
    "CollectRawWgsMetrics",
    "CollectWgsMetricsWithNonZeroCoverage",
    "CollectOxoGMetrics",
    "CollectSequencingArtifactMetrics",
    "CollectRrbsMetrics",
    "CollectHsMetrics",
    "CollectTargetedPcrMetrics",
    "CollectRnaSeqMetrics",
    "CollectVariantCallingMetrics",
    "GenotypeConcordance",
    "CompareMetrics",
    "CollectIlluminaLaneMetrics",
    "CollectIlluminaBasecallingMetrics",
    "CollectHiSeqXPfFailMetrics",
]


def extract_table(lines: list[str]) -> tuple[list[str], list[list[str]]] | None:
    """
    Extract the tab-delimited table that follows a Picard section marker.

    Args:
        lines: The lines of a Picard metrics file (newlines stripped).

    Returns:
        A tuple of (header columns, data rows) for the first `## METRICS CLASS` or
        `## HISTOGRAM` section, or None if no well-formed table is found.
    """
    marker = next(
        (i for i, ln in enumerate(lines) if ln.startswith(("## METRICS CLASS", "## HISTOGRAM"))),
        None,
    )
    if marker is None or marker + 1 >= len(lines):
        return None
    header = lines[marker + 1].split("\t")
    rows: list[list[str]] = []
    for ln in lines[marker + 2 :]:
        if not ln.strip() or ln.startswith("#"):
            break
        rows.append(ln.split("\t"))
    if len(header) < 2 or not rows:
        return None
    return header, rows


def validate_metrics_file(path: Path) -> str | None:
    """
    Validate a Picard metrics/histogram file's structure.

    Args:
        path: Path to the example file.

    Returns:
        None if valid, otherwise a human-readable error message.
    """
    lines = path.read_text().splitlines()
    if not any(ln.startswith("## htsjdk.samtools.metrics") for ln in lines):
        return "missing htsjdk metrics header"
    table = extract_table(lines)
    if table is None:
        return "no well-formed METRICS CLASS / HISTOGRAM table"
    header, rows = table
    bad = [r for r in rows if len(r) != len(header)]
    if bad:
        return f"{len(bad)} row(s) do not match the {len(header)}-column header"
    return None


def validate(tool: str) -> str | None:
    """
    Validate the example file for one tool.

    Args:
        tool: The Picard tool name.

    Returns:
        None if valid, otherwise a human-readable error message.
    """
    path = ASSETS / f"example.{tool}"
    if not path.exists():
        return "missing"
    if path.stat().st_size == 0:
        return "empty"
    text = path.read_text()
    if tool in MD5_TOOLS:
        return None if re.fullmatch(r"[0-9a-f]{32}\s*", text) else "not a 32-char md5"
    if tool in REPORT_TOOLS:
        return None if "Metrics are" in text or "Comparison" in text else "not a comparison report"
    return validate_metrics_file(path)


def demo_fgmetric_parse() -> Iterator[str]:
    """
    Parse a Picard WGS metrics table with fgmetric to prove the table is consumable.

    Yields:
        Lines describing the parsed result.
    """

    class WgsMetric(Metric):
        """A subset of Picard's WgsMetrics columns (extra columns are ignored)."""

        GENOME_TERRITORY: int
        MEAN_COVERAGE: float
        SD_COVERAGE: float
        MEDIAN_COVERAGE: int

    lines = (ASSETS / "example.CollectWgsMetrics").read_text().splitlines()
    table = extract_table(lines)
    assert table is not None
    header, rows = table
    source = ["\t".join(header), *["\t".join(r) for r in rows]]
    # A directly-constructed reader is iterated (it does not own the source); only
    # MetricReader.open() is a context manager.
    for m in MetricReader(WgsMetric, source):
        yield (
            f"  fgmetric parsed WgsMetrics: GENOME_TERRITORY={m.GENOME_TERRITORY} "
            f"MEAN_COVERAGE={m.MEAN_COVERAGE} MEDIAN_COVERAGE={m.MEDIAN_COVERAGE}"
        )


def main() -> int:
    """
    Validate every expected asset and run the fgmetric parse demo.

    Returns:
        Process exit code (0 if all assets are valid).
    """
    found = sorted(p.name for p in ASSETS.glob("example.*"))
    failures: list[str] = []
    for tool in EXPECTED_TOOLS:
        err = validate(tool)
        status = "ok  " if err is None else "FAIL"
        print(f"  [{status}] example.{tool}{'' if err is None else f'  -- {err}'}")
        if err is not None:
            failures.append(tool)

    unexpected = set(found) - {f"example.{t}" for t in EXPECTED_TOOLS}
    if unexpected:
        print(f"\nUnexpected files: {sorted(unexpected)}")

    print(
        f"\n{len(EXPECTED_TOOLS) - len(failures)}/{len(EXPECTED_TOOLS)} assets valid; "
        f"{len(found)} files present."
    )

    print("\nfgmetric round-trip demo:")
    for line in demo_fgmetric_parse():
        print(line)

    if failures:
        print(f"\nFAILURES: {failures}")
        return 1
    print("\nAll assets valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
