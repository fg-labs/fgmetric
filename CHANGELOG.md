# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### 💥 Breaking Changes

- Remove `Metric.read()` — read metrics via `MetricReader.open()` instead (#49)
- `MetricWriter` is IO-first; open a path with `MetricWriter.open()` rather than passing it to the constructor (#42)

### 🚀 Features

- Introduce `MetricReader` for iterating metrics from any text-IO source (#41)
- Add an `encoding` kwarg on `MetricReader.open` and `MetricWriter.open` (#43)
- Transparent gzip/bz2/xz support via `xopen` (#44)

## [0.3.0] - 2026-05-12

### 🚀 Features

- Expose `fieldnames` arg in `Metric.read` (#38)

### 🐛 Bug Fixes

- Update repository URLs to fg-labs after org transfer (#32)

### 📚 Documentation

- Add Fulcrum Genomics branding to README (#33)

## [0.2.0] - 2026-03-13

### 🐛 Bug Fixes

- Fix file handle leak in MetricWriter.__init__ (#24)
- Use JSON mode for model serialization in MetricWriter (#25)
- Specify UTF-8 encoding when opening output files (#26)
- Shallow copy input dict in `_empty_field_to_none` validator (#28)

### 🚜 Refactor

- Improve error messages in CounterPivotTable and DelimitedList (#27)
- Modernize type annotations (#29)

### 📚 Documentation

- Add examples to docstrings (#30)

## [0.1.0] - 2026-01-22

### 🚀 Features

- Metric and MetricWriter (#6)
- Benchmarking (#7)
- Typing helpers (#2)
- Delimited lists (#1)
- CounterPivotTable (#3)

### 🚜 Refactor

- Minor cleanups (#11)

### 📚 Documentation

- Update README (#14)

### ⚙️ Miscellaneous Tasks

- Publish workflow (#13)
- Clean up toolkit and add updates from template (#5)
- Configure pre-push hook (#12)
