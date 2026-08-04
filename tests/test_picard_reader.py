from pathlib import Path

import pytest

from fgmetric.picard import PicardFloat
from fgmetric.picard import PicardMetric
from fgmetric.picard import PicardMetricReader
from fgmetric.picard._reader import metrics_block

ASSETS = Path(__file__).parents[1] / "assets"

# One example output per metrics-producing Picard tool; see docs/picard-example-assets.md.
ASSET_PATHS = sorted(ASSETS.glob("example.*"))

# Four of those outputs have no `## METRICS CLASS` section for this reader to find. Two are not
# metrics tables at all: `CalculateReadGroupChecksum` emits an md5 and `CompareMetrics` a
# comparison report. The other two emit only a `## HISTOGRAM` section, which needs the model
# shape that histogram support (a follow-up to this MVP) will add.
ASSETS_WITHOUT_A_METRICS_SECTION = [
    ASSETS / "example.CalculateReadGroupChecksum",
    ASSETS / "example.CompareMetrics",
    ASSETS / "example.MeanQualityByCycle",
    ASSETS / "example.QualityScoreDistribution",
]

ASSETS_WITH_A_METRICS_SECTION = [
    path for path in ASSET_PATHS if path not in ASSETS_WITHOUT_A_METRICS_SECTION
]

PREAMBLE = [
    "## htsjdk.samtools.metrics.StringHeader",
    "# CollectAlignmentSummaryMetrics INPUT=example.bam OUTPUT=metrics.txt",
    "## htsjdk.samtools.metrics.StringHeader",
    "# Started on: Wed Jun 10 13:31:07 EDT 2026",
    "",
]


class AlignmentSummaryMetric(PicardMetric):
    """The first two columns of Picard's AlignmentSummaryMetrics."""

    category: str
    total_reads: int


def test_reads_the_metrics_block_after_the_preamble() -> None:
    """The comment preamble is skipped and each data row becomes one metric."""
    source = [
        *PREAMBLE,
        "## METRICS CLASS\tpicard.analysis.AlignmentSummaryMetrics",
        "CATEGORY\tTOTAL_READS",
        "FIRST_OF_PAIR\t10820",
        "SECOND_OF_PAIR\t10820",
        "PAIR\t21640",
    ]

    metrics = list(PicardMetricReader(AlignmentSummaryMetric, source))

    assert [m.category for m in metrics] == ["FIRST_OF_PAIR", "SECOND_OF_PAIR", "PAIR"]
    assert [m.total_reads for m in metrics] == [10820, 10820, 21640]


def test_ignores_a_trailing_histogram_block() -> None:
    """A `## HISTOGRAM` block has different columns, so its rows must not be read as metrics."""
    source = [
        *PREAMBLE,
        "## METRICS CLASS\tpicard.analysis.AlignmentSummaryMetrics",
        "CATEGORY\tTOTAL_READS",
        "PAIR\t21640",
        "",
        "## HISTOGRAM\tjava.lang.Integer",
        "READ_LENGTH\tPAIRED_TOTAL_LENGTH_COUNT",
        "100\t21640",
        "",
    ]

    metrics = list(PicardMetricReader(AlignmentSummaryMetric, source))

    assert [m.category for m in metrics] == ["PAIR"]


def test_reads_only_the_first_metrics_block() -> None:
    """A second `## METRICS CLASS` block maps to a different model, so it is not read here."""
    source = [
        *PREAMBLE,
        "## METRICS CLASS\tpicard.analysis.AlignmentSummaryMetrics",
        "CATEGORY\tTOTAL_READS",
        "PAIR\t21640",
        "",
        "## METRICS CLASS\tpicard.analysis.SomeOtherMetrics",
        "CATEGORY\tTOTAL_READS",
        "UNPAIRED\t7",
    ]

    metrics = list(PicardMetricReader(AlignmentSummaryMetric, source))

    assert [m.category for m in metrics] == ["PAIR"]


def test_empty_source_yields_nothing() -> None:
    """An empty (0-byte) file iterates empty rather than raising."""
    assert list(PicardMetricReader(AlignmentSummaryMetric, [])) == []


def test_source_without_a_metrics_class_marker_raises() -> None:
    """Content with no metrics block has no header, so there is nothing to validate against."""
    reader = PicardMetricReader(AlignmentSummaryMetric, PREAMBLE)

    with pytest.raises(ValueError, match="METRICS CLASS"):
        list(reader)


def test_fieldnames_is_rejected() -> None:
    """The header always comes from inside the metrics block, so supplying names is an error."""
    with pytest.raises(ValueError, match="fieldnames"):
        PicardMetricReader(AlignmentSummaryMetric, [], fieldnames=["CATEGORY", "TOTAL_READS"])


