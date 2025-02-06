#!/usr/bin/env python3

"""
Use ``./RNAseq_expression_in_mice_heatmap.py`` from UNRAVEL to join cell metadata with scRNA-seq expression data.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/general_accessing_10x_snRNASeq_tutorial.html

Usage:
------
    ./RNAseq_expression_in_mice_heatmap.py -b path/base_dir -g genes [-o output] [-v]
"""

from pathlib import Path
import anndata
import pandas as pd
from rich import print
from rich.traceback import install

import merfish as m
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)
    reqs.add_argument('-g', '--genes', help='Space-separated list of genes to analyze', required=True, nargs='*', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='path/expression_metrics.csv. Default: cell_metadata_<gene>.csv', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

@print_func_name_args_times()
def load_RNAseq_mouse_cell_metadata(download_base):
    cell_metadata_path = download_base / "metadata/WMB-10X/20231215/cell_metadata.csv"
    cell_df = pd.read_csv(cell_metadata_path, dtype={'cell_label': str},
                          usecols=['cell_label', 'feature_matrix_label', 'region_of_interest_acronym', 
                                   'x', 'y', 'cluster_alias'])
    cell_df.set_index('cell_label', inplace=True)
    return cell_df

@print_func_name_args_times()
def load_mouse_RNAseq_gene_metadata(download_base):
    gene_metadata_path = download_base / "metadata/WMB-10X/20231215/gene.csv"
    gene_df = pd.read_csv(gene_metadata_path)
    gene_df.set_index('gene_identifier', inplace=True)
    return gene_df

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

    # Create empty gene expression dataframe
    gene_df = load_mouse_RNAseq_gene_metadata(download_base)
    pred = [x in args.genes for x in gene_df.gene_symbol]
    gene_filtered = gene_df[pred]
    gdata = pd.DataFrame(index=cell_df_joined.index, columns=gene_filtered.index)
    
    # Initialize an empty list to store each exp_df for concatenation later
    exp_dfs = []
    expression_matrices_dir = download_base / 'expression_matrices'
    list_of_paths_to_expression_matrices = list(expression_matrices_dir.rglob('WMB-10X*/**/*-log2.h5ad'))
    for file in list_of_paths_to_expression_matrices:

        print(f"\n    Loading expression data from {file}\n")

        # Connect the cells with expression data to the cell metadata
        matrix_prefix = str(file.name).replace('-log2.h5ad', '')
        cell_filtered = cell_df_joined[cell_df_joined['feature_matrix_label'] == matrix_prefix]
        
        # Load the expression data
        ad = anndata.read_h5ad(file, backed='r')
        exp_df = ad[cell_filtered.index, gene_filtered.index].to_df()
        exp_df.columns = gene_filtered.gene_symbol  # Set gene symbols as column names

        # Append this exp_df to the list for concatenation later
        exp_dfs.append(exp_df)
        ad.file.close()
        del ad

    # Concatenate all exp_dfs into a single DataFrame along the rows
    gdata = pd.concat(exp_dfs, axis=0)

    # Remove rows with no expression data
    pred = pd.notna(gdata[gdata.columns[0]])
    gdata = gdata[pred].copy(deep=True)

    # Join the full concatenated gene expression data with the cell metadata
    cell_df_joined_w_exp = cell_df_joined.join(gdata, how="inner")

    # Save the joined cell metadata with expression data
    if args.output is not None:
        output = args.output
    else:
        if len(args.genes) == 1:
            output = f"scRNAseq_WMB_{args.genes[0]}.csv"
        elif len(args.genes) == 2:
            output = f"scRNAseq_WMB_{args.genes[0]}_{args.genes[1]}.csv"
        elif len(args.genes) == 3:
            output = f"scRNAseq_WMB_{args.genes[0]}_{args.genes[1]}_{args.genes[2]}.csv"
        else:
            output = "scRNAseq_WMB_w_exp.csv"
        output_path = Path().cwd() / output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cell_df_joined_w_exp.to_csv(output_path)

    verbose_end_msg()

if __name__ == '__main__':
    main()