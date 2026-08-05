#!/usr/bin/env python3

"""
Use ``abca_scRNAseq_expression`` ()``rna_exp`` from UNRAVEL to extract expression data for specific genes from the ABCA.

Inputs:
    - Cell metadata from the Allen Brain Cell Atlas (use ``abca_cache`` to download).
    - Gene metadata from the Allen Brain Cell Atlas (use ``abca_cache`` to download).
    - Expression data from the Allen Brain Cell Atlas (use ``abca_cache`` to download).

Outputs:
    - A CSV file with the expression data for the selected genes, indexed by cell_label.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/general_accessing_10x_snRNASeq_tutorial.html
    - Only the first gene in the list will be used to name the output file.
    - For humans, the cell type must be specified (Neurons or Nonneurons).
    - For mice, optionally filter neurons or nonneurons with ``abca_scRNAseq_filter`` after joining cell metadata and expression data using ``abca_scRNAseq_join_gene``.
    - The output will be a CSV file with the expression data for the selected genes, indexed by cell_label.

Usage:
------
    abca_scRNAseq_expression -b path/base_dir -g genes [-s mouse | human] [-c Neurons | Nonneurons] [-r region] [-d log2 | raw ] [-o output] [-v]

Usage for humans:
-----------------
    abca_scRNAseq_expression -b path/base_dir -g genes -c Neurons [-o output_dir] [-v]

Usage for mice:
---------------
    abca_scRNAseq_expression -b path/base_dir -g genes [-r region] [-o output_dir] [-v]
"""

from typing import List
import anndata
import h5py
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install
import scipy


