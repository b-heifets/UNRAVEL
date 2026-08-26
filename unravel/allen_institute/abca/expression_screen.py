#!/usr/bin/env python3

"""
Use ``abca_expression_screen`` (``exp_screen``) from UNRAVEL to screen one or
more expression-summary CSVs across ABCA datasets, brain regions, and cell-type
ontology levels.

Inputs:
    - Wide CSVs produced by ``abca_expression_summary`` (``exp_summary``).
    - Cell-level expression CSVs are not analyzed directly. During a directory
      scan, they are skipped with a warning so a directory may contain both
      cell-level inputs and expression summaries.

Default eligibility criteria:
    - cell_count >= 20
    - percent_cells >= 0.1

Within each summary, cell types are ranked separately for every gene by:
    - mean expression
    - cell-type abundance
    - percent expression
    - expressing-cell share

``expressing_cell_share`` is the percentage of all cells in the summarized
input that belong to the cell type and express the gene above the threshold.
It is calculated directly from cell counts when available. With complete
expression values, it is equivalent to:

    percent_cells * percent_expression / 100

For multi-gene panels, expression is aggregated across the selected genes using
the maximum mean expression by default. Use ``--expression-aggregate mean`` to
favor cell types with broader expression across the gene panel.

Outputs:
    - <prefix>_all.csv
        All eligible cell type x gene rows and their within-input ranks.
    - <prefix>_candidates.csv
        Rows in the top N by expression, abundance, or expressing-cell share.
    - <prefix>_panels.csv
        One row per eligible cell type with multi-gene panel rankings.
    - <prefix>_inputs.csv
        One row per screened summary, including the proportion of cells
        represented by the top expression, abundance, and union selections.
    - <prefix>_cross_region.csv
        Recurrence and expression summaries for each cell type x gene across
        regions within a dataset and anatomical granularity.

Notes:
    - ``percent_cells`` represents cell-type representation within the cells in
      each input. For sc/snRNA-seq, it should not automatically be interpreted
      as unbiased tissue abundance.
    - Rank selection occurs after applying both eligibility cutoffs.
    - The abundance ranking is gene-independent within a summary. Individual-
      gene abundance plots are therefore usually redundant.
    - Dataset, region, and anatomical granularity are inferred from the source
      input name and path when possible and are retained as explicit columns.

Usage:
------
    exp_screen -i path/exp_summary_thr3 [-g gene1 gene2 ...] ...
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, match_files, verbose_end_msg, verbose_start_msg


MEAN_SUFFIX = '_mean_expression'
PERCENT_SUFFIX = '_percent_expression'
EXPRESSING_COUNT_SUFFIX = '_expressing_cell_count'

SUMMARY_BASE_COLUMNS = {
    'input',
    'species',
    'threshold',
    'level',
    'cell_type',
    'cell_count',
    'percent_cells',
}

RANK_SPECS = (
    ('mean_expression', 'expression_rank', 'top_expression'),
    ('percent_cells', 'abundance_rank', 'top_abundance'),
    ('percent_expression', 'percent_expression_rank', 'top_percent_expression'),
    (
        'expressing_cell_share',
        'expressing_cell_share_rank',
        'top_expressing_cell_share',
    ),
)

PANEL_RANK_SPECS = (
    ('panel_expression_score', 'panel_expression_rank', 'top_panel_expression'),
    ('percent_cells', 'abundance_rank', 'top_abundance'),
    (
        'max_expressing_cell_share',
        'expressing_cell_share_rank',
        'top_expressing_cell_share',
    ),
)


def parse_args():
    parser = RichArgumentParser(
        formatter_class=SuppressMetavar,
        add_help=False,
        docstring=__doc__,
    )

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument(
        '-i', '--input',
        help="Pattern or patterns for CSV file(s) from `exp_summary`. (e.g., '**/*.csv' for a recursive search)",
        required=True,
        nargs='*',
        action=SM,
    )

    opts = parser.add_argument_group('Screening options')
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
        '-n', '--top',
        help='Top cell types selected per ranking. Use 0 for all. Default: 20',
        default=20,
        type=int,
        action=SM,
    )
    opts.add_argument(
        '--expression-aggregate',
        help='Multi-gene panel expression score (max or mean expression across genes for a given cell type). Default: max',
        default='max',
        choices=('max', 'mean'),
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


def natural_sort_text(value) -> str:
    """Return a zero-padded natural-sort key."""
    text = '' if pd.isna(value) else str(value).lower()
    return re.sub(r'\d+', lambda match: f'{int(match.group()):012d}', text)


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


def select_genes(available: list[str], requested: list[str] | None) -> list[str]:
    """Select genes case-insensitively while preserving source column order."""
    if not requested:
        return available
    requested_keys = {gene.casefold() for gene in requested}
    return [gene for gene in available if gene.casefold() in requested_keys]


def infer_dataset(source_input: str, summary_path: Path, species: str) -> str:
    """Infer a useful dataset label from existing naming conventions."""
    text = f'{source_input} {summary_path}'.lower()
    if 'imputed' in text or re.search(r'(^|[/_])im([/_]|$)', text):
        return 'MERFISH imputed'
    if 'regular_exp' in text or 'merfish' in text:
        return 'MERFISH regular'
    if 'whb' in text:
        return 'human snRNA-seq'
    if 'wmb' in text:
        return 'mouse scRNA-seq'
    if species:
        return f'{species} ABCA'
    return 'ABCA'


def infer_region(source_input: str) -> str:
    """Infer region from region-filtered ABCA input filenames."""
    stem = Path(str(source_input)).stem

    match = re.search(r'__Human_(.+)$', stem, flags=re.IGNORECASE)
    if match:
        return f"Human {match.group(1).replace('_', ' ')}"

    if '__' in stem:
        suffix = stem.rsplit('__', maxsplit=1)[1]
        if suffix:
            return suffix.replace('_', ' ')

    match = re.search(r'_filtered_(.+)$', stem, flags=re.IGNORECASE)
    if match:
        return match.group(1).replace('_', ' ')

    return 'brain-wide'


def infer_anatomical_level(summary_path: Path, region: str) -> str:
    """Infer MERFISH parcellation granularity or scRNA-seq region scope."""
    text = str(summary_path).lower()
    for level in (
        'parcellation_substructure',
        'parcellation_structure',
        'parcellation_division',
    ):
        if level in text:
            return level
    if region == 'brain-wide':
        return 'brain-wide'
    return 'region_of_interest'


def first_nonmissing(series: pd.Series, default=''):
    """Return the first nonmissing series value or a default."""
    nonmissing = series.dropna()
    return nonmissing.iloc[0] if not nonmissing.empty else default


def rank_group(
    group: pd.DataFrame,
    rank_specs: tuple[tuple[str, str, str], ...],
    top: int,
) -> pd.DataFrame:
    """Add deterministic ordinal ranks and top-N flags to one group."""
    ranked = group.copy()
    ranked['_cell_type_sort'] = ranked['cell_type'].map(natural_sort_text)

    for metric, rank_column, top_column in rank_specs:
        order = ranked.sort_values(
            [metric, '_cell_type_sort'],
            ascending=[False, True],
            kind='stable',
            na_position='last',
        ).index
        positions = pd.Series(
            np.arange(1, len(order) + 1),
            index=order,
            dtype='int64',
        )
        ranked[rank_column] = positions.reindex(ranked.index).astype('int64')
        ranked[top_column] = True if top == 0 else ranked[rank_column].le(top)

    return ranked.drop(columns='_cell_type_sort')


def add_selection_reason(
    df: pd.DataFrame,
    flag_to_reason: tuple[tuple[str, str], ...],
) -> pd.Series:
    """Describe which transparent top-N criteria selected each row."""
    reasons = []
    for row in df.itertuples(index=False):
        selected = [
            reason
            for flag, reason in flag_to_reason
            if bool(getattr(row, flag))
        ]
        reasons.append(';'.join(selected))
    return pd.Series(reasons, index=df.index, dtype='string')


def process_summary_file(
    summary_path: Path,
    requested_genes: list[str] | None,
    requested_levels: set[str] | None,
    min_cells: int,
    min_percent_cells: float,
) -> tuple[list[pd.DataFrame], list[dict], list[dict], set[str]]:
    """Convert one wide expression summary to eligible long-form rows."""
    df = pd.read_csv(summary_path, low_memory=False)
    available_genes = summary_genes(df.columns.tolist())
    genes = select_genes(available_genes, requested_genes)
    found_genes = {gene.casefold() for gene in genes}

    if not genes:
        return [], [], [], found_genes

    for column in ('cell_count', 'percent_cells', 'threshold'):
        df[column] = pd.to_numeric(df[column], errors='coerce')

    group_columns = ['input', 'species', 'threshold', 'level']
    long_parts = []
    input_records = []
    evaluation_records = []

    grouped = df.groupby(group_columns, sort=False, dropna=False)
    for group_values, group_df in grouped:
        source_input, species, threshold, level = group_values
        level = str(level)
        if requested_levels and level.casefold() not in requested_levels:
            continue

        source_input = str(source_input)
        species = str(species)
        region = infer_region(source_input)
        dataset = infer_dataset(source_input, summary_path, species)
        anatomical_level = infer_anatomical_level(summary_path, region)
        screen_id = '::'.join(
            (
                str(summary_path.resolve()),
                source_input,
                species,
                str(threshold),
                level,
            )
        )

        group_df = group_df.copy()
        group_df['cell_count'] = pd.to_numeric(
            group_df['cell_count'], errors='coerce'
        ).fillna(0)
        group_df['percent_cells'] = pd.to_numeric(
            group_df['percent_cells'], errors='coerce'
        ).fillna(0)

        total_cells = float(group_df['cell_count'].sum())
        eligible = group_df[
            (group_df['cell_count'] >= min_cells)
            & (group_df['percent_cells'] >= min_percent_cells)
        ].copy()

        common = {
            '_screen_id': screen_id,
            'summary_path': str(summary_path.resolve()),
            'summary_file': summary_path.name,
            'source_input': source_input,
            'dataset': dataset,
            'species': species,
            'threshold': threshold,
            'anatomical_level': anatomical_level,
            'region': region,
            'level': level,
        }

        input_records.append(
            {
                **common,
                'total_cells': total_cells,
                'total_cell_types': len(group_df),
                'eligible_cell_types': len(eligible),
                'eligible_percent_cells_total': eligible['percent_cells'].sum(),
                'genes_screened': len(genes),
                'genes': ';'.join(genes),
            }
        )

        for gene in genes:
            evaluation_records.append({**common, 'gene': gene})

        if eligible.empty:
            continue

        for gene in genes:
            gene_df = eligible.copy()
            gene_df['mean_expression'] = pd.to_numeric(
                gene_df[f'{gene}{MEAN_SUFFIX}'], errors='coerce'
            )
            gene_df['percent_expression'] = pd.to_numeric(
                gene_df[f'{gene}{PERCENT_SUFFIX}'], errors='coerce'
            )

            count_column = f'{gene}{EXPRESSING_COUNT_SUFFIX}'
            if count_column in gene_df.columns:
                gene_df['expressing_cell_count'] = pd.to_numeric(
                    gene_df[count_column], errors='coerce'
                )
            else:
                gene_df['expressing_cell_count'] = (
                    gene_df['cell_count']
                    * gene_df['percent_expression']
                    / 100
                )

            if count_column in gene_df.columns and total_cells > 0:
                gene_df['expressing_cell_share'] = (
                    gene_df['expressing_cell_count']
                    / total_cells
                    * 100
                )
            else:
                gene_df['expressing_cell_share'] = (
                    gene_df['percent_cells']
                    * gene_df['percent_expression']
                    / 100
                )

            gene_df['gene'] = gene
            for column, value in common.items():
                gene_df[column] = value

            optional_columns = [
                column
                for column in (
                    'cell_type_color',
                    'source_path_count',
                    'source_ontology_paths',
                )
                if column in gene_df.columns
            ]
            keep_columns = list(common) + [
                'gene',
                'cell_type',
                *optional_columns,
                'cell_count',
                'percent_cells',
                'expressing_cell_count',
                'mean_expression',
                'percent_expression',
                'expressing_cell_share',
            ]
            long_parts.append(gene_df[keep_columns])

    return long_parts, input_records, evaluation_records, found_genes


def rank_long_table(long_df: pd.DataFrame, top: int) -> pd.DataFrame:
    """Rank cell types separately for every summary and gene."""
    ranked_parts = []
    for _, group in long_df.groupby(['_screen_id', 'gene'], sort=False):
        ranked_parts.append(rank_group(group, RANK_SPECS, top))

    ranked = pd.concat(ranked_parts, ignore_index=True)
    ranked['selected'] = ranked[
        ['top_expression', 'top_abundance', 'top_expressing_cell_share']
    ].any(axis=1)
    ranked['selection_reason'] = add_selection_reason(
        ranked,
        (
            ('top_expression', 'expression'),
            ('top_abundance', 'abundance'),
            ('top_expressing_cell_share', 'expressing_cell_share'),
        ),
    )
    return ranked.sort_values(
        ['dataset', 'anatomical_level', 'region', 'level', 'gene', 'expression_rank'],
        kind='stable',
    ).reset_index(drop=True)


def build_panel_table(
    long_df: pd.DataFrame,
    top: int,
    expression_aggregate: str,
) -> pd.DataFrame:
    """Create one multi-gene ranking row per eligible cell type."""
    rows = []
    group_columns = ['_screen_id', 'cell_type']
    metadata_columns = [
        'summary_path',
        'summary_file',
        'source_input',
        'dataset',
        'species',
        'threshold',
        'anatomical_level',
        'region',
        'level',
        'cell_type_color',
        'source_path_count',
        'source_ontology_paths',
        'cell_count',
        'percent_cells',
    ]

    for (screen_id, cell_type), group in long_df.groupby(
        group_columns, sort=False, dropna=False
    ):
        numeric_expression = pd.to_numeric(
            group['mean_expression'], errors='coerce'
        )
        if numeric_expression.notna().any():
            maximum_index = numeric_expression.idxmax()
            highest_gene = group.loc[maximum_index, 'gene']
            highest_mean = numeric_expression.loc[maximum_index]
        else:
            highest_gene = ''
            highest_mean = np.nan

        if expression_aggregate == 'max':
            panel_score = numeric_expression.max()
        else:
            panel_score = numeric_expression.mean()

        row = {
            '_screen_id': screen_id,
            'cell_type': cell_type,
        }
        for column in metadata_columns:
            if column in group.columns and column not in row:
                row[column] = first_nonmissing(group[column])

        row.update(
            {
                'genes_screened': group['gene'].nunique(),
                'genes': ';'.join(dict.fromkeys(group['gene'].astype(str))),
                'genes_expressed': int(group['percent_expression'].gt(0).sum()),
                'expression_aggregate': expression_aggregate,
                'panel_expression_score': panel_score,
                'highest_expression_gene': highest_gene,
                'highest_mean_expression': highest_mean,
                'max_percent_expression': group['percent_expression'].max(),
                'max_expressing_cell_share': group[
                    'expressing_cell_share'
                ].max(),
            }
        )
        rows.append(row)

    panels = pd.DataFrame(rows)
    ranked_parts = []
    for _, group in panels.groupby('_screen_id', sort=False):
        ranked_parts.append(rank_group(group, PANEL_RANK_SPECS, top))

    panels = pd.concat(ranked_parts, ignore_index=True)
    panels['plot_selected'] = panels[
        ['top_panel_expression', 'top_abundance']
    ].any(axis=1)
    panels['screen_selected'] = panels[
        [
            'top_panel_expression',
            'top_abundance',
            'top_expressing_cell_share',
        ]
    ].any(axis=1)
    panels['selection_reason'] = add_selection_reason(
        panels,
        (
            ('top_panel_expression', 'panel_expression'),
            ('top_abundance', 'abundance'),
            ('top_expressing_cell_share', 'expressing_cell_share'),
        ),
    )
    return panels.sort_values(
        ['dataset', 'anatomical_level', 'region', 'level', 'panel_expression_rank'],
        kind='stable',
    ).reset_index(drop=True)


def selected_cell_type_text(group: pd.DataFrame, flag: str) -> str:
    """Return semicolon-separated selected cell types in rank order."""
    rank_column = {
        'top_panel_expression': 'panel_expression_rank',
        'top_abundance': 'abundance_rank',
        'top_expressing_cell_share': 'expressing_cell_share_rank',
        'plot_selected': 'panel_expression_rank',
        'screen_selected': 'panel_expression_rank',
    }[flag]
    selected = group[group[flag]].sort_values(rank_column, kind='stable')
    return ';'.join(selected['cell_type'].astype(str))


def selected_percent_total(group: pd.DataFrame, flag: str) -> float:
    """Sum cell-type percentages for a nonoverlapping panel selection."""
    return float(group.loc[group[flag], 'percent_cells'].sum())


def build_input_table(
    input_records: list[dict],
    panels: pd.DataFrame,
) -> pd.DataFrame:
    """Summarize coverage and selections once per screened summary input."""
    inputs = pd.DataFrame(input_records)
    selection_rows = []
    for screen_id, group in panels.groupby('_screen_id', sort=False):
        selection_rows.append(
            {
                '_screen_id': screen_id,
                'top_expression_percent_cells_total': selected_percent_total(
                    group, 'top_panel_expression'
                ),
                'top_abundance_percent_cells_total': selected_percent_total(
                    group, 'top_abundance'
                ),
                'top_expressing_share_percent_cells_total': selected_percent_total(
                    group, 'top_expressing_cell_share'
                ),
                'plot_union_percent_cells_total': selected_percent_total(
                    group, 'plot_selected'
                ),
                'screen_union_percent_cells_total': selected_percent_total(
                    group, 'screen_selected'
                ),
                'top_expression_cell_types': selected_cell_type_text(
                    group, 'top_panel_expression'
                ),
                'top_abundance_cell_types': selected_cell_type_text(
                    group, 'top_abundance'
                ),
                'top_expressing_share_cell_types': selected_cell_type_text(
                    group, 'top_expressing_cell_share'
                ),
            }
        )

    if selection_rows:
        inputs = inputs.merge(
            pd.DataFrame(selection_rows),
            on='_screen_id',
            how='left',
            validate='one_to_one',
        )

    return inputs.sort_values(
        ['dataset', 'anatomical_level', 'region', 'level'],
        kind='stable',
    ).reset_index(drop=True)


def joined_unique(values: pd.Series) -> str:
    """Join unique, nonempty values in natural order."""
    unique = {
        str(value)
        for value in values.dropna()
        if str(value).strip()
    }
    return ';'.join(sorted(unique, key=natural_sort_text))


def build_cross_region_table(
    long_df: pd.DataFrame,
    evaluation_records: list[dict],
) -> pd.DataFrame:
    """Aggregate candidate strength and recurrence across regions."""
    group_columns = [
        'dataset',
        'species',
        'threshold',
        'anatomical_level',
        'level',
        'gene',
        'cell_type',
    ]

    rows = []
    for group_values, group in long_df.groupby(
        group_columns, sort=False, dropna=False
    ):
        row = dict(zip(group_columns, group_values))
        top_expression = group[group['top_expression']]
        top_abundance = group[group['top_abundance']]
        top_share = group[group['top_expressing_cell_share']]
        selected = group[group['selected']]
        row.update(
            {
                'inputs_passing_filters': group['_screen_id'].nunique(),
                'regions_passing_filters': group['region'].nunique(),
                'inputs_top_expression': top_expression['_screen_id'].nunique(),
                'regions_top_expression': top_expression['region'].nunique(),
                'inputs_top_abundance': top_abundance['_screen_id'].nunique(),
                'regions_top_abundance': top_abundance['region'].nunique(),
                'inputs_top_expressing_cell_share': top_share[
                    '_screen_id'
                ].nunique(),
                'regions_top_expressing_cell_share': top_share[
                    'region'
                ].nunique(),
                'inputs_selected': selected['_screen_id'].nunique(),
                'regions_selected': selected['region'].nunique(),
                'selected_regions': joined_unique(selected['region']),
                'median_mean_expression': group['mean_expression'].median(),
                'max_mean_expression': group['mean_expression'].max(),
                'median_percent_expression': group['percent_expression'].median(),
                'max_percent_expression': group['percent_expression'].max(),
                'median_percent_cells': group['percent_cells'].median(),
                'max_percent_cells': group['percent_cells'].max(),
                'median_expressing_cell_share': group[
                    'expressing_cell_share'
                ].median(),
                'max_expressing_cell_share': group[
                    'expressing_cell_share'
                ].max(),
            }
        )
        rows.append(row)

    cross_region = pd.DataFrame(rows)

    evaluations = pd.DataFrame(evaluation_records)
    evaluation_columns = [
        'dataset',
        'species',
        'threshold',
        'anatomical_level',
        'level',
        'gene',
    ]
    evaluated = evaluations.groupby(
        evaluation_columns, sort=False, dropna=False
    ).agg(
        inputs_evaluated=('_screen_id', 'nunique'),
        regions_evaluated=('region', 'nunique'),
    ).reset_index()

    cross_region = cross_region.merge(
        evaluated,
        on=evaluation_columns,
        how='left',
        validate='many_to_one',
    )
    cross_region['fraction_regions_selected'] = (
        cross_region['regions_selected']
        / cross_region['regions_evaluated'].replace(0, np.nan)
    )
    cross_region['fraction_regions_top_expression'] = (
        cross_region['regions_top_expression']
        / cross_region['regions_evaluated'].replace(0, np.nan)
    )

    return cross_region.sort_values(
        [
            'dataset',
            'anatomical_level',
            'level',
            'gene',
            'regions_selected',
            'max_mean_expression',
        ],
        ascending=[True, True, True, True, False, False],
        kind='stable',
    ).reset_index(drop=True)


def default_output_dir(
    inputs: list[str],
    min_cells: int,
    min_percent_cells: float,
    top: int,
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
        f'_top{top}'
    )
    return parent / name


def write_outputs(
    output_dir: Path,
    output_prefix: str,
    long_df: pd.DataFrame,
    panels: pd.DataFrame,
    inputs: pd.DataFrame,
    cross_region: pd.DataFrame,
) -> list[Path]:
    """Write all screening tables and return their paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        'all': long_df,
        'candidates': long_df[long_df['selected']].copy(),
        'panels': panels,
        'inputs': inputs,
        'cross_region': cross_region,
    }

    saved_paths = []
    for suffix, table in tables.items():
        output_path = output_dir / f'{output_prefix}_{suffix}.csv'
        table.drop(columns=['_screen_id'], errors='ignore').to_csv(
            output_path, index=False
        )
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
    if args.top < 0:
        raise ValueError('--top must be 0 or greater.')

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

    long_parts = []
    input_records = []
    evaluation_records = []
    found_gene_keys = set()
    for summary_path in summary_paths:
        parts, records, evaluations, found = process_summary_file(
            summary_path=summary_path,
            requested_genes=args.genes,
            requested_levels=requested_levels,
            min_cells=args.min_cells,
            min_percent_cells=args.min_percent_cells,
        )
        long_parts.extend(parts)
        input_records.extend(records)
        evaluation_records.extend(evaluations)
        found_gene_keys.update(found)

    if args.genes:
        missing_genes = [
            gene for gene in args.genes
            if gene.casefold() not in found_gene_keys
        ]
        if missing_genes:
            print(
                '[yellow]Requested genes not found in any screened summary:[/yellow] '
                + ', '.join(missing_genes)
            )

    if not input_records:
        raise ValueError(
            'No summaries matched the requested genes and ontology levels.'
        )
    if not long_parts:
        raise ValueError(
            'No cell types passed the minimum cell-count and percentage cutoffs.'
        )

    long_df = pd.concat(long_parts, ignore_index=True)
    long_df = rank_long_table(long_df, args.top)
    panels = build_panel_table(
        long_df,
        top=args.top,
        expression_aggregate=args.expression_aggregate,
    )
    inputs = build_input_table(input_records, panels)
    cross_region = build_cross_region_table(long_df, evaluation_records)

    output_dir = (
        Path(args.output)
        if args.output is not None
        else default_output_dir(
            args.input,
            args.min_cells,
            args.min_percent_cells,
            args.top,
        )
    )
    saved_paths = write_outputs(
        output_dir=output_dir,
        output_prefix=args.output_prefix,
        long_df=long_df,
        panels=panels,
        inputs=inputs,
        cross_region=cross_region,
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
