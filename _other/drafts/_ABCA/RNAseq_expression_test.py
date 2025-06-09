#!/usr/bin/env python3

"""
Use ``./RNAseq_expression`` from UNRAVEL to extract expression data for specific genes from the Allen Brain Cell Atlas RNA-seq data.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/general_accessing_10x_snRNASeq_tutorial.html
    - Only the first gene in the list will be used to name the output file.
    - For humans, the cell type must be specified (Neurons or Nonneurons).
    - For mice, the region must be specified (OLF, CTXsp, Isocortex-1, Isocortex-2, HPF, STR, PAL, TH, HY, MB, MY, P, CB).
    - The output will be a CSV file with the expression data for the selected genes, indexed by cell_label.

Usage:
------
    ./RNAseq_expression -b path/base_dir -g genes [-s mouse | human] [-c Neurons | Nonneurons] [-r region] [-d log2 | raw ] [-o output] [-v]

Usage for humans:
-----------------
    ./RNAseq_expression -b path/base_dir -g genes -c Neurons [-o output_dir] [-v]

Usage for mice:
---------------
    ./RNAseq_expression -b path/base_dir -g genes -r region [-o output_dir] [-v]
"""

from typing import List
import anndata
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

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
    opts.add_argument('-r', '--region', help='Region to use for mice (OLF, CTXsp, Isocortex-1, Isocortex-2, HPF, STR, PAL, TH, HY, MB, MY, P, CB). Default: None', default=None, action=SM)
    opts.add_argument('-d', '--data_type', help='Type of expression data (log2 or raw). Default: log2', default='log2', action=SM)
    opts.add_argument('-o', '--output', help='Path to output folder for the expression data. Default: current directory', default='.', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Should load_RNAseq_cell_metadata and load_RNAseq_gene_metadata be moved to a separate module?

def load_scRNAseq_cell_metadata(download_base, species='mouse'):
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

def load_scRNAseq_gene_metadata(download_base, species='human'):
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

def load_scRNAseq_expression_data(
    download_base: Path,
    all_cells: pd.DataFrame,
    all_genes: pd.DataFrame,
    selected_genes: List[str],
    data_type: str = "log2",
    species: str = "human",
    region: str = None,
    cell_type: str = None
) -> pd.DataFrame:
    """Efficiently load RNA-seq expression data only for selected genes and matching cells."""
    # Filter genes
    gene_mask = all_genes.gene_symbol.isin(selected_genes)
    gene_filtered = all_genes[gene_mask]
    if gene_filtered.empty:
        raise ValueError(f"None of the selected genes found in gene metadata: {selected_genes}")

    print(f"\n    Selected genes in metadata: {gene_filtered['gene_symbol'].tolist()}")

    # Path to expression matrix
    if species == 'mouse':
        expression_path = download_base / f"expression_matrices/WMB-10Xv3/20230630/WMB-10Xv3-{region}-{data_type}.h5ad"
    else:
        expression_path = download_base / f"expression_matrices/WHB-10Xv3/20240330/WHB-10Xv3-{cell_type}-{data_type}.h5ad"

    if not expression_path.exists():
        raise FileNotFoundError(f"Expression data not found at {expression_path}")

    print(f"    Opening {expression_path} in backed mode...")

    # Open AnnData in backed mode
    adata = anndata.read_h5ad(expression_path, backed="r")

    # Match cells and genes using index positions
    matched_cells = all_cells.index.intersection(adata.obs_names)
    matched_genes = gene_filtered.index.intersection(adata.var_names)

    if len(matched_cells) == 0 or len(matched_genes) == 0:
        raise ValueError("No matching cells or genes found.")

    print(f"    Matched {len(matched_cells)} cells and {len(matched_genes)} genes")

    # Convert names to positions
    cell_idx = [adata.obs_names.get_loc(c) for c in matched_cells]
    gene_idx = [adata.var_names.get_loc(g) for g in matched_genes]

    # Read only relevant slice from backed .X
    print("    Reading subset of data from disk...")
    X = adata.X[cell_idx, :][:, gene_idx]  # this is still an h5py array, will be read lazily

    # Convert to dense array (efficient since it's a small subset)
    X = np.asarray(X)

    # Build final DataFrame
    df = pd.DataFrame(X, index=matched_cells, columns=gene_filtered.loc[matched_genes, "gene_symbol"].values)
    df.index.name = "cell_label"
    return df.reset_index()


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
    if args.species == 'mouse' and args.region is None:
        print("\n    [red1]Please provide a region for mice\n")
        return

    cell_df = load_scRNAseq_cell_metadata(download_base, species=args.species) # Add option to load cell_metadata_with_cluster_annotation.csv instead? Does this just add extra columns?

    gene_df = load_scRNAseq_gene_metadata(download_base, species=args.species)

    # Retrieve expression data for all selected genes at once
    expression_data = load_scRNAseq_expression_data(
        download_base, cell_df, gene_df, args.genes, data_type=args.data_type,
        species=args.species, region=args.region, cell_type=args.cell_type
    )
    
    # Check the data before saving to confirm structure
    print(f"\n    Final output data for {args.genes}:\n{expression_data.head()}\n")

    # Define output file path and save the DataFrame
    output_folder = Path(args.output) if args.output != '.' else Path.cwd()
    output_folder.mkdir(parents=True, exist_ok=True)
    if args.species == 'mouse':
        output_file = output_folder / f"WMB-10Xv3_{args.genes[0]}_expression_data_{args.region}_{args.data_type}.csv"
    else:
        if args.region is None:
            output_file = output_folder / f"WHB-10Xv3_{args.genes[0]}_expression_data_{args.cell_type}_{args.data_type}.csv"
        else:
            output_file = output_folder / f"WHB-10Xv3_{args.genes[0]}_expression_data_{args.cell_type}_{args.region}_{args.data_type}.csv"

    expression_data.to_csv(output_file, index=False)
    print(f"\n    Saved expression data for gene {args.genes[0]} to {output_file}\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()
