#!/usr/bin/env python3

"""
Use ``abca_scRNAseq_expression_summary`` or ``rna_exp_summary`` from UNRAVEL to summarize log2(CPM+1) expression across every level of the ABCA cell-type ontology.

The input should be a CSV produced by ``abca_scRNAseq_expression`` / ``rna_exp``
with ABCA cell-type annotations and one or more gene-expression columns.

Mouse hierarchy:
    neurotransmitter -> class -> subclass -> supertype -> cluster

Human hierarchy:
    neurotransmitter -> supercluster -> cluster -> subcluster

For each gene and ontology node, the script calculates:
    - cell_count
    - expression_cell_count
    - expressing_cell_count
    - mean_expression
    - percent_expression above the selected log2(CPM+1) threshold

Outputs:
    - all_levels_long/<input>__all_levels_expression_summary_thr<value>.csv
      One row per gene and ontology node. This is the primary dot-plot-ready output.
    - by_gene/<input>__gene-GENE_expression_summary_thr<value>.csv
      One CSV per gene containing all ontology levels.
    - by_level/<input>__level-LEVEL_expression_summary_thr<value>.csv
      One wide CSV per ontology level, with gene-specific metric columns.

Notes:
    - The script reads the input in chunks so it can summarize large human and mouse CSVs without loading the entire file into memory.
    - ``cell_count`` counts all rows assigned to an ontology node.
    - ``expression_cell_count`` counts non-missing values for a gene and is the denominator used for mean and percent expression.
    - An ``all`` row is included for each gene before the ontology levels.

Usage for mouse:
----------------
    rna_exp_summary -i path/expression_data_log2.csv -s mouse -g Htr2a Htr2b Drd1 Drd2 -t 3

Usage for human:
----------------
    rna_exp_summary -i path/expression_data_Neurons_log2.csv -s human -g HTR2A HTR2B DRD1 DRD2 -t 3
"""

import re
from pathlib import Path

import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


HIERARCHY_LEVELS = {
    'mouse': ['neurotransmitter', 'class', 'subclass', 'supertype', 'cluster'],
    'human': ['neurotransmitter', 'supercluster', 'cluster', 'subcluster'],
}

METRIC_COLUMNS = [
    'expression_cell_count',
    'expressing_cell_count',
    'mean_expression',
    'percent_expression',
]


def parse_args():
    parser = RichArgumentParser(
        formatter_class=SuppressMetavar,
        add_help=False,
        docstring=__doc__,
    )

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument(
        '-i', '--input',
        help='Path to a CSV containing ABCA cell-type annotations and gene expression.',
        required=True,
        action=SM,
    )
    reqs.add_argument(
        '-g', '--genes',
        help='Gene-expression columns to summarize.',
        nargs='+',
        required=True,
        action=SM,
    )

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument(
        '-s', '--species',
        help='Species to analyze. Default: mouse',
        default='mouse',
        choices=('mouse', 'human'),
        action=SM,
    )
    opts.add_argument(
        '-t', '--threshold',
        help='Log2(CPM+1) threshold for percent expression. Default: 3',
        default=3,
        type=float,
        action=SM,
    )
    opts.add_argument(
        '-o', '--output',
        help='Output directory. Default: input_dir/ABCA_expression_summary_thr<value>',
        default=None,
        action=SM,
    )
    opts.add_argument(
        '-op', '--output_prefix',
        help='Output file prefix. Default: input stem',
        default=None,
        action=SM,
    )
    opts.add_argument(
        '-ch', '--chunksize',
        help='Rows read per chunk. Default: 250000',
        default=250_000,
        type=int,
        action=SM,
    )
    opts.add_argument(
        '--no-gene-files',
        help='Do not save one CSV per gene.',
        action='store_true',
        default=False,
    )
    opts.add_argument(
        '--no-level-files',
        help='Do not save one CSV per ontology level.',
        action='store_true',
        default=False,
    )

    general = parser.add_argument_group('General arguments')
    general.add_argument(
        '-v', '--verbose',
        help='Increase verbosity. Default: False',
        action='store_true',
        default=False,
    )

    return parser.parse_args()


def format_number(value: float) -> str:
    """Format a numeric CLI value for compact file names."""
    return f'{value:g}'


