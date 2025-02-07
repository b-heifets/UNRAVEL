#!/usr/bin/env python3

"""
Use ``./RNAseq_expression_in_mice_heatmap.py`` from UNRAVEL to join cell metadata with scRNA-seq expression data.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/general_accessing_10x_snRNASeq_tutorial.html
    - By default, expression data is collected frmo the WMB-10Xv3, WMB-10Xv2, and WMB-10XMulti datasets.

Next steps:
    - RNAseq_filter.py

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
    opts.add_argument('-d', '--data_set', help='The dataset to use (all \[default], CB, CTXsp, HPF, HY, Isocortex, MB, MY, OLF, P, PAL, STR, TH)', default='all', nargs='+', action=SM)
    opts.add_argument('-e', '--extra_cols', help='Include extra columns in the cell metadata (e.g., x and y). Default: False', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

@print_func_name_args_times()
def load_RNAseq_mouse_cell_metadata(download_base, extra_cols=False):
    cell_metadata_path = download_base / "metadata/WMB-10X/20231215/cell_metadata.csv"
    if extra_cols: 
        cell_df = pd.read_csv(cell_metadata_path, dtype={'cell_label': str},
                            usecols=['cell_label', 'feature_matrix_label', 'region_of_interest_acronym', 
                                    'x', 'y', 'cluster_alias'])
    else:
        cell_df = pd.read_csv(cell_metadata_path, dtype={'cell_label': str},
                            usecols=['cell_label', 'feature_matrix_label', 'region_of_interest_acronym', 'cluster_alias'])

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
    cell_df = load_RNAseq_mouse_cell_metadata(download_base, extra_cols=args.extra_cols)

    # Add: 'neurotransmitter', 'class', 'subclass', 'supertype', 'cluster'
    if args.extra_cols:
        cell_df = m.join_cluster_details(cell_df, download_base) 

    # Create empty gene expression dataframe
    gene_df = load_mouse_RNAseq_gene_metadata(download_base)
    pred = [x in args.genes for x in gene_df.gene_symbol]
    gene_filtered = gene_df[pred]
    gdata = pd.DataFrame(index=cell_df.index, columns=gene_filtered.index)
    
    # Initialize an empty list to store each exp_df for concatenation later
    exp_dfs = []
    expression_matrices_dir = download_base / 'expression_matrices'
    list_of_paths_to_expression_matrices = []
    if args.data_set == 'all':
        list_of_paths_to_expression_matrices = list(expression_matrices_dir.rglob('WMB-10X*/**/*-log2.h5ad'))
    else:
        list_of_paths_to_expression_matrices.append(expression_matrices_dir / 'WMB-10XMulti/20230830/WMB-10XMulti-log2.h5ad')
        v3_prefix = 'WMB-10Xv3/20230630/WMB-10Xv3-'
        v2_prefix = 'WMB-10Xv2/20230630/WMB-10Xv2-'
        suffix = '-log2.h5ad'
        
        datasets = [args.data_set] if isinstance(args.data_set, str) else args.data_set  # Convert to list if str

        v3_paths = [expression_matrices_dir / f"{v3_prefix}{dataset}{suffix}" for dataset in datasets]
        v2_paths = [expression_matrices_dir / f"{v2_prefix}{dataset}{suffix}" for dataset in datasets]

        list_of_paths_to_expression_matrices.extend(v3_paths)
        list_of_paths_to_expression_matrices.extend(v2_paths)
    
    for file in list_of_paths_to_expression_matrices:

        print(f"\n    Loading expression data from {file}\n")

        # Connect the cells with expression data to the cell metadata
        matrix_prefix = str(file.name).replace('-log2.h5ad', '')
        cell_filtered = cell_df[cell_df['feature_matrix_label'] == matrix_prefix]
        
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
    cell_df_joined_w_exp = cell_df.join(gdata, how="inner")

    if not args.extra_cols:
        cell_df_joined_w_exp.drop(columns=['feature_matrix_label'], inplace=True)

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