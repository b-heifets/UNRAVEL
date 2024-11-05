#!/usr/bin/env python3

"""
Use ``./Allen_RNAseq_expression_in_mice.py`` from UNRAVEL to analyze mouse Allen Brain Cell Atlas scRNA-seq expression.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/general_accessing_10x_snRNASeq_tutorial.htmlml

Usage:
------
    ./Allen_RNAseq_expression_in_mice.py -b path/base_dir -i expression_matrices/WMB-10Xv2/20230630/WMB-10Xv2-TH-log2.h5ad [-v]
"""

from pathlib import Path
import anndata
from matplotlib import pyplot as plt
import pandas as pd
from rich import print
from rich.traceback import install

import merfish as m
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the MERFISH data', required=True, action=SM)
    reqs.add_argument('-i', '--input', help='(e.g., Relative path to expression data. E.g., expression_matrices/WMB-10Xv2/20230630/WMB-10Xv2-TH-log2.h5ad', required=True, action=SM)
    # reqs.add_argument('-g', '--gene', help='Gene to analyze', required=True, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def load_RNAseq_mouse_cell_metadata(download_base):
    cell_df = None

    cell_metadata_path = download_base / "metadata/WMB-10X/20231215/cell_metadata.csv"
    if cell_metadata_path.exists():
        print(f"\n    Loading cell metadata from {cell_metadata_path}\n")
        cell_df = pd.read_csv(cell_metadata_path, dtype={'cell_label': str}, 
                                usecols=['cell_label', 'feature_matrix_label', 'region_of_interest_acronym', 'dataset_label', 'x', 'y', 'cluster_alias'])
        
    if cell_df is not None:
        cell_df.set_index('cell_label', inplace=True)
    else:
        print(f"\n    [red1]Cell metadata not loadable from: {cell_metadata_path}\n")
        import sys ; sys.exit()
    return cell_df

def join_region_of_interest_metadata(cell_df, download_base):
    roi_df = None
    roi_metadata_path = download_base / "metadata/WMB-10X/20231215/region_of_interest_metadata.csv"
    if roi_metadata_path.exists():
        print(f"\n    Loading region of interest metadata from {roi_metadata_path}\n")
        roi_df = pd.read_csv(roi_metadata_path, dtype={'acronym': str})
        
    if roi_df is not None:
        roi_df.set_index('acronym', inplace=True)
        roi_df.rename(columns={'order': 'region_of_interest_order',
                    'color_hex_triplet': 'region_of_interest_color'}, inplace=True)
        cell_df_joined = cell_df.join(roi_df[['region_of_interest_order', 'region_of_interest_color']], on='region_of_interest_acronym')
        
    else:
        print(f"\n    [red1]Region of interest metadata not loadable from: {roi_metadata_path}\n")
        import sys ; sys.exit()
    return cell_df_joined

def plot_umap(xx, yy, cc=None, val=None, fig_width=8, fig_height=8, cmap=None):

    fig, ax = plt.subplots()
    fig.set_size_inches(fig_width, fig_height)
    
    if cmap is not None :
        plt.scatter(xx, yy, s=0.5, c=val, marker='.', cmap=cmap)
    elif cc is not None :
        plt.scatter(xx, yy, s=0.5, color=cc, marker='.')
        
    ax.axis('equal')
    ax.set_xlim(-18, 27)
    ax.set_ylim(-18, 27)
    ax.set_xticks([])
    ax.set_yticks([])
    
    return fig, ax

def load_mouse_RNAseq_gene_metadata(download_base):
    gene_metadata_path = download_base / "metadata/WMB-10X/20231215/gene.csv"
    if gene_metadata_path.exists():
        print(f"\n    Loading gene metadata from {gene_metadata_path}\n")
        gene_df = pd.read_csv(gene_metadata_path)
        gene_df.set_index('gene_identifier', inplace=True)
    else:
        print(f"\n    [red1]Gene metadata not found at {gene_metadata_path}\n")
        import sys ; sys.exit()
    return gene_df

def create_expression_dataframe(ad, gf, cell_filtered):
    gdata = ad[:, gf.index].to_df()
    gdata.columns = gf.gene_symbol
    exp_df = cell_filtered.join(gdata)
    return exp_df

def aggregate_by_metadata(df, gnames, value, sort=False):
    grouped = df.groupby(value)[gnames].mean()
    if sort:
        grouped = grouped.sort_values(by=gnames[0], ascending=False)
    return grouped

def plot_heatmap(df, fig_width = 8, fig_height = 4, cmap=plt.cm.magma_r, vmax=None):

    arr = df.to_numpy()

    fig, ax = plt.subplots()
    fig.set_size_inches(fig_width, fig_height)

    res = ax.imshow(arr, cmap=cmap, aspect='auto', vmax=vmax)
    xlabs = df.columns.values
    ylabs = df.index.values

    ax.set_xticks(range(len(xlabs)))
    ax.set_xticklabels(xlabs)

    ax.set_yticks(range(len(ylabs)))
    res = ax.set_yticklabels(ylabs)

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    # Load the cell metadata
    cell_df = load_RNAseq_mouse_cell_metadata(download_base) 

    # Add: 'neurotransmitter', 'class', 'subclass', 'supertype', 'cluster'
    cell_df_joined = m.join_cluster_details(cell_df, download_base) 

    # Example of plotting the UMAP coordinates colored by neurotransmitter identity
    # cell_df_joined = m.join_cluster_colors(cell_df_joined, download_base)
    # cell_df_joined = join_region_of_interest_metadata(cell_df_joined, download_base)
    # cell_subsampled = cell_df_joined.loc[::10]
    # fig, ax = plot_umap(cell_subsampled['x'], cell_subsampled['y'], cc=cell_subsampled['neurotransmitter_color'])
    # res = ax.set_title("Neuortransmitter Identity")
    # plt.show()

    # Load expression data
    expression_data_path = download_base / args.input
    if not expression_data_path.exists():
        print(f"\n    [red1]Expression data not found at {expression_data_path}\n")
        return
    adata = anndata.read_h5ad(expression_data_path, backed='r')
    

    # expression_matrices/WMB-10Xv2/20230630/WMB-10Xv2-TH-log2.h5ad

    # Connect the cells with expression data to the cell metadata
    feature_matrix_label = str(Path(args.input).name).replace('-log2.h5ad', '')
    pred = (cell_df_joined['feature_matrix_label'] == feature_matrix_label)
    cell_filtered = cell_df_joined[pred]

    ntgenes = ['Slc17a7', 'Slc17a6', 'Slc17a8', 'Slc32a1', 'Slc6a5', 'Slc18a3', 'Slc6a3', 'Slc6a4', 'Slc6a2']
    exgenes = ['Tac2']
    gnames = ntgenes + exgenes
    pred = [x in gnames for x in adata.var.gene_symbol]
    gene_filtered = adata.var[pred]

    print("    Loading expression data for genes:")
    asubset = adata[:, gene_filtered.index].to_memory()
    print(asubset)

    pred = [x in ntgenes for x in asubset.var.gene_symbol]
    gf = asubset.var[pred]

    exp_df = create_expression_dataframe(asubset, gf, cell_filtered)
    agg = aggregate_by_metadata(exp_df, gf.gene_symbol, 'neurotransmitter')
    plot_heatmap(df=agg, fig_width=8, fig_height=3, vmax=10)
    plt.show()


    verbose_end_msg()

if __name__ == '__main__':
    main()