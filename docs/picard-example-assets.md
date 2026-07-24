# Picard example assets — scope & build plan

Status: **complete — 29/29 assets generated and verified** · Date: 2026-06-09

## Goal

Provide one example Picard output file per metrics-producing Picard tool, under a new
top-level `assets/` directory, named `assets/example.{PicardTool}` (the tool name is the
file "extension", e.g. `assets/example.CollectInsertSizeMetrics`). These serve as real,
on-disk fixtures/examples for `fgmetric`, which parses delimited metrics files.

Outputs are produced by **running Picard locally** (chosen approach: option 4) on a small,
internally-consistent set of inputs. Where producing an input is disproportionately
expensive (Illumina run folders, bisulfite/UMI BAMs), the input is **acquired** from
Picard/htsjdk test resources rather than fabricated — a hybrid keyed off this scope.

## Tools in scope (29)

Metrics-producing tools, grouped as researched against the Picard source:

| Group | Tools |
|---|---|
| Alignment / read QC | `CollectAlignmentSummaryMetrics`, `CollectInsertSizeMetrics`, `CollectBaseDistributionByCycle`, `CollectQualityYieldMetrics`, `MeanQualityByCycle`, `QualityScoreDistribution`, `CollectJumpingLibraryMetrics`, `CalculateReadGroupChecksum`, `CollectMultipleMetrics` |
| Coverage / artifact | `CollectGcBiasMetrics`, `CollectWgsMetrics`, `CollectRawWgsMetrics`, `CollectWgsMetricsWithNonZeroCoverage`, `CollectOxoGMetrics`, `CollectSequencingArtifactMetrics`, `CollectRrbsMetrics` |
| Targeted / RNA / duplicates | `CollectHsMetrics`, `CollectTargetedPcrMetrics`, `CollectRnaSeqMetrics`, `MarkDuplicates`, `MarkDuplicatesWithMateCigar`, `UmiAwareMarkDuplicatesWithMateCigar`, `EstimateLibraryComplexity` |
| Variant / Illumina / compare | `CollectVariantCallingMetrics`, `GenotypeConcordance`, `CollectIlluminaBasecallingMetrics`, `CollectIlluminaLaneMetrics`, `CollectHiSeqXPfFailMetrics`, `CompareMetrics` |

**Edge cases on the "is a metrics file" criterion** (kept in for completeness):
- `CalculateReadGroupChecksum` emits an `.md5` hash, not a Picard metrics table.
- `CompareMetrics` emits a diff / exit code, not a metrics file. It consumes two existing
  metrics files (free once other tools have run).
- `GenotypeConcordance` does emit `.genotype_concordance_*_metrics` files.

## Runtime prerequisites (via pixi)

A `pixi.toml` pins the toolchain (conda-forge / bioconda):

- `openjdk` (17+) — to run Picard.
- `picard` — pinned version; provides the `picard` CLI wrapper.
- `r-base` — **required** for the three tools whose `CHART_OUTPUT` arg is mandatory
  (`CollectBaseDistributionByCycle`, `MeanQualityByCycle`, `QualityScoreDistribution`) and
  for optional charts elsewhere. Picard's chart R scripts run under base R.
- `samtools` + `htslib` — sort/index/faidx BAMs and bgzip/tabix the VCFs.
- `bcftools`, `minimap2` — available in the env for generator variants; the current
  generator emits reads as **pre-placed alignments** (see `make_inputs.py`), so no aligner
  or read-simulator step is required.

`.pixi/` is git-ignored; `pixi.toml` + `pixi.lock` are committed for reproducibility.

## The complete input set (union — sourcing decided)

