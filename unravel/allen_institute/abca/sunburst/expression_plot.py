#!/usr/bin/env python3

"""
Use ``abca_scRNAseq_expression_plot`` or ``rna_exp_plot`` from UNRAVEL to plot
ABCA expression summaries produced by ``abca_scRNAseq_expression_summary`` /
``rna_exp_summary``.

The input should be one wide CSV from either:
    - by_level/
    - by_level_collapsed/

Plots:
    - Dot plot: dot color = mean log2(CPM+1) expression; dot size = percent
      expression above the threshold used by expression_summary.py.
    - Heatmap: mean expression, percent expression, or both.

The script auto-detects genes from columns ending in ``_mean_expression``.
For hierarchy-preserving files, row labels default to ``ontology_path``.
For collapsed files, row labels default to ``cell_type``.

Examples:
---------
Plot all human superclusters from a collapsed summary:

    rna_exp_plot \
        -i path/by_level_collapsed/input__level-supercluster_collapsed_expression_summary_thr3.csv

Plot selected cell types and genes:

    rna_exp_plot \
        -i path/input__level-supercluster_collapsed_expression_summary_thr3.csv \
        -ct "Medium spiny neuron" "Eccentric medium spiny neuron" \
        -g DRD1 DRD2

Plot the top 40 clusters ranked by maximum mean expression:

    rna_exp_plot \
        -i path/input__level-cluster_collapsed_expression_summary_thr3.csv \
        -n 40 --rank-by mean

Make only a percent-expression heatmap:

    rna_exp_plot \
        -i path/input__level-supercluster_collapsed_expression_summary_thr3.csv \
        -p heatmap -m percent
"""

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


MEAN_SUFFIX = '_mean_expression'
PERCENT_SUFFIX = '_percent_expression'
EXPRESSING_COUNT_SUFFIX = '_expressing_cell_count'


