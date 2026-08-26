#!/usr/bin/env python3

"""
Use ``abca_expression_screen`` (``exp_screen``) from UNRAVEL to screen one or
more expression-summary CSVs and create a long-form table for comparing gene
expression across regions and cell types.

Inputs:
    - Wide CSVs produced by ``abca_expression_summary`` (``exp_summary``).
    - Cell-level expression CSVs are not analyzed directly. During a directory
      scan, they are skipped with a warning so a directory may contain both
      cell-level inputs and expression summaries.

Default eligibility criteria:
    - cell_count >= 20
    - percent_cells >= 0.1

Outputs:
    - <prefix>_genes.csv
        One row per eligible region x ontology level x gene x cell type, with
        cell abundance, expression metrics, and abundance-weighted metrics.
    - <prefix>_inputs.csv
        One row per screened summary with source metadata, input size, and
        eligibility coverage.

Region labels:
    - The region is inferred from the original ``input`` value stored by
      ``exp_summary``.
    - Text after the last ``__`` is treated as the region.
    - Otherwise, text after the last ``_filtered_`` is treated as the region.
    - Inputs without either delimiter are labeled ``brain-wide``.

Notes:
    - ``percent_cells`` represents cell-type representation within the cells in
      each input. For sc/snRNA-seq, it should not automatically be interpreted
      as unbiased tissue abundance.
    - Eligibility filtering occurs before rows are written.
    - No ranks or top-N flags are generated. Filter by region, ontology level,
      and gene, then sort by ``mean_expression``, ``percent_expression``, or
      ``percent_cells`` as needed.
    - ``mean_expression_contribution`` = ``mean_expression * percent_cells / 100``
      Contribution to the abundance-weighted mean log expression among sampled cells
      (not an estimate of total transcript abundance)
    - ``percent_all_cells_expressing`` is calculated as
      ``percent_expression * percent_cells / 100``. It is the percentage of all
      cells in the input that belong to the cell type and meet the expression
      threshold for the gene.
    - Each invocation should contain summaries from one logical dataset
      collection. File prefixes are otherwise unrestricted.
    - Cell-type colors and ontology-path details remain available in the
      source expression-summary CSVs and are not repeated in these outputs.

Usage:
------
    exp_screen -i path/exp_summary_thr3 [-g gene1 gene2 ...] ...
"""

from pathlib import Path

import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, match_files, verbose_end_msg, verbose_start_msg


MEAN_SUFFIX = '_mean_expression'
PERCENT_SUFFIX = '_percent_expression'

SUMMARY_BASE_COLUMNS = {
    'input',
    'species',
    'threshold',
    'level',
    'cell_type',
    'cell_count',
    'percent_cells',
}


