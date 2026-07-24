#!/usr/bin/env bash
#
# End-to-end generation of example Picard outputs for fgmetric.
#
# Produces one `assets/example.{PicardTool}` file per metrics-producing Picard tool.
# Inputs are built deterministically from a tiny synthetic reference (see
# make_inputs.py) so the whole thing is reproducible; the 3 Illumina tools depend on
# acquired run-folder fixtures and are handled by run_illumina.sh (sourced if present).
#
# Run from anywhere:  bash assets/generate/generate.sh
# Requires the pixi toolchain (see pixi.toml).

set -uo pipefail
cd "$(dirname "$0")/../.."  # repo root

RUN="pixi run"
B=build
M=$B/metrics
L=$B/logs
A=assets
mkdir -p "$M" "$L" "$A"

# --- Inputs ------------------------------------------------------------------
uv run --script assets/generate/make_inputs.py "$B"
$RUN samtools faidx "$B/ref.fasta"
rm -f "$B/ref.dict"
$RUN picard CreateSequenceDictionary R="$B/ref.fasta" O="$B/ref.dict" QUIET=true 2>/dev/null
$RUN samtools sort -o "$B/example.bam" "$B/reads.sam"
$RUN samtools index "$B/example.bam"
for k in baits targets amplicons rrna; do
  cat "$B/ref.dict" "$B/inputs/$k.body" > "$B/inputs/$k.interval_list"
done
for v in dbsnp calls truth; do
  $RUN bgzip -f -c "$B/inputs/$v.vcf" > "$B/inputs/$v.vcf.gz"
  $RUN tabix -f -p vcf "$B/inputs/$v.vcf.gz"
done
$RUN picard FixMateInformation I="$B/example.bam" O="$B/mc.bam" \
  ADD_MATE_CIGAR=true SORT_ORDER=coordinate QUIET=true 2>/dev/null
$RUN samtools index "$B/mc.bam"
# Dup-marked BAM, created up front so CollectJumpingLibraryMetrics can consume it
# (its metrics asset is emitted in the duplicates section below).
$RUN picard MarkDuplicates I="$B/example.bam" O="$B/markdup.bam" \
  M="$M/MarkDuplicates" QUIET=true 2>/dev/null
$RUN samtools index "$B/markdup.bam"

# Shorthand for inputs
REF=$B/ref.fasta;     BAM=$B/example.bam;   MCBAM=$B/mc.bam;   DICT=$B/ref.dict
BAITS=$B/inputs/baits.interval_list;        TARGETS=$B/inputs/targets.interval_list
AMPLICONS=$B/inputs/amplicons.interval_list; RRNA=$B/inputs/rrna.interval_list
REFFLAT=$B/inputs/refFlat.txt
DBSNP=$B/inputs/dbsnp.vcf.gz; CALLS=$B/inputs/calls.vcf.gz; TRUTH=$B/inputs/truth.vcf.gz

PASS=(); FAIL=()
# run TOOL -- picard-args...   (runs the tool, logs to build/logs/TOOL.log)
run() {
  local tool=$1; shift
  if $RUN picard "$tool" "$@" QUIET=true >"$L/$tool.log" 2>&1; then return 0
  else echo "  ! $tool failed (see $L/$tool.log)"; FAIL+=("$tool"); return 1; fi
}
# emit TOOL SRC   (copy produced file SRC to assets/example.TOOL)
emit() {
  local tool=$1 src=$2
  if [[ -f $src ]]; then cp "$src" "$A/example.$tool"; PASS+=("$tool")
  else echo "  ! $tool produced no output ($src)"; FAIL+=("$tool"); fi
}

echo "== alignment / read QC =="
run CollectAlignmentSummaryMetrics I="$BAM" O="$M/CollectAlignmentSummaryMetrics" R="$REF" \
  && emit CollectAlignmentSummaryMetrics "$M/CollectAlignmentSummaryMetrics"
run CollectInsertSizeMetrics I="$BAM" O="$M/CollectInsertSizeMetrics" H="$M/is.pdf" \
  && emit CollectInsertSizeMetrics "$M/CollectInsertSizeMetrics"
run CollectBaseDistributionByCycle I="$BAM" O="$M/CollectBaseDistributionByCycle" CHART="$M/bd.pdf" \
  && emit CollectBaseDistributionByCycle "$M/CollectBaseDistributionByCycle"
run CollectQualityYieldMetrics I="$BAM" O="$M/CollectQualityYieldMetrics" \
  && emit CollectQualityYieldMetrics "$M/CollectQualityYieldMetrics"
run MeanQualityByCycle I="$BAM" O="$M/MeanQualityByCycle" CHART="$M/mq.pdf" \
  && emit MeanQualityByCycle "$M/MeanQualityByCycle"
run QualityScoreDistribution I="$BAM" O="$M/QualityScoreDistribution" CHART="$M/qs.pdf" \
  && emit QualityScoreDistribution "$M/QualityScoreDistribution"
run CollectJumpingLibraryMetrics I="$B/markdup.bam" O="$M/CollectJumpingLibraryMetrics" \
  && emit CollectJumpingLibraryMetrics "$M/CollectJumpingLibraryMetrics"
run CalculateReadGroupChecksum I="$BAM" O="$M/CalculateReadGroupChecksum" \
  && emit CalculateReadGroupChecksum "$M/CalculateReadGroupChecksum"
run CollectMultipleMetrics I="$BAM" O="$M/multiple" R="$REF" \
  && emit CollectMultipleMetrics "$M/multiple.alignment_summary_metrics"