| # | Artifact | Format | Sourcing | Consumed by |
|---|---|---|---|---|
| 1 | Reference bundle | `ref.fasta` + `.fai` + `.dict` | **synthesize** (tiny multi-contig genome) | required by Wgs×3, OxoG, SeqArtifact, Rrbs; required-in-practice by GcBias; optional-recommended for ~8 more; CRAM |
| 2 | Standard aligned BAM | coord-sorted, indexed, RG, paired, dups present | **synthesize** (pre-placed SAM → sort/index) | ~18 tools (workhorse) |
| 3 | Dup-marked BAM | #2 after `MarkDuplicates` | derive | `CollectJumpingLibraryMetrics` |
| 4 | MC-tagged BAM | coord-sorted + `MC` tag | derive (`FixMateInformation`) | `MarkDuplicatesWithMateCigar` |
| 5 | UMI+MC BAM | #4 + `RX` tag | `RX` emitted on all reads by the simulator, so **#5 == #4** (local) | `UmiAwareMarkDuplicatesWithMateCigar` |
| 6 | RNA-aligned BAM | reads over transcripts | reuse #2 vs refFlat on same ref | `CollectRnaSeqMetrics` |
| 7 | RRBS BAM | coord-sorted | **reuse #2** — run on the workhorse BAM (non-bisulfite → valid format, ~0% conversion) | `CollectRrbsMetrics` |
| 8 | Bait interval_list | Picard `.interval_list` w/ #1 `@SQ` | author | `CollectHsMetrics` (req) |
| 9 | Target interval_list | `.interval_list` | author | `CollectHsMetrics` (req), `CollectTargetedPcrMetrics` (req) |
| 10 | Amplicon interval_list | `.interval_list` | author | `CollectTargetedPcrMetrics` (req) |
| 11 | refFlat | UCSC refFlat for #1 | author | `CollectRnaSeqMetrics` (req) |
| 12 | rRNA interval_list | `.interval_list` | author | `CollectRnaSeqMetrics` (optional, for meaningful rRNA%) |
| 13 | dbSNP VCF | `.vcf.gz` + `.tbi` matching #1 dict | author (bcftools) | `CollectVariantCallingMetrics` (req); optional OxoG/SeqArtifact |
| 14 | Call VCF | `.vcf.gz` + index | author | `CollectVariantCallingMetrics` (INPUT), `GenotypeConcordance` (CALL_VCF) |
| 15 | Truth VCF | `.vcf.gz` + index | author | `GenotypeConcordance` (TRUTH_VCF) |
| 16 | Illumina run folder | BaseCalls (BCL/CBCL + locs + filter), `RunInfo.xml`, `InterOp/`, barcode files | **acquire** (Picard testdata) | the 3 Illumina tools |

`CompareMetrics` consumes two metrics files produced above — no new input.

## Per-tool input / output matrix

Required file inputs (R = `REFERENCE_SEQUENCE`); "example" = which output file becomes
`assets/example.{Tool}` when a tool emits several.

| Tool | Required inputs | Example output file | Notes |
|---|---|---|---|
| CollectAlignmentSummaryMetrics | #2 (+R recommended) | the metrics table | R unlocks full metric set |
| CollectInsertSizeMetrics | #2 | the metrics table | paired reads; chart optional |
| CollectBaseDistributionByCycle | #2 + CHART | the metrics table | CHART **required** → needs R |
| CollectQualityYieldMetrics | #2 | the metrics table | |
| MeanQualityByCycle | #2 + CHART | the metrics table | CHART **required** → needs R |
| QualityScoreDistribution | #2 + CHART | the metrics table | CHART **required** → needs R |
| CollectJumpingLibraryMetrics | #3 (dups marked) | the metrics table | uses duplicate flag |
| CalculateReadGroupChecksum | #2 | the `.read_group_md5` | not a metrics table |
| CollectMultipleMetrics | #2 (+R) | alignment_summary_metrics (representative) | wrapper; emits several — see risks |
| CollectGcBiasMetrics | #2 + R | summary metrics table | also detail + chart; R runtime-required |
| CollectWgsMetrics | #2 + R | the metrics table | |
| CollectRawWgsMetrics | #2 + R | the metrics table | `COVERAGE_CAP=1000` (see results) |
| CollectWgsMetricsWithNonZeroCoverage | #2 + R | the metrics table | chart optional |
| CollectOxoGMetrics | #2 + R | the metrics table | DB_SNP optional |
| CollectSequencingArtifactMetrics | #2 + R | pre_adapter_summary_metrics (representative) | emits 5 files |
| CollectRrbsMetrics | #2 + R | rrbs_summary_metrics | run on workhorse BAM (non-bisulfite) |
| CollectHsMetrics | #2 + #8 + #9 (+R) | the metrics table | both bait & target required |
| CollectTargetedPcrMetrics | #2 + #10 + #9 (+R) | the metrics table | both amplicon & target required |
| CollectRnaSeqMetrics | #6 + #11 (+#12) | the metrics table | REF_FLAT required |
| MarkDuplicates | #2 | the METRICS_FILE | also writes a BAM |
| MarkDuplicatesWithMateCigar | #4 (MC tag) | the METRICS_FILE | coord-sorted + MC required |
| UmiAwareMarkDuplicatesWithMateCigar | #5 (MC + RX) | the METRICS_FILE | + UMI metrics file |
| EstimateLibraryComplexity | #2 | the metrics table | no alignment needed |
| CollectVariantCallingMetrics | #14 + #13 (+dict) | summary metrics (representative) | detail + summary |
| GenotypeConcordance | #15 + #14 | summary metrics (representative) | 3 metrics files |
| CollectIlluminaBasecallingMetrics | #16 (+ ExtractIlluminaBarcodes pre-step) | the metrics file | acquired run folder |
| CollectIlluminaLaneMetrics | #16 (RunInfo + InterOp) | illumina_lane_metrics | acquired run folder |
| CollectHiSeqXPfFailMetrics | #16 (HiSeq X basecalls) | pffail_summary_metrics | acquired run folder |
| CompareMetrics | two metrics files from above | comparison output | not a metrics table |

