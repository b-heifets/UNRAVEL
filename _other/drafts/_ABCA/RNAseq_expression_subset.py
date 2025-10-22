#!/usr/bin/env python3

"""
Use ``abca_scRNAseq_expression_subset`` or ``rna_exp`` from UNRAVEL to quickly load a subset of genes from scRNA-seq expression data from the Allen Brain Cell Atlas.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/general_accessing_10x_snRNASeq_tutorial.html
    - Only the first gene in the list will be used to name the output file.
    - For humans, the cell type must be specified (Neurons or Nonneurons).
    - For mice, the region must be specified (OLF, CTXsp, Isocortex-1, Isocortex-2, HPF, STR, PAL, TH, HY, MB, MY, P, CB).
    - The output will be a CSV file with the expression data for the selected genes, indexed by cell_label.

Usage:
------
    abca_scRNAseq_expression -b path/base_dir -g genes [-s mouse | human] [-c Neurons | Nonneurons] [-r region] [-d log2 | raw ] [-o output] [-v]

Usage for humans:
-----------------
    abca_scRNAseq_expression -b path/base_dir -g genes -c Neurons [-o output_dir] [-v]

Usage for mice:
---------------
    abca_scRNAseq_expression -b path/base_dir -g genes -r region [-o output_dir] [-v]
"""

from typing import List
import anndata

import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

from adata.load_dense_zarr_dask import lazy_load_genes

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)
    reqs.add_argument('-g', '--genes', help='Genes to extract expression data for.', nargs='*', required=True, action=SM)
    
    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-s', '--species', help='Species to use (human or mouse). Default: human', default='human', action=SM)
    opts.add_argument('-c', '--cell_type', help='Cell type to extract data from for humans (Neurons \[default] or Nonneurons)', default='Neurons', action=SM)
    opts.add_argument('-r', '--region', help='Region to use for mice (OLF, CTXsp, Isocortex-1, Isocortex-2, HPF, STR, PAL, TH, HY, MB, MY, P, CB). Default: None', default=None, action=SM)
    opts.add_argument('-d', '--data_type', help='Type of expression data (log2 or raw). Default: log2', default='log2', action=SM)
    opts.add_argument('-o', '--output', help='Path to output CSV file.', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Should load_RNAseq_cell_metadata and load_RNAseq_gene_metadata be moved to a separate module?
# TODO: loading expression data is slow (loads whoe dataset). It might be optimized by changing the orientation of the data (CSR to CSC) once, and then perhaps slices of data can be loaded instead of the whole dataset.

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
        The species to use (human or mouse). Default: 'human'.

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


def get_gene_data_wo_cache_and_chunking(
    download_base: Path,
    all_cells: pd.DataFrame,
    all_genes: pd.DataFrame,
    selected_genes: List[str],
    data_type: str = "log2",
    species: str = "human",
    region: str = None,
    cell_type: str = None
) -> pd.DataFrame:
    """Load and structure gene expression data directly from RNA-seq data for specific genes.
    
    Parameters
    ----------
    download_base : Path
        The base directory where the data is located.
    all_cells : pandas.DataFrame
        Cell metadata indexed on cell_label.
    all_genes : pandas.DataFrame
        Gene metadata indexed on gene_identifier.
    selected_genes : list of strings
        List of gene_symbols that are a subset of those in the full genes DataFrame.
    data_type : str
        Type of expression data, "log2" or "raw". Defaults to "log2".
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
        expression_path = download_base / f"expression_matrices/WMB-10Xv3/20230630/WMB-10Xv3-{region}-{data_type}.h5ad"
    else:
        expression_path = download_base / f"expression_matrices/WHB-10Xv3/20240330/WHB-10Xv3-{cell_type}-{data_type}.h5ad"
    
    if not expression_path.exists():
        print(f"[red1]Error: Expression data not found at {expression_path}\n")
        import sys; sys.exit()
    
    print(f"    Loading expression data from {expression_path}")
    expression_data = anndata.read_h5ad(expression_path)
    print("    Data loaded successfully.\n")
    
    # Match cells between metadata and expression data
    print("    Matching cell labels between metadata and expression data...")
    cell_indexes = all_cells.index.intersection(expression_data.obs_names)  # Check for matching cell labels
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
        valid_cell_types = {"Neurons", "Nonneurons"}
        if args.cell_type is None or args.cell_type not in valid_cell_types:
            print(f"\n    [red1]Error: Please provide a valid cell type: {valid_cell_types}\n")
            return
        
    # Load gene metadata. Index: gene_identifier (e.g., ENSMUSG00000034997). Columns: gene_symbol (e.g., Htr2a)
    gene_df = load_RNAseq_gene_metadata(download_base, species=args.species)
    gene_list = [g for g in args.genes if g in gene_df["gene_symbol"].values]
    if not gene_list:
        raise ValueError("None of the requested genes found in gene metadata.")


    # Load cell metadata. Index: cell_label. Columns: feature_matrix_label, region_of_interest_acronym, x, y, cluster_alias
    cell_df = load_RNAseq_cell_metadata(download_base, species=args.species)

    # Load expression data from each file and concatenate
    expression_matrices_dir = download_base / 'expression_matrices'
    pattern = "**/WMB-10Xv3-*-log2.zarr" if args.species == "mouse" else "**/WHB-10Xv3-*-log2.zarr"
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

    # Join with cell metadata
    print(f"\n    Full expression data:\n{full_exp_df.head()}\n")
    cell_df_joined = cell_df.join(full_exp_df, how='inner')


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
