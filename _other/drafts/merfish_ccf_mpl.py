#!/usr/bin/env python3

"""
Use ``/Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/_other/drafts/merfish_ccf.py`` from UNRAVEL to plot MERFISH data from the Allen Brain Cell Atlas.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/descriptions/notebook_subtitle1.html
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/merfish_ccf_registration_tutorial.html

Usage:
------
    /Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/_other/drafts/merfish_ccf.py -r path/to/root_dir -g gene_name -si slice_index
"""

import anndata
import matplotlib.pyplot as plt
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
    reqs.add_argument('-r', '--root', help='Path to the root directory of the MERFISH data', required=True, action=SM)
    reqs.add_argument('-g', '--gene', help='Gene to plot.', required=True, action=SM)
    reqs.add_argument('-si', '--slice_index', help='Index of the Z slice to view (0 to 52)', type=int, required=True, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# Helper functions
def plot_section(xx, yy, val=None, fig_width=8, fig_height=8, cmap=None, vmin=None, vmax=None):
    fig, ax = plt.subplots()
    fig.set_size_inches(fig_width, fig_height)
    scatter = ax.scatter(xx, yy, s=0.5, c=val, marker='.', cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_ylim(11, 0)
    ax.set_xlim(0, 11)
    ax.axis('equal')
    ax.set_xticks([])
    ax.set_yticks([])
    fig.colorbar(scatter, ax=ax)  # Add color bar to show the scale
    return fig, ax

def create_expression_dataframe(anndata_obj, gene_symbol):
    """
    Extracts expression data for a specific gene by its symbol and returns a DataFrame.
    """
    # Find the corresponding Ensembl ID for the gene symbol
    ens_id = anndata_obj.var[anndata_obj.var['gene_symbol'] == gene_symbol].index
    if len(ens_id) == 0:
        raise ValueError(f"Gene symbol {gene_symbol} not found in dataset.")
    
    # Extract expression data for the gene
    gene_data = anndata_obj[:, ens_id].to_df()
    return gene_data, ens_id[0]  # Return the expression data and Ensembl ID

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    root_dir = Path(args.root)

    # Load the expression data
    expression_path = root_dir / 'expression_matrices/MERFISH-C57BL6J-638850/20230830/C57BL6J-638850-log2.h5ad'
    print(f"\nLoading expression data from {expression_path}\n")
    adata = anndata.read_h5ad(expression_path)

    # Load the metadata
    cell_metadata_path = root_dir / 'metadata/MERFISH-C57BL6J-638850/20231215/views/cell_metadata_with_cluster_annotation.csv'
    reconstructed_coords_path = root_dir / 'metadata/MERFISH-C57BL6J-638850-CCF/20231215/reconstructed_coordinates.csv'

    # Read in metadata files
    print(f"\nLoading metadata from {cell_metadata_path}\n")
    cell_metadata = pd.read_csv(cell_metadata_path)

    print(f"\nLoading reconstructed coordinates from {reconstructed_coords_path}\n")
    reconstructed_coords = pd.read_csv(reconstructed_coords_path, dtype={'cell_label': str})

    # Rename the columns to distinguish CCF coordinates from MERFISH coordinates
    reconstructed_coords.rename(columns={'x': 'x_ccf', 'y': 'y_ccf', 'z': 'z_ccf'}, inplace=True)

    # Get the unique Z slices and check if the slice index is valid
    z_values = np.sort(reconstructed_coords['z_ccf'].unique())    
    if args.slice_index < 0 or args.slice_index >= len(z_values):
        print(f"\nError: Slice index {args.slice_index} is out of bounds. Please select a value between 0 and {len(z_values) - 1}.")
        return

    z_slice = z_values[args.slice_index]
    print(f"\nSelected Z slice (index {args.slice_index}): {z_slice} µm\n")

    # Filter the data for the selected Z slice
    slice_data = reconstructed_coords[reconstructed_coords['z_ccf'] == z_slice]

    if slice_data.empty:
        print(f"\nError: No cells found in Z slice {z_slice}.")
        return

    # Join metadata and expression data
    print(f"\nCreating expression DataFrame for gene: {args.gene}\n")
    pred = adata.var['gene_symbol'] == args.gene  # Check if gene is present in the dataset
    if not pred.any():
        print(f"\nError: Gene {args.gene} not found in the dataset.")
        return

    # Join with metadata
    print("\nMerging metadata and expression data\n")
    gene_expression_df, ensembl_id = create_expression_dataframe(adata, args.gene)

    print(gene_expression_df.describe())


    # Reset index to avoid misalignment issues
    full_data = pd.concat([cell_metadata.reset_index(drop=True), 
                           slice_data.reset_index(drop=True), 
                           gene_expression_df.reset_index(drop=True)], axis=1)
    
    # Check for NaN values in gene expression
    nan_count = full_data[ensembl_id].isna().sum()
    print(f"Number of NaN values in {args.gene}: {nan_count}")

    # Check how many rows have non-NaN values
    non_nan_count = full_data[ensembl_id].notna().sum()
    print(f"Number of non-NaN values in {args.gene}: {non_nan_count}")

    # Check for high-expression cells before dropping NaN values
    high_expression_cells = full_data[full_data[ensembl_id] > 5]
    print(f"Number of cells with expression > 5 before filtering: {len(high_expression_cells)}")

    # Check the number of cells with expression greater than 3: 
    high_expression_cells = full_data[full_data[ensembl_id] > 3]
    print(f"Number of cells with expression > 3 before filtering: {len(high_expression_cells)}")

    # Filter out rows with NaN values
    valid_data = full_data.dropna(subset=[ensembl_id])

    # Check for high-expression cells after filtering
    high_expression_after_filter = valid_data[valid_data[ensembl_id] > 5]
    print(f"Number of cells with expression > 5 after filtering: {len(high_expression_after_filter)}")

    # Check the number of cells with expression greater than 3 after filtering
    high_expression_after_filter = valid_data[valid_data[ensembl_id] > 3]
    print(f"Number of cells with expression > 3 after filtering: {len(high_expression_after_filter)}")

    # Check maximum expression value
    max_expression_value = full_data[ensembl_id].max()
    print(f"Maximum expression value for {args.gene}: {max_expression_value}")

    # Plot data in CCF space using the Ensembl ID
    print(f"\nPlotting gene expression for {args.gene} (Ensembl ID: {ensembl_id}) in CCF space\n")
    fig, ax = plot_section(valid_data['x_ccf'], valid_data['y_ccf'], 
                       val=valid_data[ensembl_id], cmap='plasma_r', 
                       vmin=0.4, vmax=7)  # Adjust vmax based on your data range
    ax.set_title(f'Gene Expression: {args.gene} (Z Slice: {z_slice} µm)')
    plt.show()

    verbose_end_msg()

if __name__ == '__main__':
    main()