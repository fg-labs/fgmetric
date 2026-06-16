from typing import ClassVar

from fgmetric.converters import CounterPivotTable
from fgmetric.converters import DelimitedList
from fgmetric.converters import NullSentinels
from fgmetric.record_model import RecordModel


class Metric(
    DelimitedList,
    CounterPivotTable,
    NullSentinels,
    RecordModel,
):
    """
    Abstract base class for defining structured "metric" data models.

    `Metric` is a `RecordModel` with the default `fgmetric.converters` mixins layered on. It
    provides the same file-reading and -writing surface as `RecordModel` (see `RecordModel.read`,
    `ModelReader`, and `ModelWriter`) plus the conversion behaviors below. Subclasses should define
    their fields using Pydantic field annotations.

    Metrics are delimited files containing a header and zero or more rows for metric values. When
    using a `Metric` to read a delimited file, the `Metric`'s fields correspond to the columns and
    header of the file.

    Relative to a plain `RecordModel`, `Metric` adds the following custom
    serialization/deserialization behaviors:

    1. **Null sentinels.** Empty strings in Optional fields are converted to `None` before field
       validation. The sentinel values converted to `None` can be overridden by the
       `null_sentinels` class variable.
    2. **Delimited lists.** Any field typed as `list[T]` will be parsed from and serialized to a
       delimited string. The list delimiter may be controlled by the `collection_delimiter` class
       variable.
    3. **Counter pivot tables.** A single field typed as `Counter[T]` (where `T` is a `StrEnum`)
       is pivoted into one column per enum member during serialization and folded back during
       validation.

    Class Variables:
        collection_delimiter: A single-character delimiter used to split and join `list` fields
            during serialization/deserialization.
        null_sentinels: The set of input strings that should be treated as `None` on Optional
            fields during validation. Defaults to `frozenset({""})`.

    Example:
        ```python
        class AlignmentMetric(Metric):
            read_name: str
            mapping_quality: int
            is_duplicate: bool = False

        # Read metrics from a TSV file
        for metric in AlignmentMetric.read("metrics.txt"):
            print(metric.read_name, metric.mapping_quality)
        ```
    """

    null_sentinels: ClassVar[frozenset[str]] = frozenset({""})
