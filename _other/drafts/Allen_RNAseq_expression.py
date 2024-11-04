#!/usr/bin/env python3

"""
Use ``./Allen_RNAseq_expression`` from UNRAVEL to extract expression data for specific genes from the Allen Brain Cell Atlas RNA-seq data.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/general_accessing_10x_snRNASeq_tutorial.htmlml

Usage:
------
    ./Allen_RNAseq_expression -b path/base_dir -g genes [-s mouse | human] [-c Neurons | Nonneurons] [-r region] [-d log2 | raw ] [-o output] [-v]

Usage for humans:
-----------------
    ./Allen_RNAseq_expression -b path/base_dir -g genes -c Neurons [-o output_dir] [-v]

Usage for mice:
---------------
    ./Allen_RNAseq_expression -b path/base_dir -g genes -r region [-o output_dir] [-v]
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


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the MERFISH data', required=True, action=SM)
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


def load_RNAseq_cell_metadata(download_base, species='human'):
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
        The cell metadata dataframe. Index: cell_label. Columns: cell_barcode, barcoded_cell_sample_label, library_label, feature_matrix_label, entity, brain_section_label, library_method, donor_label, donor_sex, dataset_label, x, y, cluster_alias, region_of_interest_label, anatomical_division_label, abc_sample_id.
    """
    if species == 'mouse':
        cell_metadata_path = download_base / "metadata/WMB-10X/20231215/cell_metadata.csv"
    else:
        cell_metadata_path = download_base / "metadata/WHB-10Xv3/20240330/cell_metadata.csv"
    if cell_metadata_path.exists():
        print(f"\n    Loading cell metadata from {cell_metadata_path}\n")
        cell_df = pd.read_csv(cell_metadata_path, dtype={'cell_label': str})
        cell_df.set_index('cell_label', inplace=True)
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
    all_cells: pd.DataFrame,
    all_genes: pd.DataFrame,
    selected_genes: List[str],
    data_type: str = "log2",
    species: str = "human",
    region: str = None,
    cell_type: str = None
):
    """Load expression matrix data directly from RNA-seq data for specific genes.
    
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
    # Filter the gene metadata to only include the selected genes
    gene_mask = all_genes.gene_symbol.isin(selected_genes)
    gene_filtered = all_genes[gene_mask]  
    
    # Define path to expression data
    if species == 'mouse':
        expression_path = download_base / f"expression_matrices/WMB-10Xv3/20230630/WMB-10Xv3-{region}-{data_type}.h5ad"
    else:
        expression_path = download_base / f"expression_matrices/WHB-10Xv3/20240330/WHB-10Xv3-{cell_type}-{data_type}.h5ad"
    
    # Load the full dataset without chunking (must have enough RAM)
    if expression_path.exists():
        print(f"\nLoading expression data from {expression_path}")
        expression_data = anndata.read_h5ad(expression_path)
        print("Data loaded successfully.\n")
    else:
        print(f"\n    [red1]Expression data not found at {expression_path}\n")
        import sys ; sys.exit()
    
    # Filter for selected cells and genes
    cell_indexes = all_cells.index
    output_gene_data = expression_data[cell_indexes, gene_filtered.index].to_df()  # Extract expression data for the gene
    output_gene_data.columns = gene_filtered.gene_symbol  # Set the column names to the gene symbols
    # output_gene_data.columns = gene_filtered.gene_symbol.values  # Set the column names to the gene symbols

    if hasattr(expression_data, 'file'):
        expression_data.file.close()  # Close file only if backed mode is used
    del expression_data  # Clean up

    return output_gene_data


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    # Check that either a cell type or region is provided
    if args.species == 'human':
        if args.cell_type is None:
            print("\n    [red1]Please provide a cell type (Neurons or Nonneurons) for humans\n")
            return
    else:
        if args.region is None:
            print("\n    [red1]Please provide a region (OLF, CTXsp, Isocortex-1, Isocortex-2, HPF, STR, PAL, TH, HY, MB, MY, P, CB) for mice\n")
            return

    # Load the cell metadata
    cell_df = load_RNAseq_cell_metadata(download_base, species=args.species) # Add option to load cell_metadata_with_cluster_annotation.csv instead? Does this just add extra columns?

    # Load the gene metadata
    gene_df = load_RNAseq_gene_metadata(download_base, species=args.species)

    # Load the expression data
    expression_data = get_gene_data_wo_cache_and_chunking(download_base, cell_df, gene_df, [args.genes], data_type=args.data_type, species=args.species, region=args.region, cell_type=args.cell_type)

    # Save the subset of expression data to a CSV file
    output_folder = Path(args.output) if args.output != '.' else Path.cwd()
    output_folder.mkdir(parents=True, exist_ok=True)

    for gene in args.genes:
        gene_data = expression_data[[gene]]  # Select only the current gene's data
        
        # Define the output file path for the current gene
        if args.species == 'mouse':
            output_file = output_folder / f"WMB-10Xv3_{gene}_expression_data_{args.region}_{args.data_type}.csv"
        else:
            output_file = output_folder / f"WHB-10Xv3_{gene}_expression_data_{args.cell_type}_{args.data_type}.csv"
        
        # Save the gene-specific data to a CSV file
        gene_data.to_csv(output_file)
        print(f"\nSaved expression data for gene {gene} to {output_file}\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()
