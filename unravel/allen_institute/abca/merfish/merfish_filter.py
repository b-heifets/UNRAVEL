#!/usr/bin/env python3

"""
Use ``abca_merfish_filter`` or ``mf_filter`` from UNRAVEL to filter ABCA MERFISH cells based on columns and values in the cell metadata. 
It integrates the filtering with the generation of `exp_df` and allows optional export of filtered data or the generation of updated 3D images.

Note:
    - Columns to filter by: parcellation_substructure (default)
    - Values to filter by: e.g., ACB
    - The input CSV may be previously filtered (e.g., ``abca_merfish_filter_by_mask``) or it may be the full cell metadata (cell_metadata.csv).

    
Outputs:
    - Filtered cell metadata CSV file (default: <input_stem>_filtered[_<first_value>][_neurons].csv)
    
Usage:
------
    abca_merfish_filter -b path/base_dir [--columns] [--values] [-o path/output.csv] [-n] [-v]
"""

import anndata
import numpy as np
import pandas as pd
import nibabel as nib
from pathlib import Path
from rich import print
from rich.traceback import install

import unravel.allen_institute.abca.merfish.merfish as mf
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import get_stem, log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-val', '--values', help='Values to filter MERFISH cell metadata or input.csv by (e.g., ACB).', nargs='*', action=SM)
    opts.add_argument('-i', '--input', help='Input CSV file containing MERFISH cell metadata. If omitted, cell_metadata.csv will be loaded.', default=None, action=SM)
    opts.add_argument('-c', '--columns', help='Columns to filter MERFISH cell metadata by (e.g., parcellation_substructure \[default])', default=['parcellation_substructure'], nargs='*', action=SM)
    opts.add_argument('-o', '--output', help='Output path for the filtered df. Default: <input_stem>_filtered_<first_value>.csv', default=None, action=SM)
    opts.add_argument('-n', '--neurons', help='Filter out non-neuronal cells. Default: False', action='store_true', default=False)

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
    if args.input:
        cell_df_joined = pd.read_csv(args.input)
        print(f"\n    Cell metadata shape:\n    {cell_df_joined.shape}")
    else:
        # If no input is provided, load the default cell metadata
        print(f"Loading default cell metadata from {download_base}")
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

    missing_cols = [col for col in args.columns if col not in cell_df_joined.columns]
    if missing_cols:
        raise ValueError(f"Missing expected column(s) in input file: {missing_cols}")
    
    # Filter the DataFrame
    if args.values:
        filtered_df = filter_dataframe(cell_df_joined, args.columns, args.values)
    else:
        filtered_df = cell_df_joined.copy()


    print("\nFiltered cell metadata shape:", filtered_df.shape)
    print("\n                                             First row:")
    print(filtered_df.iloc[0])

    if args.neurons:
        print("[green]Filtering out non-neuronal cells (class > 29)[/green]")
        filtered_df = filtered_df[filtered_df['class'].str.split().str[0].astype(int) <= 29]

    print("Filtered cell metadata:")
    print(f'\n{filtered_df}\n')
    
    # Save the filtered DataFrame
    stem = get_stem(args.input) if args.input else "cell_metadata"
    if args.values:
        suffix = f'_{args.values[0]}'
        if args.neurons:
            suffix += '_neurons'
    elif args.neurons:
        suffix = '_neurons'
    else:
        suffix = ''
    output_path = args.output if args.output else Path().cwd() / f"{stem}_filtered{suffix}.csv"
    filtered_df.to_csv(output_path)

    print("\nUnique parcellation substructures:")
    print(cell_df_joined['parcellation_substructure'].unique())

    verbose_end_msg()


if __name__ == '__main__':
    main()