class IlluminaLaneMetric(PicardMetric):
    """Picard's IlluminaLaneMetrics, the narrowest real metrics table in `assets/`."""

    cluster_density: float
    lane: int


def test_open_reads_a_real_picard_file() -> None:
    """The `open` classmethod reads a file Picard actually produced."""
    with PicardMetricReader.open(
        IlluminaLaneMetric,
        ASSETS / "example.CollectIlluminaLaneMetrics",
    ) as reader:
        metrics = list(reader)

    assert [m.lane for m in metrics] == [1, 2]
    assert metrics[0].cluster_density == 993597.96782


def test_open_on_an_empty_file_yields_nothing(tmp_path: Path) -> None:
    """A 0-byte file iterates empty rather than raising."""
    path = tmp_path / "empty.alignment_summary_metrics"
    path.touch()

    with PicardMetricReader.open(AlignmentSummaryMetric, path) as reader:
        assert list(reader) == []


def test_metric_read_uses_the_picard_reader() -> None:
    """
    `read`, inherited from `Metric`, must route through the Picard reader.

    `Metric.read` is an eager wrapper around a reader. Left inheriting the generic one, it
    would treat the first preamble line as the column header on every Picard file.
    """
    metrics = IlluminaLaneMetric.read(ASSETS / "example.CollectIlluminaLaneMetrics")

    assert [m.lane for m in metrics] == [1, 2]


def test_open_ignores_the_histogram_in_a_real_picard_file() -> None:
    """
    A real MarkDuplicates file carries a trailing histogram; only its one metric is read.

    The `.MarkDuplicates` extension is not one a delimiter can be inferred from, so this also
    covers `open` defaulting to the tab separator that the Picard format always uses.
    """

    class DuplicationMetric(PicardMetric):
        library: str
        unpaired_reads_examined: int
        read_pairs_examined: int
        secondary_or_supplementary_rds: int
        unmapped_reads: int
        unpaired_read_duplicates: int
        read_pair_duplicates: int
        read_pair_optical_duplicates: int
        percent_duplication: PicardFloat
        estimated_library_size: int

    with PicardMetricReader.open(DuplicationMetric, ASSETS / "example.MarkDuplicates") as reader:
        metrics = list(reader)

    assert len(metrics) == 1
    assert metrics[0].library == "lib1"
    assert metrics[0].percent_duplication == 0.076433


def test_open_maps_question_marks_in_a_real_file_to_none() -> None:
    """Picard's `?` float token becomes None on the rows of a real file that carries them."""

    class ConcordanceMetric(PicardMetric):
        variant_type: str
        truth_sample: str
        call_sample: str
        het_sensitivity: PicardFloat
        het_ppv: PicardFloat
        het_specificity: PicardFloat
        homvar_sensitivity: PicardFloat
        homvar_ppv: PicardFloat
        homvar_specificity: PicardFloat
        var_sensitivity: PicardFloat
        var_ppv: PicardFloat
        var_specificity: PicardFloat
        genotype_concordance: PicardFloat
        non_ref_genotype_concordance: PicardFloat

    with PicardMetricReader.open(
        ConcordanceMetric,
        ASSETS / "example.GenotypeConcordance",
    ) as reader:
        snp, indel = list(reader)

    assert snp.het_sensitivity == 1.0
    assert snp.het_specificity is None
    assert indel.variant_type == "INDEL"
    assert indel.het_sensitivity is None
    assert indel.non_ref_genotype_concordance is None


def test_every_metrics_producing_tool_has_an_example_asset() -> None:
    """Guard the sweeps below against silently collecting nothing if `assets/` moves."""
    assert len(ASSET_PATHS) == 29


@pytest.mark.parametrize("path", ASSETS_WITH_A_METRICS_SECTION, ids=lambda p: p.name)
def test_metrics_block_of_every_real_asset_is_a_well_formed_table(path: Path) -> None:
    """Across every real Picard output, the extracted block is a header plus aligned rows."""
    header, *rows = metrics_block(path.read_text().splitlines())
    columns = len(header.split("\t"))

    assert columns >= 2
    assert rows, "expected at least one data row"
    assert not any(row.startswith("#") for row in rows), "a comment leaked into the data rows"
    assert all(len(row.split("\t")) == columns for row in rows)


@pytest.mark.parametrize("path", ASSETS_WITHOUT_A_METRICS_SECTION, ids=lambda p: p.name)
def test_real_asset_with_no_metrics_section_raises(path: Path) -> None:
    """An md5, a comparison report, and the two histogram-only outputs have no table to read."""
    with pytest.raises(ValueError, match="METRICS CLASS"):
        list(metrics_block(path.read_text().splitlines()))