def parse_args():
    parser = RichArgumentParser(
        formatter_class=SuppressMetavar,
        add_help=False,
        docstring=__doc__,
    )

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument(
        '-i', '--input',
        help=(
            "Pattern or patterns for CSV file(s) from `exp_summary`. "
            "Default: '*.csv'"
        ),
        nargs='*',
        default='*.csv',
        action=SM,
    )
    opts.add_argument(
        '-g', '--genes',
        help=(
            'Genes to screen. Matching is case-insensitive so one symbol can '
            'match human and mouse capitalization. Default: all detected genes.'
        ),
        nargs='*',
        default=None,
        action=SM,
    )
    opts.add_argument(
        '-l', '--levels',
        help='Cell-type ontology levels to include. Default: all detected levels.',
        nargs='*',
        default=None,
        action=SM,
    )
    opts.add_argument(
        '--min-cells',
        help='Minimum cell_count required. Default: 20',
        default=20,
        type=int,
        action=SM,
    )
    opts.add_argument(
        '--min-percent-cells',
        help='Minimum percent_cells required. Default: 0.1',
        default=0.1,
        type=float,
        action=SM,
    )
    opts.add_argument(
        '-o', '--output',
        help='Output directory. Default: expression_screen_* beside the input.',
        default=None,
        action=SM,
    )
    opts.add_argument(
        '-op', '--output-prefix',
        help='Output file prefix. Default: expression_screen',
        default='expression_screen',
        action=SM,
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
    """Format a numeric CLI value compactly for directory names."""
    return f'{value:g}'


def summary_genes(columns: list[str]) -> list[str]:
    """Return genes with complete mean- and percent-expression columns."""
    column_set = set(columns)
    genes = []

    for column in columns:
        if not column.endswith(MEAN_SUFFIX):
            continue

        gene = column[:-len(MEAN_SUFFIX)]
        if f'{gene}{PERCENT_SUFFIX}' in column_set:
            genes.append(gene)

    return genes


def is_expression_summary(columns: list[str]) -> bool:
    """Return True when a CSV header matches expression-summary output."""
    return SUMMARY_BASE_COLUMNS.issubset(columns) and bool(summary_genes(columns))


def select_genes(
    available: list[str],
    requested: list[str] | None,
) -> list[str]:
    """Select genes case-insensitively while preserving source column order."""
    if not requested:
        return available

    requested_keys = {gene.casefold() for gene in requested}
    return [gene for gene in available if gene.casefold() in requested_keys]


def infer_region(source_input: str) -> str:
    """Infer a region label from an exp_summary source-input name."""
    stem = Path(str(source_input)).stem

    if '__' in stem:
        region = stem.rsplit('__', 1)[-1]
    elif '_filtered_' in stem:
        region = stem.rsplit('_filtered_', 1)[-1]
    else:
        return 'brain-wide'

    if region.endswith('_neurons'):
        region = region[:-len('_neurons')]

    return region.replace('_', ' ')


def process_summary_file(
    summary_path: Path,
    requested_genes: list[str] | None,
    requested_levels: set[str] | None,
    min_cells: int,
    min_percent_cells: float,
) -> tuple[list[pd.DataFrame], list[dict], set[str]]:
    """Convert one wide expression summary to eligible long-form rows."""
    df = pd.read_csv(summary_path, low_memory=False)
    available_genes = summary_genes(df.columns.tolist())
    genes = select_genes(available_genes, requested_genes)
    found_genes = {gene.casefold() for gene in genes}

    if not genes:
        return [], [], found_genes

    for column in ('cell_count', 'percent_cells', 'threshold'):
        df[column] = pd.to_numeric(df[column], errors='coerce')

    group_columns = ['input', 'species', 'threshold', 'level']
    gene_parts = []
    input_records = []

    grouped = df.groupby(group_columns, sort=False, dropna=False)
    for group_values, group_df in grouped:
        source_input, species, threshold, level = group_values
        level = str(level)

        if requested_levels and level.casefold() not in requested_levels:
            continue

        source_input = str(source_input)
        species = str(species)
        region = infer_region(source_input)

        group_df = group_df.copy()
        group_df['cell_count'] = pd.to_numeric(
            group_df['cell_count'],
            errors='coerce',
        ).fillna(0)
        group_df['percent_cells'] = pd.to_numeric(
            group_df['percent_cells'],
            errors='coerce',
        ).fillna(0)

        eligible = group_df[
            (group_df['cell_count'] >= min_cells)
            & (group_df['percent_cells'] >= min_percent_cells)
        ].copy()

        input_records.append(
            {
                'source_input': source_input,
                'region': region,
                'species': species,
                'threshold': threshold,
                'level': level,
                'total_cells': int(group_df['cell_count'].sum()),
                'total_cell_types': len(group_df),
                'eligible_cell_types': len(eligible),
                'eligible_cell_coverage_percent': eligible[
                    'percent_cells'
                ].sum(),
                'genes': ';'.join(genes),
            }
        )

        if eligible.empty:
            continue

        for gene in genes:
            gene_df = eligible.copy()
            gene_df['mean_expression'] = pd.to_numeric(
                gene_df[f'{gene}{MEAN_SUFFIX}'],
                errors='coerce',
            )
            gene_df['percent_expression'] = pd.to_numeric(
                gene_df[f'{gene}{PERCENT_SUFFIX}'],
                errors='coerce',
            )
            gene_df['mean_expression_contribution'] = (
                gene_df['mean_expression']
                * gene_df['percent_cells']
                / 100
            )
            gene_df['percent_all_cells_expressing'] = (
                gene_df['percent_expression']
                * gene_df['percent_cells']
                / 100
            )
            gene_df['region'] = region
            gene_df['level'] = level
            gene_df['gene'] = gene

            keep_columns = [
                'region',
                'level',
                'gene',
                'cell_type',
                'cell_count',
                'mean_expression',
                'percent_expression',
                'percent_cells',
                'mean_expression_contribution',
                'percent_all_cells_expressing',
            ]
            gene_parts.append(gene_df[keep_columns])

    return gene_parts, input_records, found_genes


def build_gene_table(gene_parts: list[pd.DataFrame]) -> pd.DataFrame:
    """Combine and sort eligible gene-expression rows."""
    genes = pd.concat(gene_parts, ignore_index=True)

    return genes.sort_values(
        [
            'gene',
            'level',
            'mean_expression',
            'percent_expression',
            'percent_cells',
            'region',
            'cell_type',
        ],
        ascending=[True, True, False, False, False, True, True],
        kind='stable',
        na_position='last',
    ).reset_index(drop=True)


def build_input_table(input_records: list[dict]) -> pd.DataFrame:
    """Summarize source metadata, input size, and eligibility."""
    inputs = pd.DataFrame(input_records)

    return inputs.sort_values(
        ['species', 'threshold', 'level', 'region', 'source_input'],
        kind='stable',
    ).reset_index(drop=True)


def default_output_dir(
    inputs: list[str],
    min_cells: int,
    min_percent_cells: float,
) -> Path:
    """Choose a descriptive output directory beside a single input."""
    if len(inputs) == 1:
        input_path = Path(inputs[0])
        parent = input_path if input_path.is_dir() else input_path.parent
    else:
        parent = Path.cwd()

    name = (
        f'expression_screen_cells{min_cells}'
        f'_pct{format_number(min_percent_cells)}'
    )
    return parent / name


def write_outputs(
    output_dir: Path,
    output_prefix: str,
    genes: pd.DataFrame,
    inputs: pd.DataFrame,
) -> list[Path]:
    """Write screening tables and return their paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        'genes': genes,
        'inputs': inputs,
    }

    saved_paths = []
    for suffix, table in tables.items():
        output_path = output_dir / f'{output_prefix}_{suffix}.csv'
        table.to_csv(output_path, index=False)
        saved_paths.append(output_path)

    return saved_paths


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if args.min_cells < 0:
        raise ValueError('--min-cells must be 0 or greater.')
    if not 0 <= args.min_percent_cells <= 100:
        raise ValueError('--min-percent-cells must be between 0 and 100.')

    requested_levels = (
        {level.casefold() for level in args.levels}
        if args.levels
        else None
    )
    csv_paths = match_files(args.input)

    summary_paths = []
    skipped = []
    for csv_path in csv_paths:
        columns = pd.read_csv(csv_path, nrows=0).columns.tolist()

        if is_expression_summary(columns):
            summary_paths.append(csv_path)
        else:
            skipped.append(csv_path)

    if not summary_paths:
        raise ValueError(
            'No abca_expression_summary CSVs were found. Run exp_summary on '
            'cell-level expression inputs before screening them.'
        )

    gene_parts = []
    input_records = []
    found_gene_keys = set()

    for summary_path in summary_paths:
        parts, records, found = process_summary_file(
            summary_path=summary_path,
            requested_genes=args.genes,
            requested_levels=requested_levels,
            min_cells=args.min_cells,
            min_percent_cells=args.min_percent_cells,
        )
        gene_parts.extend(parts)
        input_records.extend(records)
        found_gene_keys.update(found)

    if args.genes:
        missing_genes = [
            gene
            for gene in args.genes
            if gene.casefold() not in found_gene_keys
        ]

        if missing_genes:
            print(
                '[yellow]Requested genes not found in any screened summary:'
                '[/yellow] '
                + ', '.join(missing_genes)
            )

    if not input_records:
        raise ValueError(
            'No summaries matched the requested genes and ontology levels.'
        )
    if not gene_parts:
        raise ValueError(
            'No cell types passed the minimum cell-count and percentage cutoffs.'
        )

    genes = build_gene_table(gene_parts)
    inputs = build_input_table(input_records)

    output_dir = (
        Path(args.output)
        if args.output is not None
        else default_output_dir(
            args.input,
            args.min_cells,
            args.min_percent_cells,
        )
    )
    saved_paths = write_outputs(
        output_dir=output_dir,
        output_prefix=args.output_prefix,
        genes=genes,
        inputs=inputs,
    )

    print(f'\nScreened {len(summary_paths)} expression-summary CSV(s).')
    if skipped:
        print(
            f'[yellow]Skipped {len(skipped)} non-summary CSV(s).[/yellow] '
            'Run exp_summary first if they should be included.'
        )

        if args.verbose:
            for path in skipped:
                print(f'  {path}')

    print('\nSaved:')
    for path in saved_paths:
        print(f'  {path}')

    verbose_end_msg()


if __name__ == '__main__':
    main()
