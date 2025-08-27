#!/usr/bin/env python3
"""
Use ``abca_merfish_slice`` or ``mf_slice`` from UNRAVEL to plot a MERFISH slice from the Allen Brain Cell Atlas (ABCA).

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/merfish_ccf_registration_tutorial.html#read-in-section-reconstructed-and-ccf-coordinates-for-all-cells
    - The slice index ranges from 05 to 67.
    - Missing slices include: 07 20 21 22 23 34 41 63 65.

Usage for color mode (choose cell_metadata.csv color column):
-------------------------------------------------------------
    abca_merfish_slice -b path/to/base_dir -s 40 -c subclass_color -o slice40_subclass.png

Usage for gene expression mode:
-------------------------------
    abca_merfish_slice -b path/to/base_dir -s 40 -g Htr2a --imputed -o slice40_Htr2a_imputed.png

Usage for overlaying neurons:
-----------------------------
    abca_merfish_slice -b path/to/base_dir -s 40 -g Htr2a --neurons -o slice40_Htr2a_neurons.png
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.allen_institute.abca.merfish import utils, gene_catalog
from unravel.allen_institute.abca.merfish.utils import plot_slice_color, plot_slice_gene
from unravel.core.config import Configuration 
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument("-b", "--base", help="ABCA root directory", required=True, action=SM)
    reqs.add_argument("-s", "--slice", help="Slice index (e.g., 40)", required=True, type=int, action=SM)

    mode = parser.add_argument_group('Required arguments: mode selection (choose one)')
    mode.add_argument("-c", "--color", help="Metadata color column (e.g., subclass_color)", action=SM)
    mode.add_argument("-g", "--gene", help="Gene symbol for expression coloring", action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument("-csv", "--csv", help="Filtered cell_metadata.csv to highlight specific cells. Default: all cells", default=None, action=SM)
    opts.add_argument("-n", "--neurons", help="Restrict cells to neuronal classes (class code ≤ 29).", action="store_true", default=False)
    opts.add_argument("-im", "--imputed", help="Use imputed expression data. Default: False", action="store_true", default=False)

    # Style/plotting options
    style = parser.add_argument_group('Optional args: style/plotting')
    style.add_argument("-aa", "--alpha_all", help="Opacity for all cells (default 1.00)", default=1.00, type=float, action=SM)
    style.add_argument("-as", "--alpha_subset", help="Opacity for subset cells (default 1.00)", default=1.00, type=float, action=SM)
    style.add_argument("-sa", "--size_all", help="Marker size for all cells (default 8.0)", default=8.0, type=float, action=SM)
    style.add_argument("-ss", "--size_subset", help="Marker size for subset cells (default 8.0)", default=8.0, type=float, action=SM)
    style.add_argument("-l", "--legend", help="Draw legend (color mode only)", action="store_true", default=False)
    style.add_argument("-ll", "--legend-loc", help="Legend location. Default: upper right", default="upper right", action=SM)
    style.add_argument("-d", "--dpi", help="Figure DPI when saving (default: 300).", default=300, type=int, action=SM)
    style.add_argument("-t", "--title", help="Custom plot title. Default: MERFISH-CCF Slice <slice> - <gene> Expression", action=SM)

    # Output and misc
    out_misc = parser.add_argument_group('Optional args: output and misc')
    out_misc.add_argument("-o", "--output", help="Save figure to this path; otherwise show.")
    out_misc.add_argument("--check_gene", help="Print whether GENE exists in raw/imputed catalogs and exit.")

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Also allow for non-neuronal filtering. Use load_region_boundaries() from utils.py to show region boundaries. Add better error messages if cache files are missing (e.g., command to create them). Decorate utils functions.

def join_cell_metadata(csv_path, base, neurons_only=False): 
    """Return a fully-joined cell metadata DataFrame."""
    if csv_path is None:
        df = utils.load_cell_metadata(base)  # default behavior
    else:
        df = utils.load_cell_metadata(Path(csv_path))
    df = utils.join_reconstructed_coords(df, base)
    df = utils.join_cluster_details(df, base)
    df = utils.join_cluster_colors(df, base)
    df = utils.join_parcellation_annotation(df, base)
    df = utils.join_parcellation_color(df, base)
    if neurons_only:
        df = utils.filter_neurons(df)  # uses your class<=29 rule inside utils
    return df

def legend_prep(ax, df_section, color_col: str, legend_loc: str):
    """Build a categorical legend using the label column associated with <color_col>."""
    label_col = color_col[:-6] if color_col.endswith("_color") else color_col
    if label_col not in df_section.columns:
        print(f"[yellow]Legend skipped: '{label_col}' column not found in data[/yellow]")
        return
    unique_labels = np.unique(df_section[label_col])
    handles = []
    for label in unique_labels:
        cols = df_section.loc[df_section[label_col] == label, color_col].unique()
        col = cols[0] if cols.size > 0 else "black"
        handles.append(plt.Line2D([0], [0], marker="o", color=col, linestyle="",
                                  markersize=8, label=str(label)))
    if handles:
        ax.legend(handles=handles, title=label_col, loc=legend_loc)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if (args.color is None) == (args.gene is None):
        raise ValueError("You must provide exactly one of --color or --gene.")

    base = Path(args.base)

    # Optional quick check for gene presence and exit
    if args.check_gene:
        raw_ok = gene_catalog.gene_exists(args.check_gene, imputed=False)
        imp_ok = gene_catalog.gene_exists(args.check_gene, imputed=True)
        print({"gene": args.check_gene, "raw": raw_ok, "imputed": imp_ok})
        verbose_end_msg()
        return

    # Load and join either the provided CSV or the full cell metadata
    df = join_cell_metadata(args.csv, base, neurons_only=args.neurons)

    if df.empty:
        print("[red]No cells matched your filter criteria.[/red]")
        return

    if args.color:
        fig, ax = plot_slice_color(
            base,
            args.slice,
            args.color,
            s_all=args.size_all,
            s_subset=args.size_subset,
            alpha_all=args.alpha_all,
            alpha_subset=args.alpha_subset,
            df=df,
            neurons=args.neurons, 
        )
        if args.legend and df is not None and not df.empty:
            legend_prep(ax, utils.filter_brain_section(df, args.slice),
                        args.color, args.legend_loc)
        ax.set_title(args.title if args.title else f"MERFISH-CCF Slice {args.slice} - {args.color}")
    else:
        # Gene expression mode

        # Check if the gene exists in raw or imputed catalogs
        if args.imputed and gene_catalog.gene_exists(args.gene, imputed=True):
            print(f"Using imputed MERFISH data for gene '{args.gene}'")
            use_imputed = True
        elif gene_catalog.gene_exists(args.gene, imputed=False):
            print(f"Using raw MERFISH data for gene '{args.gene}'")
            use_imputed = False
        elif gene_catalog.gene_exists(args.gene, imputed=True):
            print(f"Using imputed MERFISH data for gene '{args.gene}'")
            use_imputed = True
        else:
            raise ValueError(f"Gene '{args.gene}' not found in MERFISH raw or imputed catalogs")

        try:
            fig, ax = plot_slice_gene(
                base,
                args.slice,
                args.gene,
                s_all=args.size_all,
                s_subset=args.size_subset,
                alpha_all=args.alpha_all,
                alpha_subset=args.alpha_subset,
                subset_df=df,
                imputed=use_imputed,  
                neurons=args.neurons, 
            )
        except ValueError as e:
            raise RuntimeError(f"Failed to plot slice for gene {args.gene}: {e}") from e

        ax.set_title(args.title if args.title else f"MERFISH-CCF Slice {args.slice} - {args.gene} Expression")

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.output, dpi=args.dpi)
    else:
        plt.show()

    verbose_end_msg()


if __name__ == '__main__':
    main()