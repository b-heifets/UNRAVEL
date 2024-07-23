#!/usr/bin/env python3

"""
Use ``cluster_prism`` from UNRAVEL to organize data for clusters for plotting in Prism.

Usage
-----
    cluster_prism -ids 1 2 3

Note:
    - cluster_table saves valid_clusters_dir/valid_cluster_IDs_sorted_by_anatomy.txt

Inputs:
    <asterisk>.csv from ``cluster_org_data`` (in working dir) or ``cluster_mean_IF``

CSV naming conventions:
    - Condition: first word before '_' in the file name (use ``utils_prepend`` if needed)
    - Sample: second word in file name

Example unilateral inputs:
    - condition1_sample01_<cell|label>_density_data.csv
    - condition1_sample02_<cell|label>_density_data.csv
    - condition2_sample03_<cell|label>_density_data.csv
    - condition2_sample04_<cell|label>_density_data.csv

Example bilateral inputs (if any file has _LH.csv or _RH.csv, the command will attempt to pool data):
    - condition1_sample01_<cell|label>_density_data_LH.csv
    - condition1_sample01_<cell|label>_density_data_RH.csv

Columns in the input .csv files:
    sample, cluster_ID, <cell_count|label_volume|mean_IF_intensity>, [cluster_volume], [cell_density|label_density], ...

Outputs:
    - Outputs saved in ./cluster_validation_summary/
    - Cluster order follows -ids order
    - <cell_count|label_volume|mean_IF_intensity>_summary.csv
    - [<cell_density|label_density>_summary.csv]
    - [<cell_density|label_density>_summary_across_clusters.csv]
    - [cluster_volume_summary.csv]
"""

