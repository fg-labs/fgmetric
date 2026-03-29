# User Guide

## Defining a Metric

A `Metric` is a Pydantic model that maps to rows in a delimited file.
Define one by subclassing `Metric` and declaring fields with type annotations:

```python
from fgmetric import Metric


class AlignmentMetric(Metric):
    read_name: str
    mapping_quality: int
    is_duplicate: bool = False
```

Each field corresponds to a column in your file.
Pydantic handles type coercion automatically --- string values like `"60"` become `int`, `"true"` becomes `bool`, and so on.

## Reading Metrics

Use the `read()` class method to iterate over rows in a delimited file:

```python
from pathlib import Path

for metric in AlignmentMetric.read(Path("alignments.tsv")):
    print(f"{metric.read_name}: MQ={metric.mapping_quality}")
```

`read()` yields one `Metric` instance per row, lazily --- so you can process files larger than memory.
If any row fails validation, Pydantic raises a `ValidationError` with details about which field failed and why.

Example input file (`alignments.tsv`):

```tsv
read_name	mapping_quality	is_duplicate
read1	60	false
read2	30	true
```

### Custom Delimiters

By default, `read()` expects tab-separated values. Pass a `delimiter` argument for other formats:

```python
# Reading CSV files
for metric in AlignmentMetric.read(Path("data.csv"), delimiter=","):
    ...
```

### Empty Fields

Empty fields in optional columns are automatically converted to `None`:

```python
class QualityMetric(Metric):
    sample: str
    score: float | None  # Empty string in file becomes None
```

## Writing Metrics

Use `MetricWriter` as a context manager to write metrics to a file:

```python
from fgmetric import MetricWriter

metrics = [
    AlignmentMetric(read_name="read1", mapping_quality=60),
    AlignmentMetric(read_name="read2", mapping_quality=30, is_duplicate=True),
]

with MetricWriter(AlignmentMetric, Path("output.tsv")) as writer:
    writer.writeall(metrics)
```

The writer automatically outputs the header row based on the Metric's field names.
You can also write one metric at a time with `writer.write(metric)`.

### Custom Delimiters

Just like reading, writing supports custom delimiters:

```python
with MetricWriter(AlignmentMetric, Path("output.csv"), delimiter=",") as writer:
    writer.writeall(metrics)
```

## List Fields

Fields typed as `list[T]` are automatically parsed from and serialized to delimited strings:

```python
class TaggedRead(Metric):
    read_id: str
    tags: list[str]           # "A,B,C" becomes ["A", "B", "C"]
    scores: list[int]         # "1,2,3" becomes [1, 2, 3]
    optional_tags: list[str] | None  # "" becomes None
```

The list delimiter defaults to `,` but can be customized per-metric with the `collection_delimiter` class variable:

```python
class SemicolonMetric(Metric):
    collection_delimiter = ";"
    values: list[int]  # "1;2;3" becomes [1, 2, 3]
```

## Counter Fields

When your file has categorical data with one column per category (e.g. base counts A, C, G, T), you can model them as a single `Counter[StrEnum]` field:

```python
from collections import Counter
from enum import StrEnum

from fgmetric import Metric


class Base(StrEnum):
    A = "A"
    C = "C"
    G = "G"
    T = "T"


class BaseCountMetric(Metric):
    position: int
    counts: Counter[Base]
```

Given an input file:

```tsv
position	A	C	G	T
1	10	5	3	2
```

This parses to:

```python
BaseCountMetric(position=1, counts=Counter({Base.A: 10, Base.C: 5, Base.G: 3, Base.T: 2}))
```

The enum members define both the expected column names and the keys in the resulting `Counter`.
When writing, the `Counter` is "pivoted" back into separate columns.
