# Illumina trio — sourced by generate.sh (uses its $RUN/$M/$A/$L, run(), emit()).
#
# These three tools read sequencer run-folder data that can't be synthesized, so the
# inputs are acquired from broadinstitute/picard test resources via a sparse checkout.
# CollectIlluminaLaneMetrics also has a committed expected output in that repo, so its
# example's metric values can be diffed against Picard's own (see docs).

TD=build/picard-testdata/testdata/picard/illumina

if [[ ! -d $TD/IlluminaLaneMetricsCollectorTest/tileRuns/H7BATADXX ]]; then
  echo "  fetching Picard Illumina testdata (sparse checkout)…"
  rm -rf build/picard-testdata
  git clone --no-checkout --depth 1 --filter=blob:none \
    https://github.com/broadinstitute/picard.git build/picard-testdata >/dev/null 2>&1
  (
    cd build/picard-testdata || exit 1
    git sparse-checkout init --cone >/dev/null 2>&1
    git sparse-checkout set \
      testdata/picard/illumina/IlluminaLaneMetricsCollectorTest/tileRuns/H7BATADXX \
      testdata/picard/illumina/CollectIlluminaBasecallingMetrics/25T8B25T \
      testdata/picard/illumina/25T8B8B25T_hiseqx >/dev/null 2>&1
    git checkout master >/dev/null 2>&1
  )
fi

mkdir -p "$M/illuminaLane"
# RUN_DIRECTORY = RunInfo.xml + InterOp/TileMetricsOut.bin (read structure derived from RunInfo)
run CollectIlluminaLaneMetrics \
  RUN_DIRECTORY="$TD/IlluminaLaneMetricsCollectorTest/tileRuns/H7BATADXX" \
  OUTPUT_DIRECTORY="$M/illuminaLane" OUTPUT_PREFIX=CollectIlluminaLaneMetrics \
  && emit CollectIlluminaLaneMetrics \
       "$M/illuminaLane/CollectIlluminaLaneMetrics.illumina_lane_metrics"

run CollectIlluminaBasecallingMetrics \
  BASECALLS_DIR="$TD/CollectIlluminaBasecallingMetrics/25T8B25T/Data/Intensities/BaseCalls" \
  LANE=1 READ_STRUCTURE=25T8B25T \
  INPUT="$TD/CollectIlluminaBasecallingMetrics/25T8B25T/Data/Intensities/BaseCalls/barcodeData.1" \
  OUTPUT="$M/CollectIlluminaBasecallingMetrics" \
  && emit CollectIlluminaBasecallingMetrics "$M/CollectIlluminaBasecallingMetrics"

run CollectHiSeqXPfFailMetrics \
  BASECALLS_DIR="$TD/25T8B8B25T_hiseqx/Data/Intensities/BaseCalls" \
  LANE=1 OUTPUT="$M/hiseqx" \
  && emit CollectHiSeqXPfFailMetrics "$M/hiseqx.pffail_summary_metrics"