def parse_args():
    parser = RichArgumentParser(
        formatter_class=SuppressMetavar,
        add_help=False,
        docstring=__doc__,
    )

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument(
        '-i', '--input',
        help='Wide CSV from expression_summary.py by_level or by_level_collapsed.',
        required=True,
        action=SM,
    )

    opts = parser.add_argument_group('Plot selection')
    opts.add_argument(
        '-p', '--plot',
        help='Plot type. Default: both',
        default='both',
        choices=('dotplot', 'heatmap', 'both'),
        action=SM,
    )
    opts.add_argument(
        '-m', '--heatmap-metric',
        help='Heatmap metric. Default: both',
        default='both',
        choices=('mean', 'percent', 'both'),
        action=SM,
    )
    opts.add_argument(
        '-g', '--genes',
        help='Genes to plot. Default: all detected genes.',
        nargs='+',
        default=None,
        action=SM,
    )
    opts.add_argument(
        '-ct', '--cell-types',
        help='Exact cell_type or ontology_path labels to include.',
        nargs='+',
        default=None,
        action=SM,
    )
    opts.add_argument(
        '--contains',
        help='Keep rows whose cell_type or ontology_path contains any supplied text.',
        nargs='+',
        default=None,
        action=SM,
    )
    opts.add_argument(
        '-n', '--top',
        help='Maximum cell types to plot after filtering. Use 0 for all. Default: 50',
        default=50,
        type=int,
        action=SM,
    )
    opts.add_argument(
        '--min-cells',
        help='Minimum cell_count required. Default: 0',
        default=0,
        type=int,
        action=SM,
    )
    opts.add_argument(
        '--rank-by',
        help='Metric used to choose top cell types. Default: mean',
        default='mean',
        choices=('mean', 'percent', 'cells'),
        action=SM,
    )
    opts.add_argument(
        '--sort-by',
        help='Final row order. Default: rank',
        default='rank',
        choices=('rank', 'name', 'cells', 'input'),
        action=SM,
    )
    opts.add_argument(
        '--label-column',
        help='Row-label column, or auto. Default: auto',
        default='auto',
        action=SM,
    )
    opts.add_argument(
        '--show-cell-counts',
        help='Append cell counts to row labels. Default: False',
        action='store_true',
        default=False,
    )

    appearance = parser.add_argument_group('Appearance')
    appearance.add_argument(
        '--mean-max',
        help='Maximum mean-expression color value. Default: data maximum',
        default=None,
        type=float,
        action=SM,
    )
    appearance.add_argument(
        '--percent-max',
        help='Maximum percent-expression color/size value. Default: 100',
        default=100,
        type=float,
        action=SM,
    )
    appearance.add_argument(
        '--size-min',
        help='Minimum dot area. Default: 12',
        default=12,
        type=float,
        action=SM,
    )
    appearance.add_argument(
        '--size-max',
        help='Maximum dot area. Default: 240',
        default=240,
        type=float,
        action=SM,
    )
    appearance.add_argument(
        '--mean-cmap',
        help='Matplotlib colormap for mean expression. Default: magma_r',
        default='magma_r',
        action=SM,
    )

    appearance.add_argument(
        '--percent-cmap',
        help='Matplotlib colormap for percent expression. Default: viridis_r',
        default='viridis_r',
        action=SM,
    )
    appearance.add_argument(
        '--annotate',
        help='Write values inside heatmap cells. Default: False',
        action='store_true',
        default=False,
    )
    appearance.add_argument(
        '--width',
        help='Figure width in inches. Default: automatic',
        default=None,
        type=float,
        action=SM,
    )
    appearance.add_argument(
        '--height',
        help='Figure height in inches. Default: automatic',
        default=None,
        type=float,
        action=SM,
    )
    appearance.add_argument(
        '--title',
        help='Base plot title. Default: derived from the input.',
        default=None,
        action=SM,
    )

    output = parser.add_argument_group('Output')
    output.add_argument(
        '-o', '--output',
        help='Output directory. Default: input_dir/expression_plots',
        default=None,
        action=SM,
    )
    output.add_argument(
        '-op', '--output-prefix',
        help='Output file prefix. Default: input stem',
        default=None,
        action=SM,
    )
    output.add_argument(
        '-f', '--format',
        help='Output format. Default: png',
        default='png',
        choices=('png', 'pdf', 'svg'),
        action=SM,
    )
    output.add_argument(
        '--dpi',
        help='Raster output resolution. Default: 300',
        default=300,
        type=int,
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


def safe_name(value: str) -> str:
    """Convert text to a file-name-safe string."""
    return re.sub(r'[^A-Za-z0-9._-]+', '_', str(value)).strip('_')


def natural_sort_text(value) -> str:
    """Return a zero-padded natural-sort key."""
    text = '' if pd.isna(value) else str(value).lower()
    return re.sub(r'\d+', lambda match: f'{int(match.group()):012d}', text)


def color_cell_type_tick_labels(
    ax: plt.Axes,
    df: pd.DataFrame,
) -> None:
    """Bold and color y-axis cell-type labels."""
    colors = (
        df['cell_type_color'].fillna('').astype(str)
        if 'cell_type_color' in df.columns
        else pd.Series('', index=df.index)
    )

    for tick_label, color in zip(
        ax.get_yticklabels(),
        colors,
    ):
        tick_label.set_fontweight('bold')

        color = color.strip()
        if re.fullmatch(r'#[0-9A-Fa-f]{6}', color):
            tick_label.set_color(color)


def detect_genes(columns: list[str]) -> list[str]:
    """Detect genes from wide mean-expression column names."""
    return [
        column[:-len(MEAN_SUFFIX)]
        for column in columns
        if column.endswith(MEAN_SUFFIX)
    ]


def validate_and_select_genes(
    df: pd.DataFrame,
    requested_genes: list[str] | None,
) -> list[str]:
    """Return requested or detected genes and validate plot metrics."""
    detected = detect_genes(df.columns.tolist())
    if not detected:
        raise ValueError(
            'No gene columns ending in "_mean_expression" were found. '
            'Use a wide by_level or by_level_collapsed CSV.'
        )

    genes = requested_genes if requested_genes is not None else detected
    genes = list(dict.fromkeys(genes))

    missing_genes = [gene for gene in genes if gene not in detected]
    if missing_genes:
        raise ValueError(
            f'Genes not found in the input summary: {missing_genes}. '
            f'Available genes: {detected}'
        )

    missing_columns = []
    for gene in genes:
        for suffix in (MEAN_SUFFIX, PERCENT_SUFFIX):
            column = f'{gene}{suffix}'
            if column not in df.columns:
                missing_columns.append(column)
    if missing_columns:
        raise ValueError(f'Missing required plotting columns: {missing_columns}')

    return genes


def choose_label_column(df: pd.DataFrame, requested: str) -> str:
    """Choose a unique, readable row-label column."""
    if requested != 'auto':
        if requested not in df.columns:
            raise ValueError(f'Label column not found: {requested}')
        return requested

    # Collapsed files contain one row per cell_type and usually include
    # source_path_count/source_ontology_paths.
    if 'source_path_count' in df.columns and 'cell_type' in df.columns:
        return 'cell_type'

    if 'ontology_path' in df.columns:
        return 'ontology_path'

    if 'cell_type' in df.columns:
        return 'cell_type'

    raise ValueError(
        'Could not determine row labels. Expected cell_type or ontology_path.'
    )


def row_rank(df: pd.DataFrame, genes: list[str], rank_by: str) -> pd.Series:
    """Calculate the metric used to select and sort cell types."""
    if rank_by == 'cells':
        return pd.to_numeric(df['cell_count'], errors='coerce').fillna(0)

    suffix = MEAN_SUFFIX if rank_by == 'mean' else PERCENT_SUFFIX
    columns = [f'{gene}{suffix}' for gene in genes]
    return df[columns].apply(pd.to_numeric, errors='coerce').max(axis=1)


def prepare_plot_dataframe(
    df: pd.DataFrame,
    genes: list[str],
    cell_types: list[str] | None,
    contains: list[str] | None,
    min_cells: int,
    top: int,
    rank_by: str,
    sort_by: str,
    label_column: str,
    show_cell_counts: bool,
) -> pd.DataFrame:
    """Filter, rank, sort, and label summary rows for plotting."""
    required = {'cell_type', 'cell_count'}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f'Missing required summary columns: {missing}')

    plot_df = df.copy()
    plot_df['_input_order'] = np.arange(len(plot_df))
    plot_df['cell_count'] = pd.to_numeric(
        plot_df['cell_count'],
        errors='coerce',
    ).fillna(0)

    plot_df = plot_df[plot_df['cell_count'] >= min_cells].copy()

    searchable_columns = ['cell_type']
    if 'ontology_path' in plot_df.columns:
        searchable_columns.append('ontology_path')

    if cell_types:
        exact_mask = pd.Series(False, index=plot_df.index)
        for column in searchable_columns:
            exact_mask |= plot_df[column].astype(str).isin(cell_types)
        plot_df = plot_df[exact_mask].copy()

    if contains:
        contains_mask = pd.Series(False, index=plot_df.index)
        for text in contains:
            pattern = re.escape(text)
            for column in searchable_columns:
                contains_mask |= plot_df[column].astype(str).str.contains(
                    pattern,
                    case=False,
                    na=False,
                )
        plot_df = plot_df[contains_mask].copy()

    if plot_df.empty:
        raise ValueError('No rows remain after applying the plot filters.')

    plot_df['_rank'] = row_rank(plot_df, genes, rank_by)

    if top < 0:
        raise ValueError('--top must be 0 or greater.')
    if top > 0 and len(plot_df) > top:
        plot_df = plot_df.nlargest(top, '_rank', keep='first').copy()

    if sort_by == 'rank':
        plot_df = plot_df.sort_values('_rank', ascending=False, kind='stable')
    elif sort_by == 'cells':
        plot_df = plot_df.sort_values('cell_count', ascending=False, kind='stable')
    elif sort_by == 'name':
        plot_df['_name_sort'] = plot_df[label_column].map(natural_sort_text)
        plot_df = plot_df.sort_values('_name_sort', kind='stable')
    elif sort_by == 'input':
        plot_df = plot_df.sort_values('_input_order', kind='stable')

    plot_df['_plot_label'] = plot_df[label_column].fillna('NA').astype(str)
    if show_cell_counts:
        plot_df['_plot_label'] = [
            f'{label} (n={int(count):,})'
            for label, count in zip(
                plot_df['_plot_label'],
                plot_df['cell_count'],
            )
        ]

    return plot_df.reset_index(drop=True)