echo "== duplicates =="
# MarkDuplicates also yields the dup-marked BAM used by CollectJumpingLibraryMetrics.
run MarkDuplicates I="$BAM" O="$B/markdup.bam" M="$M/MarkDuplicates" \
  && emit MarkDuplicates "$M/MarkDuplicates"
$RUN samtools index "$B/markdup.bam" 2>/dev/null
run MarkDuplicatesWithMateCigar I="$MCBAM" O="$B/mdmc.bam" M="$M/MarkDuplicatesWithMateCigar" \
  && emit MarkDuplicatesWithMateCigar "$M/MarkDuplicatesWithMateCigar"
run UmiAwareMarkDuplicatesWithMateCigar I="$MCBAM" O="$B/umi.bam" \
  M="$M/UmiAwareMarkDuplicatesWithMateCigar" UMI_METRICS="$M/umi.umi_metrics" \
  && emit UmiAwareMarkDuplicatesWithMateCigar "$M/UmiAwareMarkDuplicatesWithMateCigar"
run EstimateLibraryComplexity I="$BAM" O="$M/EstimateLibraryComplexity" \
  && emit EstimateLibraryComplexity "$M/EstimateLibraryComplexity"

echo "== coverage / artifact =="
run CollectGcBiasMetrics I="$BAM" O="$M/gc.detail" S="$M/gc.summary" CHART="$M/gc.pdf" R="$REF" \
  && emit CollectGcBiasMetrics "$M/gc.summary"
run CollectWgsMetrics I="$BAM" O="$M/CollectWgsMetrics" R="$REF" \
  && emit CollectWgsMetrics "$M/CollectWgsMetrics"
# COVERAGE_CAP capped well below the RawWgs default (100000) so the example's coverage
# histogram isn't ~100k zero-padded rows; still exercises the RawWgs metric defaults.
run CollectRawWgsMetrics I="$BAM" O="$M/CollectRawWgsMetrics" R="$REF" COVERAGE_CAP=1000 \
  && emit CollectRawWgsMetrics "$M/CollectRawWgsMetrics"
run CollectWgsMetricsWithNonZeroCoverage I="$BAM" O="$M/CollectWgsMetricsWithNonZeroCoverage" \
  CHART="$M/wgsnz.pdf" R="$REF" \
  && emit CollectWgsMetricsWithNonZeroCoverage "$M/CollectWgsMetricsWithNonZeroCoverage"
run CollectOxoGMetrics I="$BAM" O="$M/CollectOxoGMetrics" R="$REF" \
  && emit CollectOxoGMetrics "$M/CollectOxoGMetrics"
run CollectSequencingArtifactMetrics I="$BAM" O="$M/artifact" R="$REF" \
  && emit CollectSequencingArtifactMetrics "$M/artifact.pre_adapter_summary_metrics"
run CollectRrbsMetrics I="$BAM" R="$REF" M="$M/rrbs" \
  && emit CollectRrbsMetrics "$M/rrbs.rrbs_summary_metrics"

echo "== targeted / RNA =="
run CollectHsMetrics I="$BAM" O="$M/CollectHsMetrics" BAIT_INTERVALS="$BAITS" \
  TARGET_INTERVALS="$TARGETS" R="$REF" \
  && emit CollectHsMetrics "$M/CollectHsMetrics"
run CollectTargetedPcrMetrics I="$BAM" O="$M/CollectTargetedPcrMetrics" \
  AMPLICON_INTERVALS="$AMPLICONS" TARGET_INTERVALS="$TARGETS" R="$REF" \
  && emit CollectTargetedPcrMetrics "$M/CollectTargetedPcrMetrics"
run CollectRnaSeqMetrics I="$BAM" O="$M/CollectRnaSeqMetrics" REF_FLAT="$REFFLAT" \
  RIBOSOMAL_INTERVALS="$RRNA" STRAND_SPECIFICITY=NONE R="$REF" \
  && emit CollectRnaSeqMetrics "$M/CollectRnaSeqMetrics"

echo "== variant =="
run CollectVariantCallingMetrics I="$CALLS" DBSNP="$DBSNP" O="$M/vc" SD="$DICT" \
  && emit CollectVariantCallingMetrics "$M/vc.variant_calling_summary_metrics"
run GenotypeConcordance TRUTH_VCF="$TRUTH" CALL_VCF="$CALLS" O="$M/gtc" \
  && emit GenotypeConcordance "$M/gtc.genotype_concordance_summary_metrics"

echo "== compare =="
# CompareMetrics consumes two existing metrics files; compare the alignment summary
# from the raw vs the dup-marked BAM and capture the comparison report.
$RUN picard CollectAlignmentSummaryMetrics I="$B/markdup.bam" O="$M/asm_markdup" R="$REF" \
  QUIET=true >"$L/asm_markdup.log" 2>&1
run CompareMetrics INPUT="$M/CollectAlignmentSummaryMetrics" INPUT="$M/asm_markdup" \
  OUTPUT="$M/CompareMetrics" \
  && emit CompareMetrics "$M/CompareMetrics"

# --- Illumina trio (acquired fixtures) ---------------------------------------
if [[ -f assets/generate/run_illumina.sh ]]; then
  echo "== illumina =="
  # shellcheck disable=SC1091
  source assets/generate/run_illumina.sh
fi

echo
echo "PASS (${#PASS[@]}): ${PASS[*]}"
echo "FAIL (${#FAIL[@]}): ${FAIL[*]}"
