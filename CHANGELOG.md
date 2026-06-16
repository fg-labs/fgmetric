# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Add `RecordModel`, a mixin-free base class providing the default tabular read/write surface without the `fgmetric.converters` mixins; `Metric` now subclasses it (#10)
- Introduce `ModelReader` for iterating records from any text-IO source (#41)
- Add an `encoding` kwarg on `ModelReader.open` and `ModelWriter.open` (#43)
- Transparent gzip/bz2/xz support via `xopen` (#44)
- Infer the delimiter from the file extension in `ModelReader.open`/`ModelWriter.open`; pass `delimiter=` to override (#61)

### Changed

- Rename `MetricReader`/`MetricWriter` to `ModelReader`/`ModelWriter`; the IO classes now read and write any `RecordModel` subclass, not just `Metric` (#10)
- `ModelWriter` is IO-first; open a path with `ModelWriter.open()` rather than passing it to the constructor (#42)
- `Metric.read` is now a thin wrapper over `ModelReader.open` and reads eagerly, returning a `list` instead of a lazy generator; it accepts `str` paths in addition to `Path` and gains transparent decompression and the `encoding` kwarg. Use `ModelReader.open` to stream metrics without holding them all in memory (#62)
- `ModelReader.open` and `ModelWriter.open` eagerly validate that the path is readable/writable on context entry (#66)

## [0.3.0] - 2026-05-12

### Added

- Expose `fieldnames` arg in `Metric.read` (#38)

## [0.2.0] - 2026-03-13

### Fixed

- Fix file handle leak in MetricWriter.__init__ (#24)
- Use JSON mode for model serialization in MetricWriter (#25)
- Specify UTF-8 encoding when opening output files (#26)
- Shallow copy input dict in `_empty_field_to_none` validator (#28)

### Changed

- Improve error messages in CounterPivotTable and DelimitedList (#27)
- Modernize type annotations (#29)

## [0.1.0] - 2026-01-22

### Added

- Initial release.
- Metric and MetricWriter (#6)
- Benchmarking (#7)
- Typing helpers (#2)
- Delimited lists mixin (#1)
- CounterPivotTable mixin (#3)
