# fgmetric

Type-validated Python models for delimited data files.

[![Docs](https://readthedocs.org/projects/fgmetric/badge/?version=stable)](https://fgmetric.readthedocs.io/)
[![CI](https://github.com/fulcrumgenomics/fgmetric/actions/workflows/python_package.yml/badge.svg?branch=main)](https://github.com/fulcrumgenomics/fgmetric/actions/workflows/python_package.yml?query=branch%3Amain)
[![Python Versions](https://img.shields.io/badge/python-3.12_|_3.13-blue)](https://github.com/fulcrumgenomics/fgmetric)
[![MyPy Checked](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://docs.astral.sh/ruff/)

## Overview

`fgmetric` lets you define Python classes ("Metrics") that map directly to rows in CSV/TSV files.
It handles parsing, type coercion (strings → int, float, bool), and validation automatically using [Pydantic](https://docs.pydantic.dev/latest/).

## Installation

Requires Python 3.12 or later.

```console
pip install fgmetric
```

Or with [uv](https://docs.astral.sh/uv/):

```console
uv add fgmetric
```

## Why fgmetric?

If you're a bioinformatician or data engineer processing delimited files in Python, you've probably written code like this:

```python
import csv

with open("metrics.tsv") as f:
    reader = csv.DictReader(f, delimiter="\t")
    for row in reader:
        quality = int(row["mapping_quality"])
        is_duplicate = row["is_duplicate"].lower() in ("true", "1", "yes")
        if row["score"]:  # handle empty strings
            score = float(row["score"])
        # ... repeat for every field
```

`fgmetric` replaces this with:

```py
for metric in AlignmentMetric.read(path):
    # metric.mapping_quality is already an int
    # metric.is_duplicate is already a bool
    # metric.score is already Optional[float]
```

**How it compares:**
- **vs. csv + dataclasses** — Automatic type coercion and validation without boilerplate. Built on Pydantic, so additional custom validators and serializer can be readily added.
- **vs. pandas** — Unlike pandas, `fgmetric` processes records lazily — you can handle files larger than memory. And `Metric`s are type-validated and can be made immutable, making them safe to pass between functions without defensive copying.
- **vs. Pydantic alone** — `fgmetric` handles CSV/TSV specifics (header parsing, delimiter configuration) and provides out-of-the box features like empty value handling and Counter field pivoting.

## Quick Start

Define a class to represent each row:

```python
from pathlib import Path
from fgmetric import Metric, MetricWriter


class AlignmentMetric(Metric):
    read_name: str
    mapping_quality: int
    is_duplicate: bool = False
```

Then read or write:

```python
# Reading
for metric in AlignmentMetric.read(Path("alignments.tsv")):
    print(f"{metric.read_name}: MQ={metric.mapping_quality}")

# Writing
metrics = [
    AlignmentMetric(read_name="read1", mapping_quality=60),
    AlignmentMetric(read_name="read2", mapping_quality=30, is_duplicate=True),
]
with MetricWriter(AlignmentMetric, Path("output.tsv")) as writer:
    writer.writeall(metrics)
```

Example input file (`alignments.tsv`):

```tsv
read_name	mapping_quality	is_duplicate
read1	60	false
read2	30	true
```

Invalid data raises `pydantic.ValidationError` with details about which field failed.

## Core Usage

### Custom Delimiters

Both reading and writing support custom delimiters for working with CSV or other formats:

```python
# Reading CSV files
for metric in MyMetric.read(Path("data.csv"), delimiter=","):
    ...

# Writing CSV files
with MetricWriter(MyMetric, Path("output.csv"), delimiter=",") as writer:
    ...
```

### List Fields

Fields typed as `list[T]` are automatically parsed from and serialized to delimited strings:

```python
class TaggedRead(Metric):
    read_id: str
    tags: list[str]           # "A,B,C" becomes ["A", "B", "C"]
    scores: list[int]         # "1,2,3" becomes [1, 2, 3]
    optional_tags: list[str] | None  # "" becomes None
```

The list delimiter defaults to `,` but can be customized per-metric:

```python
class SemicolonMetric(Metric):
    collection_delimiter = ";"
    values: list[int]  # "1;2;3" becomes [1, 2, 3]
```

### Counter Fields

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


# Input TSV:
# position  A   C   G   T
# 1         10  5   3   2

# Parses to:
# BaseCountMetric(position=1, counts=Counter({Base.A: 10, Base.C: 5, ...}))
```

## Contributing

See the [contributing guide](./CONTRIBUTING.md) for development setup and testing instructions.