## Build pipeline

1. **Toolchain** — `pixi init` + add packages above; `pixi install`.
2. **Reference** — write a small synthetic FASTA; `samtools faidx`; `picard CreateSequenceDictionary`.
3. **Reads → workhorse BAM (#2)** — `make_inputs.py` emits a SAM of FR pairs with correct
   coordinates/flags/TLEN, per-cycle qualities, a 0.4% substitution rate, `NM`/`MD`/`RX`
   tags, and ~8% injected PCR duplicates; `samtools sort`/`index`.
4. **Derived BAMs** — `MarkDuplicates` (#3), `FixMateInformation` adds `MC` (#4); the `RX`
   tags already present make #4 double as the UMI input (#5).
5. **Text inputs** — interval_lists (#8–#10, #12), refFlat (#11), and VCFs (#13–#15) emitted by
   `make_inputs.py` on the reference's coordinate system; interval headers come from `ref.dict`.
6. **Acquire Illumina inputs** — `run_illumina.sh` sparse-checks-out three small fixtures from
   broadinstitute/picard testdata (lane-metrics run dir, basecalling BCL subtree, HiSeqX BCL
   subtree). RRBS/UMI need no acquisition (see #5, #7).
7. **Run tools** — `generate.sh` invokes each tool; copies its principal output to
   `assets/example.{Tool}`; prints a PASS/FAIL summary.
8. **Verify** — `verify_assets.py` confirms each `assets/example.*` exists, is non-empty, and
   has the expected structure, and round-trips one Picard table through `fgmetric.MetricReader`.

## Repo layout

```
assets/                      # deliverable: 29 example.{Tool} files (committed)
  example.CollectAlignmentSummaryMetrics
  ...
assets/generate/             # build infrastructure (committed)
  make_inputs.py             # deterministic reference, reads (pre-placed SAM), intervals, refFlat, VCFs
  generate.sh                # end-to-end: inputs → BAMs → run the 26 self-contained tools → assets
  run_illumina.sh            # sourced by generate.sh: sparse-checkout fixtures + run the 3 Illumina tools
  verify_assets.py           # structural validation of all 29 + an fgmetric round-trip
build/                       # intermediates: ref, BAMs, metrics, picard-testdata (git-ignored)
pixi.toml, pixi.lock         # toolchain (committed)
```

## Gating risks — how each was resolved

- **Illumina trio** — resolved by running all three locally on small fixtures sparse-checked-out
  from Picard testdata. `CollectHiSeqXPfFailMetrics` needs only `BASECALLS_DIR`+`LANE`+`OUTPUT`
  (no `RunInfo.xml`). `CollectIlluminaLaneMetrics`'s metric values match Picard's committed
  expected output exactly (only the provenance/command-line header differs).
- **RRBS / UMI** — resolved without acquisition: `CollectRrbsMetrics` runs on the workhorse BAM
  (valid format, ~0% conversion since the data isn't bisulfite); the UMI input is the MC BAM
  whose reads already carry simulator-emitted `RX` tags.
- **Charts require R** — `r-base` from pixi satisfied the three hard-`CHART_OUTPUT` tools and the
  optional charts; all chart-producing tools succeeded.
- **Multi-output tools** — representative output fixed per the matrix above (e.g. GcBias →
  summary, SequencingArtifact → `pre_adapter_summary_metrics`).
- **Edge-case tools** — `CalculateReadGroupChecksum` (md5) and `CompareMetrics` (comparison
  report) ship their real, non-metrics output.

## Results

29/29 tools produced a valid `assets/example.{Tool}`; `verify_assets.py` passes and parses a
Picard `WgsMetrics` table via `fgmetric` (`GENOME_TERRITORY=30000`, `MEAN_COVERAGE=72.1`).

- **Numbers are internally consistent**: 30 kb reference → `GENOME_TERRITORY=30000`; injected
  0.4% substitutions → `PF_MISMATCH_RATE≈0.004`; ~8% injected PCR duplicates →
  `PERCENT_DUPLICATION≈0.076`.
- **`CollectRawWgsMetrics`** was run with `COVERAGE_CAP=1000` instead of the RawWgs default
  (100000), which would otherwise zero-pad the coverage histogram to ~100k rows (790 KB);
  the capped example is ~7.5 KB and still exercises the RawWgs metric defaults.
- **Provenance**: file sizes are small (largest non-RawWgs asset ~10 KB); all values derive
  from synthetic data except the three Illumina tools, which run on real Picard test fixtures.

To regenerate: `bash assets/generate/generate.sh && uv run python assets/generate/verify_assets.py`.
