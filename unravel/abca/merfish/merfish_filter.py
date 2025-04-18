#!/usr/bin/env python3

"""
Use ``abca_merfish_filter`` or ``mf_filter`` from UNRAVEL to filter ABCA MERFISH cells based on columns and values in the cell metadata. 
It integrates the filtering with the generation of `exp_df` and allows optional export of filtered data or the generation of updated 3D images.

Notes:
    - Columns to filter by: parcellation_substructure (default)
    - Values to filter by: e.g., ACB

Usage:
------
    ./abca_merfish_filter -b path/base_dir [--columns] [--values] [-o path/output.csv] [-v]
"""

import anndata
import numpy as np
import pandas as pd
import nibabel as nib
from pathlib import Path
from rich import print
from rich.traceback import install

import unravel.abca.merfish.merfish as mf
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)
    reqs.add_argument('-val', '--values', help='Values to filter MERFISH cell metadata by (e.g., ACB).', nargs='*', action=SM)
    reqs.add_argument('-o', '--output', help='Output path for the filtered cell metadata. Default: None', default=None, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-c', '--columns', help='Columns to filter MERFISH cell metadata by (e.g., parcellation_substructure \[default])', default='parcellation_substructure', nargs='*', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Does it make sense to consolidate this with scRNA-seq_filter.py?

def filter_dataframe(df, columns, values):
    """
    Filter a DataFrame by columns and values.

    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame to filter.
    columns : list of str
        The columns to filter by.
    values : list of str
        The corresponding values or lists of values for each column.

    Returns:
    --------
    filtered_df : pd.DataFrame
        The filtered DataFrame.
    """
    for col, val in zip(columns, values):
        if ',' in val:  # Handle lists of values
            value_list = val.split(',')  # For parsing multiple values from the command line
            print(f"Filtering so that {col} only contains these values {value_list}")
            df = df[df[col].isin(value_list)]  # Filter by multiple values
            
        else:  # Handle single values
            print(f"Filtering so that {col} only contains this value {val}")
            df = df[df[col] == val]

    return df

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    # Load the cell metadata
    cell_df = mf.load_cell_metadata(download_base)
    print(f"\n    Initial cell metadata shape:\n    {cell_df.shape}")
    
    print(f'\n{cell_df=}\n')

    # Add the reconstructed coordinates to the cell metadata
    cell_df_joined = mf.join_reconstructed_coords(cell_df, download_base)

    # Add the classification levels and the corresponding color.
    cell_df_joined = mf.join_cluster_details(cell_df_joined, download_base)

    # Add the cluster colors
    cell_df_joined = mf.join_cluster_colors(cell_df_joined, download_base)
    
    # Add the parcellation annotation
    cell_df_joined = mf.join_parcellation_annotation(cell_df_joined, download_base)

    # Add the parcellation color
    cell_df_joined = mf.join_parcellation_color(cell_df_joined, download_base)
    print("\n                                             First row:")
    print(cell_df_joined.iloc[0])
    print("\nCell metadata:")
    print(f'{cell_df_joined}\n')

    # Print column names
    print(f"\nColumn names: {cell_df_joined.columns}\n")
    
    # Filter the DataFrame
    filtered_df = filter_dataframe(cell_df_joined, args.columns, args.values)
    print("\nFiltered cell metadata shape:", filtered_df.shape)
    print("\n                                             First row:")
    print(filtered_df.iloc[0])
    print("Filtered cell metadata:")
    print(f'\n{filtered_df}\n')

    filtered_df.to_csv(args.output)

    print("\nUnique parcellation substructures:")
    print(cell_df_joined['parcellation_substructure'].unique())

    verbose_end_msg()


if __name__ == '__main__':
    main()
