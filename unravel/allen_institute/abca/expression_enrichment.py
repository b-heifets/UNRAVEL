#!/usr/bin/env python3

"""
Compare GPCR or other gene expression between two groups of ABCA cells.

Input:
    CSV from rna_exp or mf_filter with log2(CPM+1) expression values.
    Requires infer_genes from unravel.allen_institute.abca.expression_summary.

Groups:
    - -c specifies a metadata column; -vals lists target values.
    - -ref lists reference values in the same column. If omitted, use all
      other non-missing values, after any -fc/-fv prefilter.
    - Values match exactly and are case-sensitive. Multiple values use OR.
      Quote each label containing spaces separately. Groups must not overlap.
    - -fc/-fv optionally restrict both groups before comparison.
    - Missing group labels are excluded. No species-specific labels are assumed.

Metrics:
    - mean_expression: mean log2(CPM+1), including zeros.
    - mean_cpm: mean of per-cell 2**expression - 1, including zeros.
    - percent_expression: percent of non-missing values strictly above -t.
    - fold_change: (target mean_cpm + p) / (reference mean_cpm + p).
    - log2_fold_change: log2(fold_change); positive favors the target.
    - percent_expression_difference: target minus reference, percentage points.
    - Missing expression values are excluded separately for each gene.
      A gene with no valid values in either group has undefined enrichment.

Notes:
    Means pool cells, weighting by sampled cell numbers, not equally by region
    or donor. These are descriptive scores, not statistical tests. Low-expression
    fold changes depend on the pseudocount. Both means zero gives log2FC = 0.
    CSV is processed in chunks. Default genes: columns after the last *_color.
    Output: one row per gene, sorted by descending log2 fold change.

Usage (replace example labels with exact values from your CSV):
    python exp_enrichment.py -i expression.csv -c region_of_interest_acronym -vals "STR label" -o STR_enrichment.csv
    python exp_enrichment.py -i expression.csv -c cluster -vals "D1 label" -ref "D2 label" -o D1_vs_D2.csv
    python exp_enrichment.py -i expression.csv -c cluster -vals "D1 label" -ref "D2 label" -fc region_of_interest_acronym -fv "STR label"
"""

from pathlib import Path

