#!/usr/bin/env python3

"""
Use ``./RNAseq_expression_in_mice.py`` from UNRAVEL to analyze mouse Allen Brain Cell Atlas scRNA-seq expression.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/general_accessing_10x_snRNASeq_tutorial.htmlml

Usage:
------
    ./RNAseq_expression_in_mice.py -b path/base_dir -i expression_matrices/WMB-10Xv2/20230630/WMB-10Xv2-TH-log2.h5ad [-v]
"""

from pathlib import Path
import anndata
from matplotlib import pyplot as plt
import pandas as pd
from rich import print
from rich.traceback import install

import unravel.allen_institute.abca.merfish.merfish as mf
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)
    reqs.add_argument('-i', '--input', help='(e.g., Relative path to expression data. E.g., expression_matrices/WMB-10Xv2/20230630/WMB-10Xv2-TH-log2.h5ad', required=True, action=SM)
    reqs.add_argument('-g', '--genes', help='Genes to analyze', required=True, nargs='*', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def load_RNAseq_mouse_cell_metadata(download_base):
    cell_df = None

    cell_metadata_path = download_base / "metadata/WMB-10X/20231215/cell_metadata.csv"
    if cell_metadata_path.exists():
        print(f"\n    Loading cell metadata from {cell_metadata_path}\n")
        cell_df = pd.read_csv(cell_metadata_path, dtype={'cell_label': str}, 
                                usecols=['cell_label', 'library_label', 'feature_matrix_label', 'region_of_interest_acronym', 'dataset_label', 'x', 'y', 'cluster_alias'])
        
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

def plot_heatmap(df, fig_width=8, fig_height=4, cmap=plt.cm.magma_r):

    arr = df.to_numpy()

    fig, ax = plt.subplots()
    fig.set_size_inches(fig_width, fig_height)

    im = ax.imshow(arr, cmap=cmap, aspect='auto', vmin=0, vmax=6)
    xlabs = df.columns.values
    ylabs = df.index.values

    ax.set_xticks(range(len(xlabs)))
    ax.set_xticklabels(xlabs)

    ax.set_yticks(range(len(ylabs)))
    res = ax.set_yticklabels(ylabs)
    
    return im

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
    cell_df_joined = mf.join_cluster_details(cell_df, download_base) 

    # Example of plotting the UMAP coordinates colored by neurotransmitter identity
    # cell_df_joined = mf.join_cluster_colors(cell_df_joined, download_base)
    # cell_df_joined = join_region_of_interest_metadata(cell_df_joined, download_base)
    # cell_subsampled = cell_df_joined.loc[::10]
    # fig, ax = plot_umap(cell_subsampled['x'], cell_subsampled['y'], cc=cell_subsampled['neurotransmitter_color'])
    # res = ax.set_title("Neuortransmitter Identity")
    # plt.show()

    # Load expression data
    # expression_data_path = download_base / args.input
    # if not expression_data_path.exists():
    #     print(f"\n    [red1]Expression data not found at {expression_data_path}\n")
    #     return
    # adata = anndata.read_h5ad(expression_data_path, backed='r')
    

    # expression_matrices/WMB-10Xv2/20230630/WMB-10Xv2-TH-log2.h5ad

    # Connect the cells with expression data to the cell metadata
    # feature_matrix_label = str(Path(args.input).name).replace('-log2.h5ad', '')
    # pred = (cell_df_joined['feature_matrix_label'] == feature_matrix_label)
    # cell_filtered = cell_df_joined[pred]


    # Expression of canonical neurotransmitter transporter genes in the thalamus
    # ntgenes = ['Slc17a7', 'Slc17a6', 'Slc17a8', 'Slc32a1', 'Slc6a5', 'Slc18a3', 'Slc6a3', 'Slc6a4', 'Slc6a2']
    # exgenes = ['Tac2']
    # gnames = ntgenes + exgenes
    # pred = [x in gnames for x in adata.var.gene_symbol]
    # gene_filtered = adata.var[pred]

    # print("    Loading expression data for genes:")
    # asubset = adata[:, gene_filtered.index].to_memory()
    # print(asubset)

    # pred = [x in ntgenes for x in asubset.var.gene_symbol]
    # gf = asubset.var[pred]

    # exp_df = create_expression_dataframe(asubset, gf, cell_filtered)
    # agg = aggregate_by_metadata(exp_df, gf.gene_symbol, 'neurotransmitter')
    # plot_heatmap(df=agg, fig_width=8, fig_height=3, vmax=10)
    # plt.show()


    # Expression of Tachykinin 2 (Tac2) in the thalamus
    # gnames = 'Tac2'
    # pred = [x in gnames for x in adata.var.gene_symbol]
    # gene_filtered = adata.var[pred]

    # asubset = adata[:, gene_filtered.index].to_memory()

    # gf = asubset.var[asubset.var.gene_symbol == 'Tac2']
    # tac2_exp = create_expression_dataframe(asubset, gf, cell_filtered)

    # agg = aggregate_by_metadata(tac2_exp, gf.gene_symbol, 'neurotransmitter', True).head(10)
    # plot_heatmap(agg, 1, 3)
    # plt.show()

    # Grouping cells by cell types class, subclass, supertype, or cluster
    # agg = aggregate_by_metadata(tac2_exp, gf.gene_symbol, 'class', True).head(8)  # Average expression of gene by class
    # plot_heatmap(agg, 1, 3)
    # plt.show()


    # Gene expression matrices
    matrices = cell_df_joined.groupby(['dataset_label', 'feature_matrix_label'])[['library_label']].count()
    # matrices.columns = ['cell_count']

    # example_matrix_file = download_base / 'expression_matrices/WMB-10XMulti/20230830/WMB-10XMulti-log2.h5ad'
    # ad = anndata.read_h5ad(file,backed='r')



    # Create empty gene expression dataframe
    gnames = ['Slc17a7', 'Tac2']
    gene_df = load_mouse_RNAseq_gene_metadata(download_base)
    pred = [x in gnames for x in gene_df.gene_symbol]
    gene_filtered = gene_df[pred]
    gdata = pd.DataFrame(index=cell_df_joined.index, columns=gene_filtered.index)
    
    expression_matrices_dir = download_base / 'expression_matrices'

    # Perhaps a recursive search for all expression matrices would be simpler
    list_of_paths_to_expression_matrices = list(expression_matrices_dir.rglob('WMB-10X*/**/*-log2.h5ad'))

    count = 0  # For testing purposes
    for file in list_of_paths_to_expression_matrices:

        if not file.exists():
            print(f"\n    [red1]Expression data not found at {file}\n")
            return
        print(f"\n    Loading expression data from {file}\n")

        # Connect the cells with expression data to the cell metadata
        matrix_prefix = str(file.name).replace('-log2.h5ad', '')
        pred = (cell_df_joined['feature_matrix_label'] == matrix_prefix)
        cell_filtered = cell_df_joined[pred]
        
        # Load the expression data
        ad = anndata.read_h5ad(file, backed='r')
        exp_df = ad[cell_filtered.index, gene_filtered.index].to_df()
        gdata.loc[ exp_df.index, gene_filtered.index ] = exp_df
        ad.file.close()
        del ad
        
        # For testing purposes
        count += 1
        if count > 2:
            break

    # Change columns from index to gene symbol
    gdata.columns = gene_filtered.gene_symbol
    exp_df.columns = gene_filtered.gene_symbol

    # Remove rows with no expression data
    pred = pd.notna(gdata[gdata.columns[0]])
    gdata = gdata[pred].copy(deep=True)

    # Join the cell metadata with the gene expression data
    exp_df_filtered = exp_df[gnames]
    cell_df_joined_w_exp = cell_df_joined.join(exp_df_filtered)

    # Plot the heatmap of the gene expression data
    agg = aggregate_by_metadata(cell_df_joined_w_exp, gnames, 'neurotransmitter')
    agg = agg[gnames]
    res = plot_heatmap(agg, 8, 3)
    plt.show()

    verbose_end_msg()

if __name__ == '__main__':
    main()