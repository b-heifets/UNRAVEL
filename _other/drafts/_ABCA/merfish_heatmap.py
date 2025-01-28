#!/usr/bin/env python3

"""
Use ``./merfish_heatmap.py`` from UNRAVEL to make a heatmap plot of MERFISH expression data from the Allen Brain Cell Atlas.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/merfish_tutorial_part_2b.html


Usage:
------
    ./merfish_heatmap.py -b path/to/base_dir -g gene -gb groupby [-v]

"""

import anndata
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import SimpleITK as sitk
from pathlib import Path
from rich import print
from rich.traceback import install

import merfish as m
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)
    reqs.add_argument('-g', '--gene', help='Gene to plot.', action=SM)
    reqs.add_argument('-gb', '--groupby', help='The metadata column to group by.', required=True, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


# def aggregate_by_metadata(df, gnames, value, sort=False) :
#     grouped = df.groupby(value)[gnames].mean()
#     if sort :
#         grouped = grouped.sort_values(by=gnames[0], ascending=False)
#     return grouped

def aggregate_by_metadata(df, gnames, value, sort=False):
    grouped = df.groupby(value)[gnames].mean()
    if sort:
        grouped = grouped.sort_values(ascending=False)
    return grouped


def plot_heatmap(df, xlabs, fig_width=4, fig_height=8, cmap=plt.cm.magma_r, vmin=0, vmax=5):
    # Ensure the input is 2D, if it's not, reshape or make it so
    if df.ndim == 1:
        arr = df.to_frame()
    else:
        arr = df.to_numpy()

    fig, ax = plt.subplots()
    fig.set_size_inches(fig_width, fig_height)

    res = ax.imshow(arr, cmap=cmap, aspect='auto', vmin=vmin, vmax=vmax)
    ylabs = df.index.values

    # Set a single x-axis label (the gene name)
    ax.set_xticks([0])
    ax.set_xticklabels([xlabs])  # Pass the gene name as a list containing one element

    ax.set_yticks(range(len(ylabs)))
    res = ax.set_yticklabels(ylabs)

    plt.show()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    # Load the cell metadata
    cell_df = m.load_cell_metadata(download_base)

    # Add the reconstructed coordinates to the cell metadata
    cell_df_joined = m.join_reconstructed_coords(cell_df, download_base)

    # Add the classification levels and the corresponding color.
    cell_df_joined = m.join_cluster_details(cell_df_joined, download_base)

    # Add the cluster colors
    cell_df_joined = m.join_cluster_colors(cell_df_joined, download_base)
    
    # Add the parcellation annotation
    cell_df_joined = m.join_parcellation_annotation(cell_df_joined, download_base)

    # Add the parcellation color
    cell_df_joined = m.join_parcellation_color(cell_df_joined, download_base)

    # Load the expression data for the specified gene
    adata = m.load_expression_data(download_base, args.gene)

    asubset, gf = m.filter_expression_data(adata, args.gene)

    # Create a dataframe with the expression data for the specified gene
    gdata = asubset[:, gf.index].to_df()  # Extract expression data for the gene
    gdata.columns = gf.gene_symbol  # Set the column names to the gene symbols
    exp_df = cell_df_joined.join(gdata)  # Join the cell metadata with the expression data

    print("Expression data columns:")
    print(exp_df.columns)
    print()

    # filtered = exp[args.gene]
    # joined = cell.join(filtered)
    agg = aggregate_by_metadata(exp_df, args.gene, args.groupby, True)
    plot_heatmap(agg, args.gene, 1, 3)

    verbose_end_msg()

if __name__ == '__main__':
    main()