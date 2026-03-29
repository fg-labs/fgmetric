# fgmetric

[![CI](https://github.com/fulcrumgenomics/fgmetric/actions/workflows/python_package.yml/badge.svg?branch=main)](https://github.com/fulcrumgenomics/fgmetric/actions/workflows/python_package.yml?query=branch%3Amain)
[![Python Versions](https://img.shields.io/badge/python-3.12_|_3.13-blue)](https://github.com/fulcrumgenomics/fgmetric)
[![MyPy Checked](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)

**Type-validated Python models for delimited data files.**

`fgmetric` lets you define Python classes ("Metrics") that map directly to rows in CSV/TSV files.
It handles parsing, type coercion (strings to int, float, bool), and validation automatically using [Pydantic](https://docs.pydantic.dev/latest/).

## Installation

=== "pip"

    ```console
    pip install fgmetric
    ```

=== "uv"

    ```console
    uv add fgmetric
    ```

## Quick Example

Define a class to represent each row, then read or write:

```python
from pathlib import Path
from fgmetric import Metric, MetricWriter


class AlignmentMetric(Metric):
    read_name: str
    mapping_quality: int
    is_duplicate: bool = False


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

## Why fgmetric?

- **vs. csv + dataclasses** --- Automatic type coercion and validation without boilerplate. Built on Pydantic, so custom validators and serializers can be readily added.
- **vs. pandas** --- Processes records lazily, handling files larger than memory. Metrics are type-validated and can be made immutable.
- **vs. Pydantic alone** --- Handles CSV/TSV specifics (header parsing, delimiter configuration) and provides out-of-the-box features like empty value handling and Counter field pivoting.

[Get started with the User Guide](guide.md)
