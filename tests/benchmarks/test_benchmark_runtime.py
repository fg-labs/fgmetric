from pathlib import Path

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

try:
    import fgpyo  # noqa: F401

    HAS_FGPYO = True
except ImportError:
    HAS_FGPYO = False


NUM_ROWS: list[str] = ["1e4", "1e5"]


@pytest.mark.parametrize("num_rows", NUM_ROWS)
def test_fgmetric(benchmark: BenchmarkFixture, benchmark_data: Path, num_rows: str) -> None:
    from fgmetric import Metric
    from fgmetric import ModelReader

    class DemoMetric(Metric):
        foo: int
        bar: str
        baz: float
        abc: str
        ghi: int | None
        jkl: str

    tsv = benchmark_data / f"demo.{num_rows}.tsv"

    def read_all() -> list[DemoMetric]:
        with ModelReader.open(DemoMetric, tsv) as reader:
            return list(reader)

    benchmark(read_all)


@pytest.mark.skipif(not HAS_FGPYO, reason="fgpyo not installed")
@pytest.mark.parametrize("num_rows", NUM_ROWS)
def test_fgpyo(benchmark: BenchmarkFixture, benchmark_data: Path, num_rows: str) -> None:
    from dataclasses import dataclass
    from typing import Optional

    from fgpyo.util.metric import Metric

    @dataclass
    class DemoMetric(Metric["DemoMetric"]):
        foo: int
        bar: str
        baz: float
        abc: str
        ghi: Optional[int]
        jkl: str

    tsv = benchmark_data / f"demo.{num_rows}.tsv"
    benchmark(lambda: list(DemoMetric.read(tsv)))