def summary_context(df: pd.DataFrame) -> tuple[str, str, str]:
    """Return species, level, and threshold labels from a summary CSV."""
    species = ''
    level = ''
    threshold = ''

    if 'species' in df.columns and not df['species'].dropna().empty:
        species = str(df['species'].dropna().iloc[0])
    if 'level' in df.columns and not df['level'].dropna().empty:
        level = str(df['level'].dropna().iloc[0])
    if 'threshold' in df.columns and not df['threshold'].dropna().empty:
        threshold_value = pd.to_numeric(
            df['threshold'].dropna().iloc[0],
            errors='coerce',
        )
        threshold = (
            f'{threshold_value:g}'
            if pd.notna(threshold_value)
            else str(df['threshold'].dropna().iloc[0])
        )

    return species, level, threshold


def default_title(df: pd.DataFrame, custom_title: str | None) -> str:
    """Create a base title from summary metadata."""
    if custom_title:
        return custom_title

    species, level, _ = summary_context(df)
    collapsed = 'source_path_count' in df.columns

    parts = []
    if species:
        parts.append(species.capitalize())
    if level:
        parts.append(level.replace('_', ' '))
    if collapsed:
        parts.append('collapsed')
    parts.append('expression')

    return ' '.join(parts)


def automatic_figure_size(
    n_rows: int,
    n_genes: int,
    width: float | None,
    height: float | None,
) -> tuple[float, float]:
    """Choose a readable figure size while allowing explicit overrides."""
    auto_width = min(60, max(10, 0.70 * n_genes + 8.0))
    auto_height = min(60, max(4, 0.30 * n_rows + 2.2))
    return width or auto_width, height or auto_height


