---
date: 2026-02-17
repository: fgmetric
repository_url: https://github.com/fulcrumgenomics/fgmetric
source_review: ../reviews/review_2026-02-17_fgmetric.md
priority_counts:
  HIGH: 0
  MEDIUM: 2
  LOW: 2
status: created
---

# Issues from Expert Review (2026-02-17)

## Summary

| ID | Title | Priority | Labels | Status |
| :- | :---- | :------- | :----- | :----: |
| ISS-001 | Fix potential file handle leak in MetricWriter.__init__ | Medium | `bug`, `good first issue` | [ ] |
| ISS-002 | Expand MetricWriter test coverage | Medium | `testing`, `enhancement` | [ ] |
| ISS-003 | Add read/write roundtrip tests | Low | `testing`, `enhancement` | [ ] |
| ISS-004 | Create initial CHANGELOG.md | Low | `documentation` | [ ] |

---

## ISS-001: Fix potential file handle leak in MetricWriter.__init__

**GitHub Issue:** [#17](https://github.com/fulcrumgenomics/fgmetric/issues/17)
**Priority:** Medium
**Labels:** `bug`, `good first issue`

### Description

In `MetricWriter.__init__()`, the file is opened on line 65 before `DictWriter` is constructed (line 67) and `writeheader()` is called (line 74). If either of those calls raises an exception, the file handle stored in `self._fout` will never be closed.

**Review evidence:** Identified in [Edge Cases and Undefined Behavior](../reviews/review_2026-02-17_fgmetric.md#edge-cases-and-undefined-behavior).

```python
# metric_writer.py:64-74
self._fout = Path(filename).open("w")

self._writer = DictWriter(
    f=self._fout,
    fieldnames=self._metric_class._header_fieldnames(),
    delimiter=delimiter,
    lineterminator=lineterminator,
)

self._writer.writeheader()
```

If `_header_fieldnames()` or `writeheader()` raises, `_fout` is open but never closed.

### Acceptance Criteria

- [ ] `MetricWriter.__init__` closes file handle on failure via try/except
- [ ] Test added verifying file is closed when init raises
- [ ] All existing tests still pass

### Notes

Suggested fix -- wrap post-open logic in try/except:

```python
self._fout = Path(filename).open("w")
try:
    self._writer = DictWriter(
        f=self._fout,
        fieldnames=self._metric_class._header_fieldnames(),
        delimiter=delimiter,
        lineterminator=lineterminator,
    )
    self._writer.writeheader()
except Exception:
    self._fout.close()
    raise
```

**Files:** `fgmetric/metric_writer.py:64-74`

---

## ISS-002: Expand MetricWriter test coverage

**GitHub Issue:** [#18](https://github.com/fulcrumgenomics/fgmetric/issues/18)
**Priority:** Medium
**Labels:** `testing`, `enhancement`

### Description

`MetricWriter` currently has only 1 test (`test_writer` in `tests/test_metric_writer.py`). This covers basic write with the default tab delimiter but leaves several code paths untested.

**Review evidence:** Identified in [Testing for Software Correctness](../reviews/review_2026-02-17_fgmetric.md#testing-for-software-correctness).

### Acceptance Criteria

- [ ] Test for writing with custom delimiter (`delimiter=","`)
- [ ] Test for `writeall()` method standalone
- [ ] Test for writing metrics with field aliases (`Field(alias=...)`)
- [ ] Test for writing metrics with `Counter[StrEnum]` fields (pivot columns in output)
- [ ] Test for `close()` behavior (file handle actually closed)
- [ ] Test for context manager exception handling (file closed on error)

### Notes

**Files:** `tests/test_metric_writer.py`

---

## ISS-003: Add read/write roundtrip tests

**GitHub Issue:** [#19](https://github.com/fulcrumgenomics/fgmetric/issues/19)
**Priority:** Low
**Labels:** `testing`, `enhancement`

### Description

There are no end-to-end roundtrip tests that write metrics to a file with `MetricWriter` and then read them back with `Metric.read()` to verify the data survives the full cycle. While individual read and write tests exist, a roundtrip test would catch serialization/deserialization mismatches.

**Review evidence:** Identified in [Testing for Software Correctness](../reviews/review_2026-02-17_fgmetric.md#testing-for-software-correctness).

### Acceptance Criteria

- [ ] Roundtrip test for simple metric (str + int fields)
- [ ] Roundtrip test for metrics with Optional fields (None preserved)
- [ ] Roundtrip test for metrics with `list[int]` fields
- [ ] Roundtrip test for metrics with `Counter[StrEnum]` fields
- [ ] Roundtrip test for empty file (header only, zero rows)

### Notes

Could live in `tests/test_metric_writer.py` or a new `tests/test_roundtrip.py`.

---

## ISS-004: Create initial CHANGELOG.md

**GitHub Issue:** [#20](https://github.com/fulcrumgenomics/fgmetric/issues/20)
**Priority:** Low
**Labels:** `documentation`

### Description

The repository has no `CHANGELOG.md` despite:
- The publish workflow generating changelogs with git-cliff (`publish.yml:125-145`)
- The CLAUDE.md referencing CHANGELOG.md updates as part of the documentation maintenance checklist

**Review evidence:** Identified in [Software Durability](../reviews/review_2026-02-17_fgmetric.md#software-durability).

### Acceptance Criteria

- [ ] `CHANGELOG.md` exists at repository root
- [ ] Contains entry for 0.1.0 release
- [ ] Format is compatible with git-cliff's expected structure

### Notes

Suggested content:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2025-XX-XX

Initial release.

- `Metric` base class for type-validated delimited file models
- `MetricWriter` context manager for writing metrics to files
- Delimited list support (`list[T]` fields)
- Counter pivot table support (`Counter[StrEnum]` fields)
- Empty field handling (empty string -> None for Optional fields)
- UTF-8 BOM handling
```

**Files:** `CHANGELOG.md` (new file)

---

## Completion Log

| ID | Date Resolved | Resolution | PR/Commit |
| :- | :------------ | :--------- | :-------- |
| | | | |