import argparse
import pandas as pd
from glob import glob
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-ids', '--valid_cluster_ids', help='Space-separated list of valid cluster IDs to include in the summary.', nargs='+', type=int, default=None, action=SM)
    parser.add_argument('-p', '--path', help='Path to the directory containing the CSV files from ``cluster_validation`` or ``cluster_mean_IF``. Default: current directory', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


# TODO: Address this warning:
# /usr/local/UNRAVEL_dev/unravel/cluster_stats/prism.py:190: PerformanceWarning: dropping on a non-lexsorted multi-index without a level parameter may impact performance.
# density_col_summary_df_sum = density_col_summary_df_sum.drop('cluster_ID').reset_index().T


def sort_samples(sample_names):
    # Extract the numeric part of the sample names and sort by it
    return sorted(sample_names, key=lambda x: int(''.join(filter(str.isdigit, x))))

def generate_summary_table(csv_files, data_column_name):
    # Create a dictionary to hold data for each condition
    data_by_condition = {}

    # Check if any files contain hemisphere indicators
    has_hemisphere = any('_LH.csv' in str(file) or '_RH.csv' in str(file) for file in csv_files)

    # Loop through each file in the working directory
    for file in csv_files:

        # Extract the condition and sample name
        parts = str(Path(file).name).split('_')
        condition = parts[0]
        sample = parts[1] 

        if has_hemisphere:
        # if has_hemisphere, pool data from LH and RH files
            if str(file).endswith('_RH.csv'):
                continue # Skip RH files

            if str(file).endswith('_LH.csv'):
                LH_df = pd.read_csv(file, usecols=['sample', 'cluster_ID', data_column_name])

                if not Path(str(file).replace('_LH.csv', '_RH.csv')).exists():
                    print(f"[red]    {Path(str(file).replace('_LH.csv', '_RH.csv'))} is missing")
                    with open(file.parent / "missing_csv_files.txt", 'a') as f:
                        f.write(f"{Path(str(file).replace('_LH.csv', '_RH.csv'))} is missing")
                    import sys ; sys.exit()

                RH_df = pd.read_csv(str(file).replace('_LH.csv', '_RH.csv'), usecols=['sample', 'cluster_ID', data_column_name])

                # Sum the data_col of the LH and RH dataframes
                if data_column_name == 'cell_count' or data_column_name == 'label_volume':
                    df = pd.concat([LH_df, RH_df], ignore_index=True).groupby(['sample', 'cluster_ID']).agg( # Group by sample and cluster_ID
                        **{data_column_name: pd.NamedAgg(column=data_column_name, aggfunc='sum')} # Sum cell_count or label_volume, unpacking the dict into keyword arguments for the .agg() method
                    ).reset_index() # Reset the index to avoid a multi-index dataframe
                elif data_column_name == 'mean_IF_intensity':
                    df = pd.concat([LH_df, RH_df], ignore_index=True).groupby(['sample', 'cluster_ID']).agg( # Group by sample and cluster_ID
                        **{data_column_name: pd.NamedAgg(column=data_column_name, aggfunc='mean')} # Mean of mean_IF_intensity, unpacking the dict into keyword arguments for the .agg() method
                    ).reset_index()

        else:
            # Load the CSV file into a pandas dataframe
            df = pd.read_csv(file, usecols=['sample', 'cluster_ID', data_column_name])

        # Set the cluster_ID as index and select the density column
        df.set_index('cluster_ID', inplace=True)
        df = df[[data_column_name]]

        # Rename the density column with the sample name to avoid column name collision during concat
        df.rename(columns={data_column_name: sample}, inplace=True)

        # If the condition is not already in the dictionary, initialize it with the dataframe
        if condition not in data_by_condition:
            data_by_condition[condition] = df
        else:
            # Concatenate the new dataframe with the existing one for the same condition
            data_by_condition[condition] = pd.concat([data_by_condition[condition], df], axis=1)

    # Loop through each condition and sort the columns by sample number
    for condition in data_by_condition:
        # Get current columns for the condition
        current_columns = data_by_condition[condition].columns
        # Sort the columns
        sorted_columns = sort_samples(current_columns)
        # Reindex the DataFrame with the sorted columns
        data_by_condition[condition] = data_by_condition[condition][sorted_columns]

    # Concatenate all condition dataframes side by side
    all_conditions_df = pd.concat(data_by_condition.values(), axis=1, keys=data_by_condition.keys())

    # Reset the index so that 'Cluster_ID' becomes a column
    all_conditions_df.reset_index(inplace=True)

    return all_conditions_df


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    path = Path(args.path) if args.path else Path.cwd()

    # Load all .csv files
    csv_files = list(path.glob('*.csv'))

    if not csv_files:
        print(f"\n[red]    No CSV files found in {path}.[/]")
        import sys ; sys.exit()

    # Load the first .csv file to check for data columns and set the appropriate column names
    first_df = pd.read_csv(csv_files[0])
    if 'cell_count' in first_df.columns:
        data_col, density_col = 'cell_count', 'cell_density'
    elif 'label_volume' in first_df.columns:
        data_col, density_col = 'label_volume', 'label_density'
    elif 'mean_IF_intensity' in first_df.columns:
        data_col, density_col = 'mean_IF_intensity', None
    else:
        print("Error: Unrecognized data columns in input files.")
        return

    # Generate a summary table for the cell_count or label_volume data
    data_col_summary_df = generate_summary_table(csv_files, data_col)  # Columns: sample, cluster_ID, cell_count|label_volume|mean_IF_intensity

    # Generate a summary table for the cluster volume data
    if 'cluster_volume' in first_df.columns:
        cluster_volume_summary_df = generate_summary_table(csv_files, 'cluster_volume')  # Columns: sample, cluster_ID, cluster_volume
    else:
        cluster_volume_summary_df = None

    # Generate a summary table for the cell_density or label_density data
    if density_col is not None:
        density_col_summary_df = generate_summary_table(csv_files, density_col)  # Columns: sample, cluster_ID, cell_density|label_density
    else:
        density_col_summary_df = None

    # Exclude clusters that are not in the list of valid clusters
    if args.valid_cluster_ids is not None:
        data_col_summary_df = data_col_summary_df[data_col_summary_df['cluster_ID'].isin(args.valid_cluster_ids)]
        if cluster_volume_summary_df is not None:
            cluster_volume_summary_df = cluster_volume_summary_df[cluster_volume_summary_df['cluster_ID'].isin(args.valid_cluster_ids)]
        if density_col_summary_df is not None:
            density_col_summary_df = density_col_summary_df[density_col_summary_df['cluster_ID'].isin(args.valid_cluster_ids)]

        # Sort data frames such that the 'cluster_ID' column matches the order of clusters in args.valid_cluster_ids
        data_col_summary_df = data_col_summary_df.sort_values(by='cluster_ID', key=lambda x: x.map({cluster: i for i, cluster in enumerate(args.valid_cluster_ids)}))
        if cluster_volume_summary_df is not None:
            cluster_volume_summary_df = cluster_volume_summary_df.sort_values(by='cluster_ID', key=lambda x: x.map({cluster: i for i, cluster in enumerate(args.valid_cluster_ids)}))
        if density_col_summary_df is not None:
            density_col_summary_df = density_col_summary_df.sort_values(by='cluster_ID', key=lambda x: x.map({cluster: i for i, cluster in enumerate(args.valid_cluster_ids)}))

    # For a summary across clusters, sum each column in the summary tables other than the 'cluster_ID' column, which could be dropped
    data_col_summary_df_sum = data_col_summary_df.sum()
    if cluster_volume_summary_df is not None:
        cluster_volume_summary_df_sum = cluster_volume_summary_df.sum()

    # For a summary across clusters, calculate the density sum from the sum of the cell_count or label_volume and cluster_volume sums
    if 'cell_count' in first_df.columns:
        density_col_summary_df_sum = data_col_summary_df_sum / cluster_volume_summary_df_sum
    elif 'label_volume' in first_df.columns:
        density_col_summary_df_sum = data_col_summary_df_sum / cluster_volume_summary_df_sum * 100

    # For a summary across clusters, organize the df like the original summary tables
    if cluster_volume_summary_df is not None and density_col_summary_df is not None:
        multi_index = data_col_summary_df.columns
        density_col_summary_df_sum.columns = multi_index
        density_col_summary_df_sum = density_col_summary_df_sum.drop('cluster_ID').reset_index().T

    # Make output dir
    output_dir = path / '_prism'
    Path(output_dir).mkdir(exist_ok=True)

    # Save the summary tables to .csv files
    if args.valid_cluster_ids is not None:
        data_col_summary_df.to_csv(output_dir / f'{data_col}_summary_for_valid_clusters.csv', index=False)
        if 'cluster_volume' in first_df.columns:
            density_col_summary_df.to_csv(output_dir / f'{density_col}_summary_for_valid_clusters.csv', index=False)
            density_col_summary_df_sum.to_csv(output_dir / f'{density_col}_summary_across_valid_clusters.csv', index=False)
            cluster_volume_summary_df.to_csv(output_dir / 'valid_cluster_volume_summary.csv', index=False)
    else:
        data_col_summary_df.to_csv(output_dir / f'{data_col}_summary.csv', index=False)
        if 'cluster_volume' in first_df.columns:
            density_col_summary_df.to_csv(output_dir / f'{density_col}_summary.csv', index=False)
            density_col_summary_df_sum.to_csv(output_dir / f'{density_col}_summary_across_clusters.csv', index=False)
            cluster_volume_summary_df.to_csv(output_dir / 'cluster_volume_summary.csv', index=False)

    print(f"\n    Saved results in [bright_magenta]{output_dir}")

    verbose_end_msg()


if __name__ == '__main__':
    main()