import unravel.allen_institute.abca.merfish.merfish as mf
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)
    reqs.add_argument('-g', '--genes', help='Genes to extract expression data for.', nargs='*', required=True, action=SM)
    
    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-s', '--species', help='Species to use (human or mouse). Default: human', default='human', action=SM)
    opts.add_argument('-c', '--cell_type', help='Cell type to extract data from for humans (Neurons or Nonneurons)', default=None, action=SM)
    opts.add_argument('-r', '--region', help='Region to use for mice (OLF, CTXsp, Isocortex-1, Isocortex-2, HPF, STR, PAL, TH, HY, MB, MY, P, CB). Default: all regions', default=None, action=SM)
    opts.add_argument('-o', '--output', help='Path to output folder for the expression data. Default: current directory', default='.', action=SM)
    opts.add_argument('-l', '--less-metadata', help='Include less metadata in the output (omit cluster annotations and colors).', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: loading expression data is slow (loads whoe dataset). It might be optimized by changing the orientation of the data (CSR to CSC) once, and then perhaps slices of data can be loaded instead of the whole dataset.
# TODO: Add the ability to filter neurons vs nonneurons for mice here too?
# TODO: Save the cell_label column too

def load_RNAseq_cell_metadata(download_base, species='mouse'):
    """
    Load the cell metadata from the RNA-seq data.

    Parameters
    ----------
    download_base : Path
        The base directory where the data is downloaded.
    species : str
        The species to use (human or mouse). Default: 'human'.

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
        print(f"\n    [red1]Cell metadata not found at {cell_metadata_path}\n")
        import sys ; sys.exit()
    return cell_df

def load_RNAseq_gene_metadata(download_base, species='human'):
    """
    Load the gene metadata from the RNA-seq data.

    Parameters
    ----------
    download_base : Path
        The base directory where the data is downloaded.
    species : str
        The species to use (human or mouse). Default: 'human'.

    Returns
    -------
    gene_df : pd.DataFrame
        The gene metadata dataframe. Index: gene_identifier. Columns: gene_symbol, biotype, name.
    """
    if species == 'mouse':
        gene_metadata_path = download_base / "metadata/WMB-10X/20231215/gene.csv"
    else:
        gene_metadata_path = download_base / "metadata/WHB-10Xv3/20240330/gene.csv"
    if gene_metadata_path.exists():
        print(f"\n    Loading gene metadata from {gene_metadata_path}\n")
        gene_df = pd.read_csv(gene_metadata_path)
        gene_df.set_index('gene_identifier', inplace=True)
    else:
        print(f"\n    [red1]Gene metadata not found at {gene_metadata_path}\n")
        import sys ; sys.exit()
    return gene_df


def get_gene_data_wo_cache_and_chunking(
    download_base: Path,
    cell_df: pd.DataFrame,
    all_genes: pd.DataFrame,
    selected_genes: List[str],
    species: str = "human",
    region: str = None,
    cell_type: str = None
) -> pd.DataFrame:
    """Load and structure gene expression data directly from RNA-seq data for specific genes.
    
    Parameters
    ----------
    download_base : Path
        The base directory where the data is located.
    cell_df : pandas.DataFrame
        Cell metadata indexed on cell_label.
    all_genes : pandas.DataFrame
        Gene metadata indexed on gene_identifier.
    selected_genes : list of strings
        List of gene_symbols that are a subset of those in the full genes DataFrame.
    species : str
        The species to use (human or mouse). Default: 'human'.
    region : str
        The region to use for mice (OLF, CTXsp, Isocortex-1, Isocortex-2, HPF, STR, PAL, TH, HY, MB, MY, P, CB). Default: None.
    cell_type : str
        The cell type to use for humans (Neurons or Nonneurons). Default: None.

    Returns
    -------
    output_gene_data : pandas.DataFrame
        Subset of gene data indexed by cell.
    """
    # Filter genes
    gene_mask = all_genes.gene_symbol.isin(selected_genes)
    gene_filtered = all_genes[gene_mask]
    if gene_filtered.empty:
        print(f"    [red1]Error: None of the selected genes ({selected_genes}) found in gene metadata.\n")
        import sys; sys.exit()
    
    print(f"\n    Selected genes in gene metadata: {gene_filtered['gene_symbol'].tolist()}\n")
    
    # Path to expression data
    if species == 'mouse':
        # Load expression data from each file and concatenate
        expression_matrices_dir = download_base / 'expression_matrices'
        exp_dfs = []
        # Glob pattern finds all regional mouse files; use WHB for human below
        pattern = 'WMB-10X*/**/*-log2.h5ad'

        for file in expression_matrices_dir.rglob(pattern):
            print(f"    Loading expression data from {file}")
            matrix_prefix = file.stem.replace('-log2', '')
            cell_filtered = cell_df[cell_df['feature_matrix_label'] == matrix_prefix]
            if cell_filtered.empty:
                continue

            ad = anndata.read_h5ad(file, backed='r')


            # DEBUGGING: Check for missing cells and genes
            missing_cells = cell_filtered.index.difference(ad.obs_names)
            missing_genes = gene_filtered.index.difference(ad.var_names)

            print(f"    Cells requested: {len(cell_filtered)}")
            print(f"    Cells in h5ad: {ad.n_obs}")
            print(f"    Missing cells: {len(missing_cells)}")
            print(f"    Missing genes: {missing_genes.tolist()}")
            print(f"    X type: {type(ad.X)}")

            print("\n    --- Environment ---")
            import sys
            print(f"    Python: {sys.version}")
            print(f"    anndata: {anndata.__version__}")
            print(f"    scipy: {scipy.__version__}")
            print(f"    numpy: {np.__version__}")
            print(f"    pandas: {pd.__version__}")
            print(f"    h5py: {h5py.__version__}")

            print("\n    --- AnnData ---")
            print(f"    Shape: {ad.shape}")
            print(f"    Backed: {ad.isbacked}")
            print(f"    X type: {type(ad.X)}")
            print(f"    X shape: {ad.X.shape}")
            print(f"    X dtype: {ad.X.dtype}")
            print(f"    X format: {getattr(ad.X, 'format', None)}")

            print("\n    --- Indexes ---")
            print(f"    ad.obs_names unique: {ad.obs_names.is_unique}")
            print(f"    ad.var_names unique: {ad.var_names.is_unique}")
            print(f"    cell_filtered index unique: {cell_filtered.index.is_unique}")
            print(f"    gene_filtered index unique: {gene_filtered.index.is_unique}")

            test_cell = cell_filtered.index[0]
            test_gene = gene_filtered.index[0]

            cell_position = ad.obs_names.get_loc(test_cell)
            gene_position = ad.var_names.get_loc(test_gene)

            print(f"    Test cell: {test_cell}")
            print(
                f"    Cell position: {cell_position!r}; "
                f"type: {type(cell_position)}"
            )
            print(f"    Test gene: {test_gene}")
            print(
                f"    Gene position: {gene_position!r}; "
                f"type: {type(gene_position)}"
            )

            ### End debugging
            #         

            try:
                exp_df = ad[cell_filtered.index, gene_filtered.index].to_df()
            except KeyError as e:
                print(f"    [yellow1]Skipping {file.name}: {e}")
                ad.file.close()
                continue

            exp_df.columns = gene_filtered['gene_symbol']
            exp_dfs.append(exp_df)

        if not exp_dfs:
            print("\n    [red1]No expression data loaded from any .h5ad files.\n")
            import sys; sys.exit()

        gdata = pd.concat(exp_dfs, axis=0)
        expression_subset = gdata

    elif species == 'human':
        expression_path = download_base / f"expression_matrices/WHB-10Xv3/20240330/WHB-10Xv3-{cell_type}-log2.h5ad"
    
        if not expression_path.exists():
            print(f"[red1]Error: Expression data not found at {expression_path}\n")
            import sys; sys.exit()
        
        print(f"    Loading expression data from {expression_path}")
        expression_data = anndata.read_h5ad(expression_path)
        print("    Data loaded successfully.\n")
        
        # Match cells between metadata and expression data
        print("    Matching cell labels between metadata and expression data...")
        cell_indexes = cell_df.index.intersection(expression_data.obs_names)  # Check for matching cell labels
        if len(cell_indexes) == 0:
            print("\n    [red1]No matching cell labels found. Please check label formats.\n")
            import sys; sys.exit()
        
        print(f"    Number of matching cells: {len(cell_indexes)}")
        
        # Extract expression data for the selected cells and genes
        try:
            print(f"    Extracting expression data for the selected cells and genes...")
            expression_subset = expression_data[cell_indexes, gene_filtered.index].to_df()
            expression_subset.columns = gene_filtered.gene_symbol
            expression_subset.index.name = 'cell_label'
            print(f"    Extracted expression data:\n\n{expression_subset.head()}\n")
        except KeyError as e:
            print(f"\n    [red1]Error extracting data: {e}\n")
            import sys; sys.exit()

        if hasattr(expression_data, 'file'):
            expression_data.file.close()  # Close file only if backed mode is used

    return expression_subset.reset_index()


def load_annotated_cell_metadata(
    download_base,
    species,
    cell_df=None,
):
    """Load cell metadata if needed, then add annotations and colors."""
    if cell_df is None:
        cell_df = load_RNAseq_cell_metadata(download_base, species=species)

    cell_df = mf.join_cluster_details(cell_df, download_base, species)
    cell_df = mf.join_cluster_colors(cell_df, download_base, species)
    return cell_df


def join_cell_metadata(
    exp_df,
    download_base,
    species,
    cell_df=None,
):
    """Join cell metadata to an expression DataFrame."""
    if 'cell_label' in exp_df.columns:
        exp_df = exp_df.set_index('cell_label')
    elif exp_df.index.name != 'cell_label':
        raise ValueError("Expression data must contain a 'cell_label' column or index.")

    cell_df = load_annotated_cell_metadata(
        download_base,
        species,
        cell_df=cell_df,
    )

    return cell_df.reindex(exp_df.index).join(exp_df).reset_index()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    if args.species == 'human':
        valid_cell_types = {"Neurons", "Nonneurons"}
        if args.cell_type is None or args.cell_type not in valid_cell_types:
            print(f"\n    [red1]Error: Please provide a valid cell type: {valid_cell_types}\n")
            return

    cell_df = load_RNAseq_cell_metadata(download_base, species=args.species) # Add option to load cell_metadata_with_cluster_annotation.csv instead? Does this just add extra columns?

    gene_df = load_RNAseq_gene_metadata(download_base, species=args.species)

    # Retrieve expression data for all selected genes at once
    expression_data = get_gene_data_wo_cache_and_chunking(
        download_base, cell_df, gene_df, args.genes, species=args.species, region=args.region, cell_type=args.cell_type
    )

    if not args.less_metadata:
        expression_data = join_cell_metadata(
            expression_data,
            download_base,
            args.species,
            cell_df=cell_df,
        )

    # Check the data before saving to confirm structure
    print(f"\n    Final output data for {args.genes}:\n{expression_data.head()}\n")

    # Define output file path and save the DataFrame
    output_folder = Path(args.output) if args.output != '.' else Path.cwd()
    output_folder.mkdir(parents=True, exist_ok=True)
    if args.species == 'mouse':
        region_label = args.region if args.region else "all_regions"
        output_file = output_folder / f"WMB-10Xv3_{args.genes[0]}_expression_data_{region_label}_log2.csv"
    else:
        if args.region is None:
            output_file = output_folder / f"WHB-10Xv3_{args.genes[0]}_expression_data_{args.cell_type}_log2.csv"
        else:
            output_file = output_folder / f"WHB-10Xv3_{args.genes[0]}_expression_data_{args.cell_type}_{args.region}_log2.csv"

    expression_data.to_csv(output_file, index=False)
    print(f"\n    Saved expression data for gene {args.genes[0]} to {output_file}\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()
