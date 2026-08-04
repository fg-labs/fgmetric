import pytest
from pydantic import ValidationError

from fgmetric.picard import PicardFloat
from fgmetric.picard import PicardMetric


def test_snake_case_field_validates_from_an_upper_snake_header() -> None:
    """Picard headers are UPPER_SNAKE; fields are declared snake_case and aliased up."""

    class AlignmentSummaryMetric(PicardMetric):
        category: str
        total_reads: int

    metric = AlignmentSummaryMetric.model_validate(
        {"CATEGORY": "PAIR", "TOTAL_READS": "21640"},
    )

    assert metric.category == "PAIR"
    assert metric.total_reads == 21640


def test_field_may_also_be_supplied_by_its_python_name() -> None:
    """`populate_by_name` keeps models constructible in Python, not only from a file."""

    class AlignmentSummaryMetric(PicardMetric):
        category: str

    assert AlignmentSummaryMetric(category="PAIR").category == "PAIR"


def test_unexpected_column_is_rejected() -> None:
    """An undeclared column means the wrong model is being used for the file, so it raises."""

    class AlignmentSummaryMetric(PicardMetric):
        category: str

    with pytest.raises(ValidationError):
        AlignmentSummaryMetric.model_validate({"CATEGORY": "PAIR", "TOTAL_READS": "21640"})


def test_column_missing_from_the_file_is_allowed_when_the_field_has_a_default() -> None:
    """Picard's column set varies by version, so a defaulted field need not be present."""

    class AlignmentSummaryMetric(PicardMetric):
        category: str
        total_reads: int = 0

    metric = AlignmentSummaryMetric.model_validate({"CATEGORY": "PAIR"})

    assert metric.total_reads == 0


def test_blank_optional_column_becomes_none() -> None:
    """`PicardMetric` inherits `Metric`'s null-sentinel handling of blank fields."""

    class AlignmentSummaryMetric(PicardMetric):
        category: str
        pct_pf_reads: PicardFloat

    metric = AlignmentSummaryMetric.model_validate({"CATEGORY": "PAIR", "PCT_PF_READS": ""})

    assert metric.pct_pf_reads is None