def safe_name(value: str) -> str:
    """Convert a label to a file-name-safe string."""
    return re.sub(r'[^A-Za-z0-9._-]+', '_', str(value)).strip('_')


def natural_sort_text(value) -> str:
    """Return a zero-padded text key for natural sorting without extra dependencies."""
    text = '' if pd.isna(value) else str(value).lower()
    return re.sub(r'\d+', lambda match: f'{int(match.group()):012d}', text)


def validate_columns(input_path: Path, species: str, genes: list[str]) -> tuple[list[str], list[str]]:
    """Validate ontology and gene columns and return hierarchy and available color columns."""
    header = pd.read_csv(input_path, nrows=0).columns.tolist()
    hierarchy_levels = HIERARCHY_LEVELS[species]

    expected = set(hierarchy_levels + genes)
    missing = sorted(expected - set(header))
    if missing:
        raise ValueError(
            f'Missing expected columns for {species} data: {missing}'
        )

    color_columns = [
        f'{level}_color'
        for level in hierarchy_levels
        if f'{level}_color' in header
    ]
    return hierarchy_levels, color_columns


def summarize_chunks(
    input_path: Path,
    species: str,
    genes: list[str],
    threshold: float,
    chunksize: int,
    verbose: bool = False,
) -> pd.DataFrame:
    """Summarize expression across all ontology levels using chunked aggregation."""
    hierarchy_levels, color_columns = validate_columns(
        input_path,
        species,
        genes,
    )
    usecols = hierarchy_levels + color_columns + genes

    partials = {level: [] for level in hierarchy_levels}
    total_cells = 0
    total_sum = {gene: 0.0 for gene in genes}
    total_expression_count = {gene: 0 for gene in genes}
    total_expressing_count = {gene: 0 for gene in genes}

    reader = pd.read_csv(
        input_path,
        usecols=usecols,
        chunksize=chunksize,
        low_memory=False,
    )

    for chunk_number, chunk in enumerate(reader, start=1):
        total_cells += len(chunk)

        for level in hierarchy_levels:
            chunk[level] = chunk[level].astype('string').fillna('NA')

        for gene in genes:
            original_nonmissing = chunk[gene].notna()
            numeric = pd.to_numeric(chunk[gene], errors='coerce')
            invalid = original_nonmissing & numeric.isna()
            if invalid.any():
                bad_value = chunk.loc[invalid, gene].iloc[0]
                raise ValueError(
                    f"Non-numeric value found in gene column '{gene}': {bad_value!r}"
                )
            chunk[gene] = numeric

            total_sum[gene] += numeric.sum()
            total_expression_count[gene] += int(numeric.count())
            total_expressing_count[gene] += int((numeric > threshold).sum())

        expressing = chunk[genes].gt(threshold).astype('int64')
        expressing.columns = [f'{gene}__expressing' for gene in genes]
        grouped_source = pd.concat(
            [chunk[hierarchy_levels + color_columns + genes], expressing],
            axis=1,
        )

        for level_index, level in enumerate(hierarchy_levels):
            group_cols = hierarchy_levels[:level_index + 1]
            grouped = grouped_source.groupby(
                group_cols,
                sort=False,
                dropna=False,
            )

            partial = grouped.size().rename('cell_count').to_frame()

            for gene in genes:
                partial[f'{gene}__sum'] = grouped[gene].sum()
                partial[f'{gene}__count'] = grouped[gene].count()
                partial[f'{gene}__expressing'] = grouped[
                    f'{gene}__expressing'
                ].sum()

            color_col = f'{level}_color'
            if color_col in color_columns:
                partial['cell_type_color'] = grouped[color_col].first()

            partials[level].append(partial.reset_index())

        if verbose:
            print(
                f'    Processed chunk {chunk_number}: '
                f'{len(chunk):,} rows; cumulative rows: {total_cells:,}'
            )

    if total_cells == 0:
        raise ValueError(f'No rows found in input: {input_path}')

    long_dfs = []

    # Include a root row for all cells.
    for gene in genes:
        expression_count = total_expression_count[gene]
        long_dfs.append(pd.DataFrame({
            'gene': [gene],
            'level': ['all'],
            'level_order': [0],
            'cell_type': ['All cells'],
            'parent_level': [''],
            'parent_cell_type': [''],
            'cell_type_color': [''],
            'ontology_path': ['All cells'],
            **{level: [''] for level in hierarchy_levels},
            'cell_count': [total_cells],
            'expression_cell_count': [expression_count],
            'expressing_cell_count': [total_expressing_count[gene]],
            'mean_expression': [
                total_sum[gene] / expression_count
                if expression_count else float('nan')
            ],
            'percent_expression': [
                total_expressing_count[gene] / expression_count * 100
                if expression_count else float('nan')
            ],
        }))

    # Combine chunk-level summaries for each ontology level.
    for level_index, level in enumerate(hierarchy_levels):
        group_cols = hierarchy_levels[:level_index + 1]
        combined = pd.concat(partials[level], ignore_index=True)

        aggregate_columns = {
            'cell_count': 'sum',
            **{
                f'{gene}__{metric}': 'sum'
                for gene in genes
                for metric in ('sum', 'count', 'expressing')
            },
        }
        if 'cell_type_color' in combined.columns:
            aggregate_columns['cell_type_color'] = 'first'

        combined = combined.groupby(
            group_cols,
            sort=False,
            dropna=False,
            as_index=False,
        ).agg(aggregate_columns)

        for gene in genes:
            expression_count = combined[f'{gene}__count']
            expressing_count = combined[f'{gene}__expressing']

            gene_df = combined[group_cols + ['cell_count']].copy()
            gene_df['gene'] = gene
            gene_df['level'] = level
            gene_df['level_order'] = level_index + 1
            gene_df['cell_type'] = gene_df[level]
            gene_df['parent_level'] = (
                hierarchy_levels[level_index - 1]
                if level_index > 0 else 'all'
            )
            gene_df['parent_cell_type'] = (
                gene_df[hierarchy_levels[level_index - 1]]
                if level_index > 0 else 'All cells'
            )
            gene_df['cell_type_color'] = (
                combined['cell_type_color'].fillna('')
                if 'cell_type_color' in combined.columns else ''
            )

            for descendant in hierarchy_levels[level_index + 1:]:
                gene_df[descendant] = ''

            gene_df['ontology_path'] = gene_df[hierarchy_levels].apply(
                lambda row: ' > '.join(
                    str(value) for value in row if str(value)
                ),
                axis=1,
            )
            gene_df['expression_cell_count'] = expression_count.astype('int64')
            gene_df['expressing_cell_count'] = expressing_count.astype('int64')
            denominator = expression_count.where(expression_count.ne(0))
            gene_df['mean_expression'] = (
                combined[f'{gene}__sum'] / denominator
            )
            gene_df['percent_expression'] = (
                expressing_count / denominator * 100
            )

            long_dfs.append(gene_df)

    summary_df = pd.concat(long_dfs, ignore_index=True)
    summary_df.insert(0, 'input', input_path.name)
    summary_df.insert(1, 'species', species)
    summary_df.insert(3, 'threshold', threshold)

    output_columns = [
        'input',
        'species',
        'gene',
        'threshold',
        'level',
        'level_order',
        'cell_type',
        'parent_level',
        'parent_cell_type',
        'cell_type_color',
        'ontology_path',
        *hierarchy_levels,
        'cell_count',
        'expression_cell_count',
        'expressing_cell_count',
        'mean_expression',
        'percent_expression',
    ]
    summary_df = summary_df[output_columns]

    gene_order = {gene: index for index, gene in enumerate(genes)}
    summary_df['_gene_order'] = summary_df['gene'].map(gene_order)

    sort_columns = []
    for level in hierarchy_levels:
        sort_col = f'_{level}_sort'
        summary_df[sort_col] = summary_df[level].map(natural_sort_text)
        sort_columns.append(sort_col)

    summary_df = summary_df.sort_values(
        ['level_order', *sort_columns, '_gene_order'],
        kind='stable',
    ).drop(columns=['_gene_order', *sort_columns])

    return summary_df.reset_index(drop=True)


