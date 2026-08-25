#!/usr/bin/env python3

"""
Use ``abca_scRNAseq_expression_summary`` or ``rna_exp_summary`` from UNRAVEL to summarize log2(CPM+1) expression across every level of the ABCA cell-type ontology.

The input should be a CSV produced by ``abca_scRNAseq_expression`` / ``rna_exp``
with ABCA cell-type annotations and one or more gene-expression columns.

Mouse hierarchy:
    neurotransmitter -> class -> subclass -> supertype -> cluster

Human hierarchy:
    neurotransmitter -> supercluster -> cluster -> subcluster

For each gene and cell type, the script calculates:
    - cell_count
    - percent_cells (percentage of cells in the input assigned to the cell type at the given ontology level.)
    - expressing_cell_count
    - mean_expression
    - percent_expression above the selected log2(CPM+1) threshold

Outputs:
    - <input>__LEVEL.csv
      One wide CSV per ontology level. Identical cell-type labels that occur
      under different parent ontology paths are combined into one row.

Notes:
    - Example of collapsing: if Cell type A occurs under two different
      neurotransmitter parents, the output contains one Cell type A row
      combining cells from both parent paths.
    - ``cell_count`` counts all rows assigned to a cell type.
    - Mean expression is calculated from non-missing expression values.
    - Percent expression uses non-missing expression values as the denominator.
    - By default, outputs are saved to ``expression_summary_thr<value>`` in the input directory.
    - ``source_path_count`` is the number of unique ontology paths contributing
      to a collapsed cell-type row.
    - ``source_ontology_paths`` lists those contributing ontology paths.

Genes:
    - Use -g/--genes to summarize selected genes.
    - If -g is omitted, all columns after the last column containing '_color' are
      assumed to contain gene-expression values.

Species:
    - Species is inferred automatically from the ABCA ontology columns

Usage for mouse:
----------------
    rna_exp_summary -i path/expression_data_log2.csv [-g Htr2a Htr2b Drd1 Drd2] [-t 3]

Usage for human:
----------------
    rna_exp_summary -i path/expression_data_Neurons_log2.csv [-g HTR2A HTR2B DRD1 DRD2] [-t 3]

Usage for parallel processing:
------------------------------
    fd -e csv -d 1 -j 4 -x rna_exp_summary -i {}
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

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument(
        '-g', '--genes',
        help='Gene-expression columns to summarize. Default: all columns after the last *_color column.',
        nargs='*',
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
        help='Output directory. Default: input_dir/expression_summary_thr<value>',
        default=None,
        action=SM,
    )
    opts.add_argument(
        '-op', '--output_prefix',
        help='Output file prefix. Default: input stem',
        default=None,
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


def infer_species(columns: list[str]) -> str:
    """Infer species from ABCA ontology columns."""
    columns = set(columns)

    if {'class', 'subclass', 'supertype'}.issubset(columns):
        return 'mouse'

    if {'supercluster', 'subcluster'}.issubset(columns):
        return 'human'

    raise ValueError(
        'Could not infer species from the ABCA ontology columns.'
    )


def infer_genes(
    columns: list[str],
    requested_genes: list[str] | None,
) -> list[str]:
    """Return requested genes or infer gene columns from column order."""
    if requested_genes:
        return list(dict.fromkeys(requested_genes))

    color_indexes = [
        index
        for index, column in enumerate(columns)
        if column.endswith('_color')
    ]

    if not color_indexes:
        raise ValueError(
            'Could not infer gene columns because no *_color columns were found. '
            'Specify genes with -g/--genes.'
        )

    genes = columns[max(color_indexes) + 1:]

    if not genes:
        raise ValueError(
            'No gene-expression columns were found after the last *_color column.'
        )

    return genes


def format_number(value: float) -> str:
    """Format a numeric CLI value for compact file names."""
    return f'{value:g}'


def natural_sort_text(value) -> str:
    """Return a zero-padded text key for natural sorting without extra dependencies."""
    text = '' if pd.isna(value) else str(value).lower()
    return re.sub(r'\d+', lambda match: f'{int(match.group()):012d}', text)


def load_expression_data(
    input_path: Path,
    species: str,
    genes: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """Load required ontology, color, and gene-expression columns."""
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

    usecols = hierarchy_levels + color_columns + genes
    cell_df = pd.read_csv(
        input_path,
        usecols=usecols,
        low_memory=False,
    )

    if cell_df.empty:
        raise ValueError(f'No rows found in input: {input_path}')

    for level in hierarchy_levels:
        cell_df[level] = cell_df[level].astype('string').fillna('NA')

    for gene in genes:
        original_nonmissing = cell_df[gene].notna()
        numeric = pd.to_numeric(cell_df[gene], errors='coerce')
        invalid = original_nonmissing & numeric.isna()
        if invalid.any():
            bad_value = cell_df.loc[invalid, gene].iloc[0]
            raise ValueError(
                f"Non-numeric value found in gene column '{gene}': {bad_value!r}"
            )
        cell_df[gene] = numeric

    return cell_df, hierarchy_levels


def source_paths_dataframe(
    cell_df: pd.DataFrame,
    level: str,
    path_columns: list[str],
) -> pd.DataFrame:
    """Summarize unique ontology paths contributing to each cell-type label."""
    path_df = cell_df[path_columns].drop_duplicates().copy()
    path_df['ontology_path'] = path_df[path_columns].agg(' > '.join, axis=1)

    path_df = path_df.groupby(
        level,
        sort=False,
        dropna=False,
        as_index=False,
    ).agg(
        source_path_count=('ontology_path', 'nunique'),
        source_ontology_paths=(
            'ontology_path',
            lambda values: ' | '.join(dict.fromkeys(values.astype(str))),
        ),
    )

    return path_df.rename(columns={level: 'cell_type'})


def summarize_level(
    cell_df: pd.DataFrame,
    input_name: str,
    species: str,
    genes: list[str],
    threshold: float,
    hierarchy_levels: list[str],
    level_index: int,
) -> pd.DataFrame:
    """Create one collapsed wide expression summary for an ontology level."""
    level = hierarchy_levels[level_index]

    grouped = cell_df.groupby(
        level,
        sort=False,
        dropna=False,
    )

    summary_df = grouped.size().rename('cell_count').to_frame()

    summary_df['percent_cells'] = (
        summary_df['cell_count']
        / len(cell_df)
        * 100
    )

    color_col = f'{level}_color'
    if color_col in cell_df.columns:
        summary_df['cell_type_color'] = grouped[color_col].first().fillna('')
    else:
        summary_df['cell_type_color'] = ''

    expression_count = grouped[genes].count()
    mean_expression = grouped[genes].mean()

    expressing_count = cell_df[genes].gt(threshold).groupby(
        cell_df[level],
        sort=False,
        dropna=False,
    ).sum()

    for gene in genes:
        denominator = expression_count[gene].where(
            expression_count[gene].ne(0)
        )

        summary_df[f'{gene}_expressing_cell_count'] = (
            expressing_count[gene].astype('int64')
        )
        summary_df[f'{gene}_mean_expression'] = (
            mean_expression[gene]
        )
        summary_df[f'{gene}_percent_expression'] = (
            expressing_count[gene]
            / denominator
            * 100
        )

    summary_df = summary_df.reset_index().rename(
        columns={level: 'cell_type'}
    )

    path_df = source_paths_dataframe(
        cell_df,
        level,
        hierarchy_levels[:level_index + 1],
    )

    summary_df = summary_df.merge(
        path_df,
        on='cell_type',
        how='left',
        validate='one_to_one',
    )

    summary_df.insert(0, 'input', input_name)
    summary_df.insert(1, 'species', species)
    summary_df.insert(2, 'threshold', threshold)
    summary_df.insert(3, 'level', level)

    base_columns = [
        'input',
        'species',
        'threshold',
        'level',
        'cell_type',
        'cell_type_color',
        'source_path_count',
        'source_ontology_paths',
        'cell_count',
        'percent_cells',
    ]

    metric_columns = [
        column
        for gene in genes
        for column in (
            f'{gene}_expressing_cell_count',
            f'{gene}_mean_expression',
            f'{gene}_percent_expression',
        )
    ]

    summary_df = summary_df[
        base_columns + metric_columns
    ]

    summary_df['_cell_type_sort'] = summary_df[
        'cell_type'
    ].map(natural_sort_text)

    return summary_df.sort_values(
        '_cell_type_sort',
        kind='stable',
    ).drop(
        columns='_cell_type_sort'
    ).reset_index(drop=True)


def save_outputs(
    cell_df: pd.DataFrame,
    input_name: str,
    output_dir: Path,
    output_prefix: str,
    species: str,
    genes: list[str],
    threshold: float,
    hierarchy_levels: list[str],
) -> list[Path]:
    """Save one collapsed wide CSV per ontology level."""
    saved_paths = []

    for level_index, level in enumerate(hierarchy_levels):
        summary_df = summarize_level(
            cell_df=cell_df,
            input_name=input_name,
            species=species,
            genes=genes,
            threshold=threshold,
            hierarchy_levels=hierarchy_levels,
            level_index=level_index,
        )

        output_path = output_dir / (
            f'{output_prefix}__{level}.csv'
        )

        summary_df.to_csv(
            output_path,
            index=False,
        )

        saved_paths.append(output_path)

    return saved_paths


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_path = Path(args.input)

    if not input_path.exists():
        raise FileNotFoundError(
            f'Input CSV not found: {input_path}'
        )


    header = pd.read_csv(input_path, nrows=0).columns.tolist()

    species = infer_species(header)
    genes = infer_genes(
        columns=header,
        requested_genes=args.genes,
    )
    threshold_label = format_number(args.threshold)

    if args.output is None:
        output_dir = input_path.parent / (
            f'expression_summary_thr{threshold_label}'
        )
    else:
        output_dir = Path(args.output)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_prefix = (
        args.output_prefix
        or input_path.stem
    )

    print(f'\nInput: {input_path}\n')
    print(f'Expression threshold: {args.threshold:g}')
    if args.verbose:
        print(f'Using species: {species}')
        print(f'Genes: {genes}')

    cell_df, hierarchy_levels = load_expression_data(
        input_path=input_path,
        species=species,
        genes=genes,
    )

    print(
        f'Loaded {len(cell_df):,} cells.\n'
    )

    saved_paths = save_outputs(
        cell_df=cell_df,
        input_name=input_path.name,
        output_dir=output_dir,
        output_prefix=output_prefix,
        species=species,
        genes=genes,
        threshold=args.threshold,
        hierarchy_levels=hierarchy_levels,
    )

    print(
        f'\nSaved {len(saved_paths)} '
        f'expression summary CSVs to: '
        f'{output_dir}'
    )

    if args.verbose:
        for path in saved_paths:
            print(f'    {path}')

    verbose_end_msg()


if __name__ == '__main__':
    main()