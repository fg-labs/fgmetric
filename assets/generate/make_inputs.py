# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Generate a small, self-consistent set of inputs for running Picard metrics tools.

Everything is derived deterministically (fixed RNG seed) from a tiny synthetic
reference so that the reference, reads, interval lists, refFlat, and VCFs all share
one coordinate system. Reads are emitted as a SAM with correct coordinates, flags,
TLEN, and NM/MD/RX tags (the reads are exact reference substrings plus a low
substitution rate), so no aligner is needed and alignments are clean.

Outputs (under the given output directory):
    ref.fasta                      synthetic reference (2 contigs)
    reads.sam                      unsorted SAM of FR paired reads
    inputs/baits.body              interval_list body lines (no header)
    inputs/targets.body
    inputs/amplicons.body
    inputs/rrna.body
    inputs/refFlat.txt             UCSC refFlat gene annotations
    inputs/dbsnp.vcf               sites-only dbSNP VCF
    inputs/calls.vcf               single-sample call VCF
    inputs/truth.vcf               single-sample truth VCF

The interval_list `.body` files carry only the interval lines; the build script
prepends the reference sequence dictionary (`ref.dict`) to form valid interval lists.
"""

import random
import sys
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path

SEED = 42
READ_LEN = 100
N_FRAGMENTS = 10_000
FRAG_MEAN = 300
FRAG_SD = 30
FRAG_MIN = 150
FRAG_MAX = 500
SUB_RATE = 0.004
UMI_POOL = ("AACCGG", "TTGGCC", "ACGTAC", "GGTTAA", "CCAATT", "TGCATG", "GATTAC", "CTAGGT")
_COMPLEMENT = str.maketrans("ACGT", "TGCA")


@dataclass(frozen=True)
class Contig:
    """
    A reference contig.

    Args:
        name: Sequence name (SN).
        length: Sequence length in bases (LN).
    """

    name: str
    length: int


CONTIGS = (Contig("chr1", 20_000), Contig("chr2", 10_000))


def revcomp(seq: str) -> str:
    """
    Return the reverse complement of a DNA sequence.

    Args:
        seq: A DNA sequence over the alphabet ACGT.

    Returns:
        The reverse-complemented sequence.
    """
    return seq.translate(_COMPLEMENT)[::-1]


def make_reference(rng: random.Random) -> dict[str, str]:
    """
    Build a deterministic synthetic reference.

    Args:
        rng: Seeded random generator.

    Returns:
        Mapping of contig name to its sequence.
    """
    bases = "ACGT"
    return {c.name: "".join(rng.choice(bases) for _ in range(c.length)) for c in CONTIGS}


def write_fasta(reference: dict[str, str], path: Path, width: int = 70) -> None:
    """
    Write a reference mapping to a FASTA file.

    Args:
        reference: Mapping of contig name to sequence.
        path: Destination FASTA path.
        width: Line wrap width.
    """
    with path.open("w") as fh:
        for name, seq in reference.items():
            fh.write(f">{name}\n")
            for i in range(0, len(seq), width):
                fh.write(seq[i : i + width] + "\n")


def mutate(segment: str, rng: random.Random) -> str:
    """
    Apply a low per-base substitution rate to a reference segment.

    Args:
        segment: The reference segment (forward strand) the read derives from.
        rng: Seeded random generator.

    Returns:
        The read sequence with occasional substitutions.
    """
    out: list[str] = []
    for ref_base in segment:
        if rng.random() < SUB_RATE:
            out.append(rng.choice([b for b in "ACGT" if b != ref_base]))
        else:
            out.append(ref_base)
    return "".join(out)


def md_tag(ref_segment: str, read_segment: str) -> tuple[str, int]:
    """
    Compute the MD tag and edit distance for an ungapped (all-M) alignment.

    Args:
        ref_segment: Reference bases spanned by the read.
        read_segment: Read bases (forward-strand representation).

    Returns:
        A tuple of (MD string, NM edit distance).
    """
    md: list[str] = []
    run = 0
    nm = 0
    for ref_base, read_base in zip(ref_segment, read_segment, strict=True):
        if ref_base == read_base:
            run += 1
        else:
            md.append(str(run))
            md.append(ref_base)
            run = 0
            nm += 1
    md.append(str(run))
    return "".join(md), nm


def quality_string(length: int) -> str:
    """
    Build a per-cycle Phred+33 quality string that declines toward the 3' end.

    Args:
        length: Read length.

    Returns:
        A quality string of the requested length.
    """
    quals = []
    for cycle in range(length):
        q = max(28, 40 - cycle // 20)
        quals.append(chr(q + 33))
    return "".join(quals)


@dataclass(frozen=True)
class ReadPair:
    """A simulated FR read pair, ready to be emitted as two SAM lines."""

    name: str
    contig: str
    r1_pos: int
    r2_pos: int
    tlen: int
    r1_seq: str
    r2_seq: str
    r1_md: str
    r1_nm: int
    r2_md: str
    r2_nm: int
    umi: str


def simulate_pairs(reference: dict[str, str], rng: random.Random) -> list[ReadPair]:
    """
    Simulate FR paired reads as exact (mostly) reference substrings.

    Args:
        reference: Mapping of contig name to sequence.
        rng: Seeded random generator.

    Returns:
        A list of simulated read pairs.
    """
    weights = [len(reference[c.name]) for c in CONTIGS]
    pairs: list[ReadPair] = []
    for i in range(N_FRAGMENTS):
        contig = rng.choices(CONTIGS, weights=weights, k=1)[0]
        seq = reference[contig.name]
        frag_len = min(FRAG_MAX, max(FRAG_MIN, int(rng.gauss(FRAG_MEAN, FRAG_SD))))
        frag_len = min(frag_len, contig.length)
        start = rng.randint(0, contig.length - frag_len)
        r1_ref = seq[start : start + READ_LEN]
        s2 = start + frag_len - READ_LEN
        r2_ref = seq[s2 : s2 + READ_LEN]
        r1_seq = mutate(r1_ref, rng)
        r2_seq = mutate(r2_ref, rng)
        r1_md, r1_nm = md_tag(r1_ref, r1_seq)
        r2_md, r2_nm = md_tag(r2_ref, r2_seq)
        pairs.append(
            ReadPair(
                name=f"frag{i}",
                contig=contig.name,
                r1_pos=start + 1,
                r2_pos=s2 + 1,
                tlen=frag_len,
                r1_seq=r1_seq,
                r2_seq=r2_seq,
                r1_md=r1_md,
                r1_nm=r1_nm,
                r2_md=r2_md,
                r2_nm=r2_nm,
                umi=rng.choice(UMI_POOL),
            )
        )
    # Inject PCR duplicates: copy ~8% of fragments verbatim (same position and
    # sequence) under a new name, so both position-based (MarkDuplicates) and
    # sequence-based (EstimateLibraryComplexity) dedupe report a realistic rate.
    for p in list(pairs):
        if rng.random() < 0.08:
            pairs.append(replace(p, name=f"{p.name}_dup"))
    return pairs


def write_sam(pairs: list[ReadPair], path: Path) -> None:
    """
    Write simulated read pairs to an unsorted SAM file.

    Args:
        pairs: Simulated read pairs.
        path: Destination SAM path.
    """
    qual = quality_string(READ_LEN)
    cigar = f"{READ_LEN}M"
    with path.open("w") as fh:
        fh.write("@HD\tVN:1.6\tSO:unsorted\n")
        for c in CONTIGS:
            fh.write(f"@SQ\tSN:{c.name}\tLN:{c.length}\n")
        fh.write("@RG\tID:A\tSM:sample1\tLB:lib1\tPL:ILLUMINA\tPU:unit1\n")
        for p in pairs:
            # FLAG 99 = paired,proper,mate-reverse,first; 147 = paired,proper,reverse,second.
            fh.write(
                "\t".join([
                    p.name,
                    "99",
                    p.contig,
                    str(p.r1_pos),
                    "60",
                    cigar,
                    "=",
                    str(p.r2_pos),
                    str(p.tlen),
                    p.r1_seq,
                    qual,
                    "RG:Z:A",
                    f"NM:i:{p.r1_nm}",
                    f"MD:Z:{p.r1_md}",
                    f"RX:Z:{p.umi}",
                ])
                + "\n"
            )
            fh.write(
                "\t".join([
                    p.name,
                    "147",
                    p.contig,
                    str(p.r2_pos),
                    "60",
                    cigar,
                    "=",
                    str(p.r1_pos),
                    str(-p.tlen),
                    p.r2_seq,
                    qual,
                    "RG:Z:A",
                    f"NM:i:{p.r2_nm}",
                    f"MD:Z:{p.r2_md}",
                    f"RX:Z:{p.umi}",
                ])
                + "\n"
            )


def write_interval_bodies(out: Path) -> None:
    """
    Write interval_list body lines (header is prepended later from ref.dict).

    Args:
        out: Directory to write the `.body` files into.
    """
    # chrom, start, end, strand, name  (1-based, inclusive).
    baits = [
        ("chr1", 1_000, 3_000, "baits_chr1_a"),
        ("chr1", 8_000, 10_000, "baits_chr1_b"),
        ("chr2", 2_000, 4_000, "baits_chr2_a"),
    ]
    # Targets sit inside the baits.
    targets = [
        ("chr1", 1_200, 2_800, "target_chr1_a"),
        ("chr1", 8_200, 9_800, "target_chr1_b"),
        ("chr2", 2_200, 3_800, "target_chr2_a"),
    ]
    rrna = [("chr2", 6_000, 6_500, "rRNA_chr2")]

    def fmt(rows: list[tuple[str, int, int, str]]) -> str:
        return "".join(f"{c}\t{s}\t{e}\t+\t{n}\n" for c, s, e, n in rows)

    (out / "baits.body").write_text(fmt(baits))
    (out / "targets.body").write_text(fmt(targets))
    (out / "amplicons.body").write_text(fmt(baits))  # amplicons reuse the bait spans
    (out / "rrna.body").write_text(fmt(rrna))


def write_refflat(out: Path) -> None:
    """
    Write a small UCSC refFlat with two genes (0-based, half-open coordinates).

    Args:
        out: Directory to write `refFlat.txt` into.
    """
    rows = [
        # geneName, name, chrom, strand, txStart, txEnd, cdsStart, cdsEnd,
        # exonCount, exonStarts, exonEnds
        ("GENE1", "NM_001", "chr1", "+", 1_000, 5_000, 1_100, 4_900, 2, "1000,3000,", "2000,5000,"),
        ("GENE2", "NM_002", "chr2", "-", 2_000, 4_000, 2_100, 3_900, 1, "2000,", "4000,"),
    ]
    lines = [
        "\t".join([g, n, c, st, str(ts), str(te), str(cs), str(ce), str(ec), es, ee])
        for g, n, c, st, ts, te, cs, ce, ec, es, ee in rows
    ]
    (out / "refFlat.txt").write_text("\n".join(lines) + "\n")


def _vcf_header(samples: tuple[str, ...]) -> str:
    """
    Build a VCF header for the synthetic reference.

    Args:
        samples: Sample names for the #CHROM line (empty for a sites-only VCF).

    Returns:
        The complete VCF header text including the column line.
    """
    lines = ["##fileformat=VCFv4.2"]
    for c in CONTIGS:
        lines.append(f"##contig=<ID={c.name},length={c.length}>")
    lines.append('##INFO=<ID=DB,Number=0,Type=Flag,Description="dbSNP membership">')
    lines.append('##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">')
    lines.append('##FORMAT=<ID=GQ,Number=1,Type=Integer,Description="Genotype Quality">')
    lines.append('##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read Depth">')
    cols = ["#CHROM", "POS", "ID", "REF", "ALT", "QUAL", "FILTER", "INFO"]
    if samples:
        cols += ["FORMAT", *samples]
    lines.append("\t".join(cols))
    return "\n".join(lines) + "\n"


def _variant_sites(
    reference: dict[str, str], rng: random.Random
) -> list[tuple[str, int, str, str]]:
    """
    Pick variant sites with REF matching the reference and a distinct ALT.

    Args:
        reference: Mapping of contig name to sequence.
        rng: Seeded random generator.

    Returns:
        A list of (chrom, pos1based, ref_base, alt_base) tuples, sorted by position.
    """
    sites: list[tuple[str, int, str, str]] = []
    for c in CONTIGS:
        seq = reference[c.name]
        positions = sorted(rng.sample(range(500, c.length - 500), 8))
        for pos0 in positions:
            ref_base = seq[pos0]
            alt = rng.choice([b for b in "ACGT" if b != ref_base])
            sites.append((c.name, pos0 + 1, ref_base, alt))
    return sites


def write_vcfs(reference: dict[str, str], out: Path, rng: random.Random) -> None:
    """
    Write sites-only dbSNP, single-sample call, and single-sample truth VCFs.

    Args:
        reference: Mapping of contig name to sequence.
        out: Directory to write the `.vcf` files into.
        rng: Seeded random generator.
    """
    sites = _variant_sites(reference, rng)

    # dbSNP: a sites-only VCF over a subset of the sites, with rs IDs.
    dbsnp_lines = [_vcf_header(())]
    for i, (chrom, pos, ref, alt) in enumerate(sites):
        if i % 3 != 0:  # ~2/3 of sites are "known"
            dbsnp_lines.append(f"{chrom}\t{pos}\trs{1000 + i}\t{ref}\t{alt}\t.\tPASS\tDB\n")
    (out / "dbsnp.vcf").write_text("".join(dbsnp_lines))

    # Call set: single sample with genotypes.
    call_lines = [_vcf_header(("call_sample",))]
    for chrom, pos, ref, alt in sites:
        gt = rng.choice(["0/1", "1/1"])
        call_lines.append(f"{chrom}\t{pos}\t.\t{ref}\t{alt}\t50\tPASS\t.\tGT:GQ:DP\t{gt}:50:30\n")
    (out / "calls.vcf").write_text("".join(call_lines))

    # Truth set: single sample, mostly concordant with the call set.
    truth_lines = [_vcf_header(("truth_sample",))]
    for i, (chrom, pos, ref, alt) in enumerate(sites):
        gt = rng.choice(["0/1", "1/1"]) if i % 5 == 0 else "0/1"
        truth_lines.append(f"{chrom}\t{pos}\t.\t{ref}\t{alt}\t50\tPASS\t.\tGT:GQ:DP\t{gt}:50:30\n")
    (out / "truth.vcf").write_text("".join(truth_lines))


def main(out_dir: Path) -> None:
    """
    Generate all inputs under the given output directory.

    Args:
        out_dir: Directory to populate (created if absent).
    """
    rng = random.Random(SEED)
    inputs = out_dir / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)

    reference = make_reference(rng)
    write_fasta(reference, out_dir / "ref.fasta")
    pairs = simulate_pairs(reference, rng)
    write_sam(pairs, out_dir / "reads.sam")
    write_interval_bodies(inputs)
    write_refflat(inputs)
    write_vcfs(reference, inputs, rng)
    print(f"Wrote reference, {len(pairs)} read pairs, intervals, refFlat, and VCFs to {out_dir}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build"))
