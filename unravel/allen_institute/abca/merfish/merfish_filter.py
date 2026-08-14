#!/usr/bin/env python3

"""
Use ``abca_merfish_filter`` or ``mf_filter`` from UNRAVEL to filter ABCA MERFISH cells based on columns and values in the cell metadata. 
It integrates the filtering with the generation of ``exp_df`` and allows optional export of filtered data or the generation of updated 3D images.

Note:
    - The input CSV may be previously filtered (e.g., ``abca_merfish_filter_by_mask``) or it may be the full cell metadata (cell_metadata.csv).
    - Columns to filter by: ``parcellation_substructure`` (default)
    - Values to filter by: e.g., ``ACB``
    - Regional columns can be printed with ``cols -i <ABCA_root>/metadata/Allen-CCF-2020/20230630/views/parcellation_to_parcellation_term_membership_acronym.csv``
    - Regional values can be printed with ``vals -i <ABCA_root>/metadata/Allen-CCF-2020/20230630/views/parcellation_to_parcellation_term_membership_acronym.csv -c substructure``
    - ``parcellation_`` is prepended to the regional column names in the cell metadata, so for example ``substructure`` becomes ``parcellation_substructure``

Outputs:
    - Filtered cell metadata CSV file (default: <input_stem>_filtered[_<first_value>][_neurons].csv)
    - With ``--all_values``, one CSV per unique value for each specified column.

Next steps:
    - Use the filtered cell metadata to examine cell type prevalence or gene expression
    - For cell type proportions like in the MapMySections data challenge, use ``mms_cell_type_proportions`` to calculate proportions for a given ontological level (e.g., subclass)
    - Then use ``mms_cell_type_proportions_concat`` to concatenate multiple CSVs into one file (one row per input file)
    - To visualize cell type proportions, use ``abca_sunburst`` to make a CSV for sunburst plotting
    - For looking at gene expression, load the filtered cell metadata and join it with the expression data for the gene(s) of interest (``abca_merfish_join_expression``)
    
Usage:
------
    abca_merfish_filter -b path/base_dir [--columns] [--values] [-o path/output.csv] [-n] [-v]
    abca_merfish_filter -b path/base_dir -a [-c column ...] [-o path/output_dir] [-w workers] [-n] [-v]
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import re

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
    opts.add_argument('-i', '--input', help='Input CSV file containing MERFISH cell metadata. If omitted, cell_metadata.csv will be loaded.', default=None, action=SM)
    opts.add_argument('-o', '--output', help='Output CSV path, or output directory with --all_values. Default: <input_stem>_filtered_<first_value>.csv or <input_stem>_filtered_by_value/', default=None, action=SM)
    opts.add_argument('-n', '--neurons', help='Filter out non-neuronal cells. Default: False', action='store_true', default=False)
    opts.add_argument('-c', '--columns', help='Columns to filter MERFISH cell metadata by (e.g., parcellation_substructure \[default])', default=['parcellation_substructure'], nargs='*', action=SM)
    opts.add_argument('-val', '--values', help='Values to filter MERFISH cell metadata or input.csv by (e.g., ACB).', nargs='*', action=SM)
    opts.add_argument('-a', '--all_values', help='Write one CSV per unique value in each specified column. Default: False', action='store_true', default=False)
    opts.add_argument('-w', '--workers', help='Number of parallel CSV-writing threads for --all_values. Default: 1', type=int, default=1, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Does it make sense to consolidate this with scRNA-seq_filter.py?


def sanitize_filename(value):
    """Convert a column value to a filesystem-safe string."""
    return re.sub(r'[^A-Za-z0-9._-]+', '_', str(value)).strip('_')


def save_filtered_value(df, indices, value, output_path):
    """Save rows corresponding to one column value."""
    value_df = df.loc[indices]
    value_df.to_csv(output_path)
    return value, len(value_df), output_path


def filter_all_values(df, columns, output_dir, stem, neurons=False, workers=1):
    """Write one CSV for every unique value in each specified column."""
    output_dir = Path(output_dir)

    for col in columns:
        col_output_dir = output_dir / col if len(columns) > 1 else output_dir
        col_output_dir.mkdir(parents=True, exist_ok=True)

        groups = df.groupby(col, dropna=True, sort=True).groups

        print(f"\nWriting {len(groups)} unique '{col}' values to {col_output_dir}")

        jobs = []
        for value, indices in groups.items():
            safe_value = sanitize_filename(value)
            suffix = '_neurons' if neurons else ''
            output_path = col_output_dir / f'{stem}_filtered_{safe_value}{suffix}.csv'
            jobs.append((value, indices, output_path))

        if workers == 1:
            for value, indices, output_path in jobs:
                value, n_cells, output_path = save_filtered_value(
                    df, indices, value, output_path
                )
                print(f"    {value}: {n_cells:,} cells -> {output_path}")
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [
                    executor.submit(
                        save_filtered_value,
                        df,
                        indices,
                        value,
                        output_path,
                    )
                    for value, indices, output_path in jobs
                ]

                for future in as_completed(futures):
                    value, n_cells, output_path = future.result()
                    print(f"    {value}: {n_cells:,} cells -> {output_path}")


def filter_dataframe(df, columns, values):
    """
    Filter a DataFrame by columns and values.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to filter.
    columns : list of str
        Columns to filter by.
    values : list of str
        Values (or comma-separated groups of values) to include across all columns.

    Returns
    -------
    filtered_df : pd.DataFrame
        The filtered DataFrame.
    """
    for col in columns:
        # Support space-separated and comma-separated values
        val_list = []
        for v in values:
            val_list.extend(v.split(','))
        val_list = [v.strip() for v in val_list if v.strip()]
        
        print(f"Filtering so that '{col}' contains any of these values: {val_list}")
        df = df[df[col].isin(val_list)]
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
    
        print(f'\nCell metadata:\n{cell_df}\n')

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

    # --all_values branch: Write one CSV per unique value in each specified column
    if args.all_values:
        if args.values:
            raise ValueError("--values cannot be used with --all_values.")

        if args.workers < 1:
            raise ValueError("--workers must be at least 1.")

        filtered_df = cell_df_joined.copy()

        if args.neurons:
            print("[green]Filtering out non-neuronal cells (class > 29)[/green]")
            filtered_df = filtered_df[filtered_df['class'].str.split().str[0].astype(int) <= 29]

        stem = get_stem(args.input) if args.input else "cell_metadata"

        output_dir = (
            Path(args.output)
            if args.output
            else Path().cwd() / f"{stem}_filtered_by_value"
        )

        filter_all_values(
            filtered_df,
            args.columns,
            output_dir,
            stem,
            neurons=args.neurons,
            workers=args.workers,
        )

        verbose_end_msg()
        return
    
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
    output_path = Path(args.output) if args.output else Path().cwd() / f"{stem}_filtered{suffix}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filtered_df.to_csv(output_path)

    print(f"\nUnique {args.columns} values in the filtered data:")
    for col in args.columns:
        print(f"Unique values in '{col}': {filtered_df[col].unique()}")
    
    print(f"\nFiltered data saved to: {output_path}")

    verbose_end_msg()


if __name__ == '__main__':
    main()
