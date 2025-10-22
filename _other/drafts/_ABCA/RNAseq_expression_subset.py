#!/usr/bin/env python3

"""
Use ``abca_scRNAseq_expression_subset`` or ``rna_subset`` from UNRAVEL to quickly load a subset of genes from scRNA-seq expression data from the Allen Brain Cell Atlas.

Prereqs:
    - Use ``abca_cache`` to download the expression matrices and metadata.
    - Use h5ad_to_dense_zarr.py to convert the h5ad files to dense Zarr format for faster loading of genes (chunks optimized for gene-wise access).

Output:
    - A CSV file with the expression data for the selected genes, indexed by cell_label.
    - Cell metadata columns: feature_matrix_label, region_of_interest_acronym, x, y, cluster_alias.    

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/general_accessing_10x_snRNASeq_tutorial.html

Next steps:
    - ``abca_scRNAseq_filter`` to filter cells based on metadata.
    - ``abca_sunburst`` to generate sunburst plots of cell type proportions.
    - ``abca_sunburst_expression`` to generate sunburst plots of gene expression.

Usage:
------
    abca_scRNAseq_expression -b path/base_dir -g genes [-s mouse | human] [-c neurons | nonneurons] [-d log2 | raw ] [-o output] [-v]

Usage for humans:
-----------------
    abca_scRNAseq_expression -b path/base_dir -g genes -c neurons [-o output_dir] [-v]

Usage for mice:
---------------
    abca_scRNAseq_expression -b path/base_dir -g genes [-o output_dir] [-v]
"""

from typing import List
import anndata

import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

import unravel.allen_institute.abca.merfish.merfish as mf
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

