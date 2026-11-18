# Intended sites in CRISPResso2 alignments

PEAnalyzer runs conventional CRISPResso2 2.3.4 once per populated two-substitution target and sample with the supplied WT references. This measures substitutions observed in amplicon sequencing. The software checks that the two intended bases and their flanking sequence correspond uniquely across all four haplotypes of all eligible references, including strand. Differences elsewhere in the references can include substitutions and indels. The allele table, reference sequences, native counts, resolved quantification windows and execution arguments are retained in the sample's metrics directory.

## Populations

The starting unit is a prepared physical read pair. A run passes both mates through Core's paired-end preprocessing. The report accounts for preprocessing losses, unaligned reads, ambiguous alignments, discarded alignments and ordinary alignments. Each ordinary allele contributes its integer abundance once to the combined result. Per-reference alignment totals audit Core's alignment choice. Separate read-pair measurements with invariant DNA markers provide biological copy evidence.

The Site A and Site B denominators count reads observing the respective coordinate as A, C, G, T or a uniquely interpretable internal deletion. An N, missing coverage, or equivalent placements of a repeat deletion that disagree at the site makes the site unassessable. Partial observation at one site can support the other site's marginal fraction. Both sites must be observed for a joint fraction. Joint WT, A-only, B-only and double-edit counts describe bases at the two intended sites. An unexpected base or an internal deletion at either site contributes to other/mixed. The any-edit numerator includes reads with an intended substitution paired with another identifiable unexpected base. Supplementary counters record additional substitutions, indels, incomplete/unknown sequence, AB with additional changes and literal full-length AB. Counters for additional changes can overlap. Core's alignment lacks the original per-mate quality evidence used by the separate dual-Q30 method.

The native window-modified count includes modifications called by Core in its effective window. PEAnalyzer reads each WT reference's actual `include_idxs`, reports excluded intended positions and preserves the requested coordinates. If an experiment supplies guide-relative window size or center alone, the guide-free measurement requires an explicit per-copy coordinate definition. The native PE-reference analysis retains its own guides, backend reference representation and denominator.

## EPSPS results

Each EPSPS run here used the two supplied WT sequences and explicit qualification windows 146–146 and 157–157 on each copy. These are documented test settings. Historical experimental guide/window and sample metadata still require confirmation. The labels 1A and all known refer to pairs of recognized inline barcodes. The acquisition-order comparison preserves the trimmed R1 and R2 pairing as sequenced. The forward-first regression places the WT-forward mate first. Both use leading trims of 26 and 27 bases in acquired R1 and R2 respectively.

| Input and supplied order | Input | After preprocessing | Aligned | Ambiguous | WT/WT | A only | B only | AB | Other/mixed | Joint unassessable | AB denominator | Literal AB among ordinary alignments |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1A, acquisition order | 5,564 | 5,465 | 5,040 | 1 | 4,979 | 31 | 8 | 21 | 0 | 0 | 5,039 | 17 |
| 1A, WT-forward mate first | 5,564 | 5,543 | 5,115 | 1 | 5,027 | 31 | 15 | 21 | 20 | 0 | 5,114 | 11 |
| All recognized pairs, WT-forward mate first | 114,761 | 114,250 | 105,769 | 49 | 105,033 | 88 | 161 | 25 | 411 | 2 | 105,718 | 12 |

In acquisition order, 1A contributed 52/5,039 Site A and 29/5,039 Site B observations carrying the respective intended substitution. With the WT-forward mate first, these counts were 52/5,114 and 36/5,114. The all-known marginal denominators were 105,720 for Site A and 105,718 for Site B. The original M7 input order is explicitly recorded. A change in supplied mate order alters the physical preprocessing result in real data. Comparing counts between the two orders requires identifying both populations.

## Reproduction

First prepare the derived pairs using the read-only procedure in [the EPSPS regression](../epsps-real/README.md). In an environment with the digest-pinned executable and editable package, run:

```sh
python docs/validation/v110-sites/qualify.py /new/workdir /path/to/attachments /path/to/derived/work --executable peanalyzer-crispresso
```

The runner checks known synthetic molecules (including partial, double, additional-change and deletion products) against four genuine two-WT runs. The three window settings are Core defaults, explicit intended coordinates and a disjoint window. The fourth run reverses the input mate order. Per-reference counts for all 82 synthetic molecules agree with their input truth. Native window-modified counts per copy were 25, 23 and 0 for the default, intended and disjoint windows respectively. An independent acquisition-order executable invocation re-demultiplexes 1A from the raw source, reconstructs each merged read's contribution by read ID and sequence and checks per-reference nucleotide frequencies. The forward-first EPSPS invocations are compared to the independently executed [integer recount](../epsps-real/evidence/core-comparison.json). The resulting [per-reference and combined integers](integer-reconciliation.json) include the paired input hashes.

The known synthetic two-site end-to-end workflow test exercises `peanalyzer run`, `--resume` and `peanalyzer analyze`. A populated experimental sample has 40 pairs. A declared negative control has zero pairs. Run the opt-in test with `M7_INTEGRATION=1` and `M3_CORE_EXECUTABLE` set to the pinned executable.