def matrix_for_metric(
    df: pd.DataFrame,
    genes: list[str],
    suffix: str,
) -> np.ndarray:
    """Return a numeric cell-type by gene matrix."""
    columns = [f'{gene}{suffix}' for gene in genes]
    return df[columns].apply(pd.to_numeric, errors='coerce').to_numpy()


def finite_max(values: np.ndarray, fallback: float = 1.0) -> float:
    """Return a positive finite maximum suitable for a color scale."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return fallback
    value = float(finite.max())
    return value if value > 0 else fallback


def save_figure(
    fig: plt.Figure,
    output_path: Path,
    dpi: int,
) -> None:
    """Save and close a Matplotlib figure."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches='tight')
    plt.close(fig)


def plot_dotplot(
    df: pd.DataFrame,
    genes: list[str],
    title: str,
    output_path: Path,
    threshold: str,
    width: float | None,
    height: float | None,
    mean_max: float | None,
    percent_max: float,
    size_min: float,
    size_max: float,
    mean_cmap: str,
    dpi: int,
) -> None:
    """Plot mean expression as color and percent expression as dot size."""
    if percent_max <= 0:
        raise ValueError('--percent-max must be greater than 0.')
    if size_min < 0 or size_max <= 0 or size_max < size_min:
        raise ValueError('Dot sizes must satisfy 0 <= size-min <= size-max.')

    mean_matrix = matrix_for_metric(df, genes, MEAN_SUFFIX)
    percent_matrix = matrix_for_metric(df, genes, PERCENT_SUFFIX)

    n_rows, n_genes = mean_matrix.shape
    figure_size = automatic_figure_size(
        n_rows,
        n_genes,
        width,
        height,
    )
    fig = plt.figure(figsize=figure_size, constrained_layout=True)
    grid = fig.add_gridspec(
        1,
        3,
        width_ratios=(max(2.5, 0.7 * n_genes), 0.18, 1.5),
        wspace=0.45,
    )
    ax = fig.add_subplot(grid[0, 0])
    colorbar_ax = fig.add_subplot(grid[0, 1])
    legend_ax = fig.add_subplot(grid[0, 2])
    legend_ax.axis('off')

    x_grid, y_grid = np.meshgrid(
        np.arange(n_genes),
        np.arange(n_rows),
    )
    valid = np.isfinite(mean_matrix) & np.isfinite(percent_matrix)

    clipped_percent = np.clip(percent_matrix, 0, percent_max)
    dot_sizes = size_min + (
        clipped_percent / percent_max
    ) * (size_max - size_min)

    vmax = mean_max if mean_max is not None else finite_max(mean_matrix)
    scatter = ax.scatter(
        x_grid[valid],
        y_grid[valid],
        c=mean_matrix[valid],
        s=dot_sizes[valid],
        cmap=mean_cmap,
        vmin=0,
        vmax=vmax,
        linewidths=0.25,
        edgecolors='black',
    )

    ax.set_xticks(np.arange(n_genes))
    ax.set_xticklabels(genes, rotation=45, ha='right')
    ax.set_yticks(np.arange(n_rows))
    ax.set_yticklabels(df['_plot_label'])
    color_cell_type_tick_labels(ax, df)
    ax.set_xlim(-0.5, n_genes - 0.5)
    ax.set_ylim(n_rows - 0.5, -0.5)
    ax.set_xlabel('Gene')
    ax.set_ylabel('Cell type', fontweight='bold')
    ax.set_title(
        f'{title}: dot plot',
        fontweight='bold',
    )
    ax.set_axisbelow(True)
    ax.grid(True, axis='both', linewidth=0.35, alpha=0.35)

    colorbar = fig.colorbar(scatter, cax=colorbar_ax)
    colorbar.set_label('Mean log2(CPM+1) expression')

    legend_values = np.linspace(0, percent_max, 5)
    legend_handles = []
    for value in legend_values:
        size = size_min + (value / percent_max) * (size_max - size_min)
        legend_handles.append(
            Line2D(
                [],
                [],
                marker='o',
                linestyle='None',
                markerfacecolor='none',
                markeredgecolor='black',
                markersize=np.sqrt(size),
                label=f'{value:g}%',
            )
        )

    legend_title = (
        f'Percent > {threshold}'
        if threshold else 'Percent expression'
    )
    legend_ax.legend(
        handles=legend_handles,
        title=legend_title,
        loc='center',
        frameon=False,
    )

    save_figure(fig, output_path, dpi)