import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.allen_institute.abca.expression_summary import infer_genes
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='CSV containing log2(CPM+1) expression.', required=True, action=SM)
    reqs.add_argument('-c', '--column', help='Metadata column defining target and reference groups.', required=True, action=SM)
    reqs.add_argument('-vals', '--target-values', help='Exact target labels; multiple values use OR.', required=True, nargs='+', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-ref', '--reference-values', help='Exact reference labels. Default: all other labeled cells.', nargs='+', default=None, action=SM)
    opts.add_argument('-fc', '--filter-column', help='Metadata column used to restrict both groups.', default=None, action=SM)
    opts.add_argument('-fv', '--filter-values', help='Exact values to retain before comparison.', nargs='+', default=None, action=SM)
    opts.add_argument('-g', '--genes', help='Genes to compare. Default: columns after the last *_color.', nargs='+', default=None, action=SM)
    opts.add_argument('-t', '--threshold', help='Log2(CPM+1) threshold for percent expression. Default: 3', type=float, default=3, action=SM)
    opts.add_argument('-p', '--pseudocount', help='Positive pseudocount added to mean CPM. Default: 1', type=float, default=1, action=SM)
    opts.add_argument('-cs', '--chunksize', help='Cells per input chunk. Default: 10000', type=int, default=10000, action=SM)
    opts.add_argument('-o', '--output', help='Output CSV. Default: <input>_enrichment.csv', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)

    args = parser.parse_args()
    if (args.filter_column is None) != (args.filter_values is None):
        parser.error('--filter-column and --filter-values must be used together.')
    if args.reference_values and set(args.target_values) & set(args.reference_values):
        parser.error('Target and reference labels must not overlap.')
    if not np.isfinite(args.threshold) or args.threshold < 0:
        parser.error('--threshold must be finite and nonnegative.')
    if not np.isfinite(args.pseudocount) or args.pseudocount <= 0:
        parser.error('--pseudocount must be finite and positive.')
    if args.chunksize < 1:
        parser.error('--chunksize must be positive.')
    return args


def new_stats(n_genes):
    return {
        'cell_count': 0,
        'expression_count': np.zeros(n_genes, dtype=np.int64),
        'expressing_cell_count': np.zeros(n_genes, dtype=np.int64),
        'sum_expression': np.zeros(n_genes),
        'sum_cpm': np.zeros(n_genes),
    }


def accumulate(frame, genes, threshold, stats):
    if frame.empty:
        return
    try:
        values = frame[genes].to_numpy(dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError('Gene columns must contain numeric expression or missing values.') from exc
    invalid = np.isinf(values) | (values < 0)
    if invalid.any():
        gene = genes[np.nonzero(invalid)[1][0]]
        raise ValueError(f'Negative or infinite expression in gene {gene!r}. Expected log2(CPM+1).')

    with np.errstate(over='raise', invalid='raise'):
        cpm = np.exp2(values) - 1
        stats['sum_cpm'] += np.nansum(cpm, axis=0)
        stats['sum_expression'] += np.nansum(values, axis=0)
    stats['cell_count'] += len(frame)
    stats['expression_count'] += np.sum(~np.isnan(values), axis=0)
    stats['expressing_cell_count'] += np.sum(values > threshold, axis=0)


def group_summary(stats, genes, prefix):
    denominator = stats['expression_count'].astype(float)
    denominator[denominator == 0] = np.nan
    return pd.DataFrame({
        f'{prefix}_cell_count': stats['cell_count'],
        f'{prefix}_expression_count': stats['expression_count'],
        f'{prefix}_expressing_cell_count': stats['expressing_cell_count'],
        f'{prefix}_mean_expression': stats['sum_expression'] / denominator,
        f'{prefix}_mean_cpm': stats['sum_cpm'] / denominator,
        f'{prefix}_percent_expression': 100 * stats['expressing_cell_count'] / denominator,
    }, index=pd.Index(genes, name='gene'))


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path.with_name(f'{input_path.stem}_enrichment.csv')
    if input_path.resolve() == output_path.resolve():
        raise ValueError('Output must differ from the input CSV.')

    header = pd.read_csv(input_path, nrows=0).columns.tolist()
    genes = infer_genes(header, args.genes)
    metadata = list(dict.fromkeys([args.column] + ([args.filter_column] if args.filter_column else [])))
    missing = sorted(set(genes + metadata) - set(header))
    if missing:
        raise ValueError(f'Missing columns: {missing}')
    if set(genes) & set(metadata):
        raise ValueError('Group/filter metadata columns must not also be selected as genes. Use -g.')

    target = new_stats(len(genes))
    reference = new_stats(len(genes))
    seen_labels = set()
    seen_filter_values = set()
    missing_labels = 0
    total_cells = 0
    reader = pd.read_csv(input_path, usecols=metadata + genes,
                         dtype={column: 'string' for column in metadata},
                         chunksize=args.chunksize, low_memory=False)

    print(f'\nInput: {input_path}\nGenes: {len(genes)}')
    print(f'Target: {args.target_values}')
    print(f'Reference: {args.reference_values or "All other labeled cells"}')

    for chunk in reader:
        total_cells += len(chunk)
        if args.filter_column:
            seen_filter_values.update(chunk[args.filter_column].dropna().unique())
            chunk = chunk.loc[chunk[args.filter_column].isin(args.filter_values)]
        labels = chunk[args.column]
        seen_labels.update(labels.dropna().unique())
        missing_labels += int(labels.isna().sum())
        target_mask = labels.isin(args.target_values)
        reference_mask = (labels.isin(args.reference_values) if args.reference_values
                          else labels.notna() & ~target_mask)
        accumulate(chunk.loc[target_mask], genes, args.threshold, target)
        accumulate(chunk.loc[reference_mask], genes, args.threshold, reference)
        if args.verbose:
            print(f'Read {total_cells:,} cells.')

    unmatched_filters = sorted(set(args.filter_values or []) - seen_filter_values)
    if unmatched_filters:
        raise ValueError(f'Filter values not found: {unmatched_filters}. Matching is exact and case-sensitive.')
    unmatched = sorted(set(args.target_values + (args.reference_values or [])) - seen_labels)
    if unmatched:
        raise ValueError(f'Group labels not found after filtering: {unmatched}. Matching is exact and case-sensitive.')
    if target['cell_count'] == 0 or reference['cell_count'] == 0:
        raise ValueError('Target and reference must each contain at least one cell after filtering.')

    summary = pd.concat([group_summary(target, genes, 'target'),
                         group_summary(reference, genes, 'reference')], axis=1)
    summary['log2_fold_change'] = (np.log2(summary['target_mean_cpm'] + args.pseudocount)
                                   - np.log2(summary['reference_mean_cpm'] + args.pseudocount))
    summary['fold_change'] = ((summary['target_mean_cpm'] + args.pseudocount)
                              / (summary['reference_mean_cpm'] + args.pseudocount))
    summary['percent_expression_difference'] = (summary['target_percent_expression']
                                                - summary['reference_percent_expression'])
    summary['group_column'] = args.column
    summary['target_values'] = ' | '.join(args.target_values)
    summary['reference_values'] = ' | '.join(args.reference_values) if args.reference_values else 'All other labeled cells'
    summary['filter_column'] = args.filter_column or ''
    summary['filter_values'] = ' | '.join(args.filter_values or [])
    summary['threshold'] = args.threshold
    summary['pseudocount_cpm'] = args.pseudocount
    summary = summary.sort_values('log2_fold_change', ascending=False, kind='stable', na_position='last')

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=True)
    print(f'\nTarget: {target["cell_count"]:,} cells; reference: {reference["cell_count"]:,} cells.')
    if missing_labels:
        print(f'[yellow]Excluded {missing_labels:,} cells with missing group labels after filtering.[/yellow]')
    print(f'Saved {len(summary):,} genes: {output_path}\n')
    verbose_end_msg()


if __name__ == '__main__':
    main()