from adata.load_dense_zarr_dask import lazy_load_genes

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)
    reqs.add_argument('-g', '--genes', help='Space-separated list of genes to extract expression data for.', nargs='*', required=True, action=SM)
    
    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-s', '--species', help='Species to use (human or mouse). Default: mouse', default='mouse', action=SM)
    opts.add_argument('-c', '--cell_type', help='Cell type to use (neurons or nonneurons). Default: None', default=None, action=SM)
    opts.add_argument('-o', '--output', help='Path to output CSV file.', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Should load_RNAseq_cell_metadata and load_RNAseq_gene_metadata be moved to a separate module?

def load_RNAseq_cell_metadata(download_base, species='mouse'):
    """
    Load the cell metadata from the RNA-seq data.

    Parameters
    ----------
    download_base : Path
        The base directory where the data is downloaded.
    species : str
        The species to use (human or mouse). Default: 'mouse'.

    Returns
    -------
    cell_df : pd.DataFrame
        The cell metadata dataframe. Index: cell_label. Columns: feature_matrix_label, region_of_interest_acronym, x, y, cluster_alias.
    """
    if species == 'mouse':
        cell_metadata_path = download_base / "metadata/WMB-10X/20231215/cell_metadata.csv"
        cols = ['cell_label', 'feature_matrix_label', 'region_of_interest_acronym', 'x', 'y', 'cluster_alias']
    else:
        cell_metadata_path = download_base / "metadata/WHB-10Xv3/20240330/cell_metadata.csv"
        cols = ['cell_label', 'feature_matrix_label', 'region_of_interest_label', 'x', 'y', 'cluster_alias']

    if cell_metadata_path.exists():
        print(f"\n    Loading cell metadata from {cell_metadata_path}\n")
        cell_df = pd.read_csv(cell_metadata_path, dtype={'cell_label': str}, usecols=cols)
        cell_df.set_index('cell_label', inplace=True)
        if species == 'human':
            cell_df.rename(columns={'region_of_interest_label': 'region_of_interest_acronym'}, inplace=True)
    else:
        raise FileNotFoundError(f"\nCell metadata not found at {cell_metadata_path}\n")
    return cell_df

def load_RNAseq_gene_metadata(download_base, species='mouse'):
    """
    Load the gene metadata from the RNA-seq data.

    Parameters
    ----------
    download_base : Path
        The base directory where the data is downloaded.
    species : str
        The species to use (human or mouse). Default: 'mouse'.

    Returns
    -------
    gene_df : pd.DataFrame
        The gene metadata dataframe. Index: gene_identifier. Columns: gene_symbol
    """
    if species == 'mouse':
        gene_metadata_path = download_base / "metadata/WMB-10X/20231215/gene.csv"
    else:
        gene_metadata_path = download_base / "metadata/WHB-10Xv3/20240330/gene.csv"
    if gene_metadata_path.exists():
        print(f"\n    Loading gene metadata from {gene_metadata_path}\n")
        gene_df = pd.read_csv(gene_metadata_path, usecols=['gene_identifier', 'gene_symbol']) # Other columns: Both: name; Human: biotype; Mouse: mapped_ncbi_identifier, comment
        gene_df.set_index('gene_identifier', inplace=True)
    else:
        raise FileNotFoundError(f"\nGene metadata not found at {gene_metadata_path}\n")
    return gene_df

def load_expression_from_zarr(file, gene_list):
    """Load and return a DataFrame of selected genes from a single Zarr file."""
    adata = lazy_load_genes(file, gene_list)
    df = adata.to_df()
    df.index = adata.obs_names  # Set cell labels as the index
    df.columns = gene_list
    return df  # locals (adata, df) freed automatically after return

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    if args.species == 'human':
        valid_cell_types = {"neurons", "nonneurons"}
        if args.cell_type is None or args.cell_type not in valid_cell_types:
            print(f"\n    [red1]Error: Please provide a valid cell type: {valid_cell_types}\n")
            return

    # Load gene metadata. Index: gene_identifier (e.g., ENSMUSG00000034997). Columns: gene_symbol (e.g., Htr2a)
    gene_df = load_RNAseq_gene_metadata(download_base, species=args.species)
    gene_list = [g for g in args.genes if g in gene_df["gene_symbol"].values]

    # Normalize gene names based on species conventions
    if args.species == 'mouse':
        # Mouse gene symbols: capitalize only the first letter (Htr2a)
        gene_list = [g.lower().capitalize() for g in gene_list]
    elif args.species == 'human':
        # Human gene symbols: all uppercase (HTR2A)
        gene_list = [g.upper() for g in gene_list]

    if not gene_list:
        raise ValueError("None of the requested genes found in gene metadata.")

    # Load cell metadata. Index: cell_label. Columns: feature_matrix_label, region_of_interest_acronym, x, y, cluster_alias
    cell_df = load_RNAseq_cell_metadata(download_base, species=args.species)

    # Define the directory containing expression matrices
    expression_matrices_dir = download_base / "expression_matrices"
    ct = args.cell_type.lower() if args.cell_type else None

    # Pattern to match files based on species and cell type
    if args.species == "mouse":
        pattern = "**/WMB-10Xv3-*-log2.zarr"

    # Load human data for neurons, nonneurons, or all cells
    elif args.species == "human":
        if args.cell_type is None:
            # load all if unspecified
            pattern = "**/WHB-10Xv3-*-log2.zarr"
        else:
            
            if ct == "neurons":
                pattern = "**/WHB-10Xv3-Neurons-log2.zarr"
            elif ct == "nonneurons":
                pattern = "**/WHB-10Xv3-Nonneurons-log2.zarr"
            else:
                raise ValueError("For human data, --cell_type must be 'neurons', 'nonneurons', or None.")
    else:
        raise ValueError("Species must be 'mouse' or 'human'.")

    zarr_files = list(expression_matrices_dir.rglob(pattern))  # Converted with h5ad_to_dense_zarr.py
    exp_dfs = []
    for file in zarr_files:
        print(f"    Loading expression data from {file}")
        matrix_prefix = file.stem.replace('-log2', '')
        cell_filtered = cell_df[cell_df['feature_matrix_label'] == matrix_prefix] # Filter cells for this matrix to join later
        if cell_filtered.empty:
            continue

        print(f"Loading {file.name} ({len(cell_filtered)} matching cells)...")
        exp_df = load_expression_from_zarr(file, gene_list)
        exp_dfs.append(exp_df)

    # Concatenate all gene expression data
    if not exp_dfs:
        raise ValueError("No expression data loaded from Zarr files. Check file paths.")
    
    full_exp_df = pd.concat(exp_dfs, axis=0)
    print(f"\n    Full expression data:\n{full_exp_df}\n")

    # Join with scRNAseq cell metadata
    cell_df_joined = cell_df.join(full_exp_df, how='inner')

    # Add the classification levels and the corresponding color.
    cell_df_joined = mf.join_cluster_details(cell_df_joined, download_base)

    # Add the cluster colors
    cell_df_joined = mf.join_cluster_colors(cell_df_joined, download_base)

    # Filter by cell type for mice if specified
    if args.species == 'mouse' and ct == 'neurons':
        cell_df_joined = cell_df_joined[cell_df_joined['class'].str.split().str[0].astype(int) <= 29]
    elif args.species == 'mouse' and ct == 'nonneurons':
        cell_df_joined = cell_df_joined[cell_df_joined['class'].str.split().str[0].astype(int) > 29]

    print(f"\n    Final expression data with metadata:\n{cell_df_joined}\n")
          
    # Define output file path and save the DataFrame
    if args.output: 
        output_path = Path(args.output)
        if not output_path.suffix == '.csv':
            output_path = output_path / f"{args.species}_RNAseq_expression_subset_{gene_list[0]}.csv"
        output_folder = output_path.parent
        output_folder.mkdir(parents=True, exist_ok=True)
        cell_df_joined.to_csv(output_path, index=False)
        print(f"\n    Saved expression data to {output_path}\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()