def plot_heatmap(
    df: pd.DataFrame,
    genes: list[str],
    metric: str,
    title: str,
    output_path: Path,
    threshold: str,
    width: float | None,
    height: float | None,
    mean_max: float | None,
    percent_max: float,
    mean_cmap: str,
    percent_cmap: str,
    annotate: bool,
    dpi: int,
) -> None:
    """Plot a mean- or percent-expression heatmap."""
    if metric == 'mean':
        suffix = MEAN_SUFFIX
        matrix = matrix_for_metric(df, genes, suffix)
        cmap = mean_cmap
        vmax = mean_max if mean_max is not None else finite_max(matrix)
        colorbar_label = 'Mean log2(CPM+1) expression'
        plot_title = f'{title}: mean expression heatmap'
    else:
        suffix = PERCENT_SUFFIX
        matrix = matrix_for_metric(df, genes, suffix)
        cmap = percent_cmap
        vmax = percent_max
        colorbar_label = (
            f'Percent expression > {threshold}'
            if threshold else 'Percent expression'
        )
        plot_title = f'{title}: percent expression heatmap'

    if vmax <= 0:
        raise ValueError('Heatmap color maximum must be greater than 0.')

    n_rows, n_genes = matrix.shape
    figure_size = automatic_figure_size(
        n_rows,
        n_genes,
        width,
        height,
    )
    fig, ax = plt.subplots(figsize=figure_size)

    image = ax.imshow(
        matrix,
        aspect='auto',
        interpolation='nearest',
        cmap=cmap,
        vmin=0,
        vmax=vmax,
    )

    ax.set_xticks(np.arange(n_genes))
    ax.set_xticklabels(genes, rotation=45, ha='right')
    ax.set_yticks(np.arange(n_rows))
    ax.set_yticklabels(df['_plot_label'])
    color_cell_type_tick_labels(ax, df)
    ax.set_xlabel('Gene')
    ax.set_ylabel('Cell type')
    ax.set_title(
        plot_title,
        fontweight='bold',
    )

    colorbar = fig.colorbar(image, ax=ax, pad=0.02)
    colorbar.set_label(colorbar_label)

    if annotate:
        text_color_cutoff = vmax / 2
        for row_index in range(n_rows):
            for gene_index in range(n_genes):
                value = matrix[row_index, gene_index]
                if not np.isfinite(value):
                    continue
                ax.text(
                    gene_index,
                    row_index,
                    f'{value:.1f}',
                    ha='center',
                    va='center',
                    fontsize=7,
                    color='white' if value > text_color_cutoff else 'black',
                )

    fig.tight_layout()
    save_figure(fig, output_path, dpi)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f'Input CSV not found: {input_path}')
    if args.min_cells < 0:
        raise ValueError('--min-cells must be 0 or greater.')
    if args.dpi <= 0:
        raise ValueError('--dpi must be greater than 0.')

    summary_df = pd.read_csv(input_path, low_memory=False)
    genes = validate_and_select_genes(summary_df, args.genes)
    label_column = choose_label_column(summary_df, args.label_column)

    plot_df = prepare_plot_dataframe(
        df=summary_df,
        genes=genes,
        cell_types=args.cell_types,
        contains=args.contains,
        min_cells=args.min_cells,
        top=args.top,
        rank_by=args.rank_by,
        sort_by=args.sort_by,
        label_column=label_column,
        show_cell_counts=args.show_cell_counts,
    )

    output_dir = (
        Path(args.output)
        if args.output is not None
        else input_path.parent / 'expression_plots'
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    output_prefix = args.output_prefix or input_path.stem
    title = default_title(summary_df, args.title)
    _, _, threshold = summary_context(summary_df)

    print(f'\nInput: {input_path}')
    print(f'Genes: {genes}')
    print(f'Rows plotted: {len(plot_df):,}')
    print(f'Row labels: {label_column}')
    print(f'Output directory: {output_dir}\n')

    saved_paths = []

    if args.plot in ('dotplot', 'both'):
        dotplot_path = output_dir / (
            f'{output_prefix}__dotplot.{args.format}'
        )
        plot_dotplot(
            df=plot_df,
            genes=genes,
            title=title,
            output_path=dotplot_path,
            threshold=threshold,
            width=args.width,
            height=args.height,
            mean_max=args.mean_max,
            percent_max=args.percent_max,
            size_min=args.size_min,
            size_max=args.size_max,
            mean_cmap=args.mean_cmap,
            dpi=args.dpi,
        )
        saved_paths.append(dotplot_path)

    if args.plot in ('heatmap', 'both'):
        heatmap_metrics = (
            ('mean', 'percent')
            if args.heatmap_metric == 'both'
            else (args.heatmap_metric,)
        )
        for metric in heatmap_metrics:
            heatmap_path = output_dir / (
                f'{output_prefix}__heatmap-{metric}.{args.format}'
            )
            plot_heatmap(
                df=plot_df,
                genes=genes,
                metric=metric,
                title=title,
                output_path=heatmap_path,
                threshold=threshold,
                width=args.width,
                height=args.height,
                mean_max=args.mean_max,
                percent_max=args.percent_max,
                mean_cmap=args.mean_cmap,
                percent_cmap=args.percent_cmap,
                annotate=args.annotate,
                dpi=args.dpi,
            )
            saved_paths.append(heatmap_path)

    print(f'Saved {len(saved_paths)} plot(s):')
    for path in saved_paths:
        print(f'    {path}')

    verbose_end_msg()


if __name__ == '__main__':
    main()