def level_wide_dataframe(
    level_df: pd.DataFrame,
    hierarchy_levels: list[str],
    genes: list[str],
) -> pd.DataFrame:
    """Convert one ontology level from long to wide gene-specific metric columns."""
    base_columns = [
        'input',
        'species',
        'threshold',
        'level',
        'level_order',
        'cell_type',
        'parent_level',
        'parent_cell_type',
        'cell_type_color',
        'ontology_path',
        *hierarchy_levels,
        'cell_count',
    ]

    first_gene = genes[0]
    wide_df = level_df[level_df['gene'] == first_gene][base_columns].copy()

    for gene in genes:
        gene_metrics = level_df[level_df['gene'] == gene][
            ['ontology_path', *METRIC_COLUMNS]
        ].copy()
        gene_metrics = gene_metrics.rename(columns={
            metric: f'{gene}_{metric}'
            for metric in METRIC_COLUMNS
        })
        wide_df = wide_df.merge(
            gene_metrics,
            on='ontology_path',
            how='left',
            validate='one_to_one',
        )

    return wide_df


def save_outputs(
    summary_df: pd.DataFrame,
    input_path: Path,
    output_dir: Path,
    output_prefix: str,
    species: str,
    genes: list[str],
    threshold: float,
    save_gene_files: bool = True,
    save_level_files: bool = True,
) -> list[Path]:
    """Save combined, per-gene, and per-level summaries."""
    hierarchy_levels = HIERARCHY_LEVELS[species]
    threshold_label = format_number(threshold)
    saved_paths = []

    long_dir = output_dir / 'all_levels_long'
    long_dir.mkdir(parents=True, exist_ok=True)
    combined_path = long_dir / (
        f'{output_prefix}__all_levels_expression_summary_thr{threshold_label}.csv'
    )
    summary_df.to_csv(combined_path, index=False)
    saved_paths.append(combined_path)

    if save_gene_files:
        gene_dir = output_dir / 'by_gene'
        gene_dir.mkdir(parents=True, exist_ok=True)
        for gene in genes:
            gene_path = gene_dir / (
                f'{output_prefix}__gene-{safe_name(gene)}_expression_summary_'
                f'thr{threshold_label}.csv'
            )
            summary_df[summary_df['gene'] == gene].to_csv(
                gene_path,
                index=False,
            )
            saved_paths.append(gene_path)

    if save_level_files:
        level_dir = output_dir / 'by_level'
        level_dir.mkdir(parents=True, exist_ok=True)
        for level in ['all', *hierarchy_levels]:
            level_df = summary_df[summary_df['level'] == level]
            wide_df = level_wide_dataframe(
                level_df,
                hierarchy_levels,
                genes,
            )
            level_path = level_dir / (
                f'{output_prefix}__level-{level}_expression_summary_'
                f'thr{threshold_label}.csv'
            )
            wide_df.to_csv(level_path, index=False)
            saved_paths.append(level_path)

    return saved_paths


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f'Input CSV not found: {input_path}')

    if args.chunksize <= 0:
        raise ValueError('--chunksize must be greater than 0.')

    genes = list(dict.fromkeys(args.genes))
    threshold_label = format_number(args.threshold)

    if args.output is None:
        output_dir = input_path.parent / (
            f'ABCA_expression_summary_thr{threshold_label}'
        )
    else:
        output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_prefix = args.output_prefix or input_path.stem

    print(f'\nUsing species: {args.species}')
    print(f'Genes: {genes}')
    print(f'Expression threshold: {args.threshold:g}')
    print(f'Input: {input_path}\n')

    summary_df = summarize_chunks(
        input_path=input_path,
        species=args.species,
        genes=genes,
        threshold=args.threshold,
        chunksize=args.chunksize,
        verbose=args.verbose,
    )

    saved_paths = save_outputs(
        summary_df=summary_df,
        input_path=input_path,
        output_dir=output_dir,
        output_prefix=output_prefix,
        species=args.species,
        genes=genes,
        threshold=args.threshold,
        save_gene_files=not args.no_gene_files,
        save_level_files=not args.no_level_files,
    )

    print(
        f'\nSaved {len(saved_paths)} expression summary CSVs to: '
        f'{output_dir}'
    )
    if args.verbose:
        for path in saved_paths:
            print(f'    {path}')

    verbose_end_msg()


if __name__ == '__main__':
    main()
