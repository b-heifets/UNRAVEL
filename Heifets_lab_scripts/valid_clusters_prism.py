#!/usr/bin/env python3

import argparse
import pandas as pd
from glob import glob
from pathlib import Path
from rich import print
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM 


def parse_args():
    parser = argparse.ArgumentParser(description='Organize cell_count|label_volume, cluster_volume, and <cell|label>_density data from cluster and sample and save as csv', formatter_class=SuppressMetavar)
    parser.add_argument('-a', '--all', help='Save all summary CSVs included ones w/ cell_count|label_volume and cluster_volume data', action='store_true', default=False)
    parser.add_argument('-c', '--clusters', help='List of valid cluster IDs to include in the summary', nargs='+', type=int, action=SM)
    parser.epilog = """Inputs: *.csv from validate_clusters.py (e.g., in working dir named after the rev_cluster_index.nii.gz file)

CSV naming conventions:
- Condition: first word before '_' in the file name
- Sample: second word in file name

Example unilateral inputs: 
- condition1_sample01_<cell|label>_density_data.csv 
- condition1_sample02_<cell|label>_density_data.csv
- condition2_sample03_<cell|label>_density_data.csv
- condition2_sample04_<cell|label>_density_data.csv

...

Columns in the .csv files:
sample, cluster_ID, <cell_count|label_volume>, cluster_volume, <cell_density|label_density>, ...

Outputs saved in ./cluster_validation_summary/"""
    return parser.parse_args()

def sort_samples(sample_names):
    # Extract the numeric part of the sample names and sort by it
    return sorted(sample_names, key=lambda x: int(''.join(filter(str.isdigit, x))))

def generate_summary_table(csv_files, data_column_name):
    # Create a dictionary to hold data for each condition
    data_by_condition = {}

    # Loop through each file in the working directory
    for file in csv_files:
        # Extract the condition and sample name
        parts = file.split('_')
        condition = parts[0]
        sample = '_'.join(parts[1:-3])  # Adjust according to your filename structure

        # Load the CSV file into a pandas dataframe
        df = pd.read_csv(file)

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

    # Make output dir
    output_dir = 'cluster_validation_summary'
    Path(output_dir).mkdir(exist_ok=True)

    return all_conditions_df


def main():
    args = parse_args()

    # Load all .csv files in the current directory
    csv_files = glob('*.csv')

    # Load the first .csv file to check for data columns and set the appropriate column names
    first_df = pd.read_csv(csv_files[0])
    if 'cell_count' in first_df.columns:
        data_col, density_col = 'cell_count', 'cell_density'
    elif 'label_volume' in first_df.columns:
        data_col, density_col = 'label_volume', 'label_density'
    else:
        print("Error: Unrecognized data columns in input files.")
        return
    
    # Generate a summary table for the cell_count or label_volume data
    data_col_summary_df = generate_summary_table(csv_files, data_col)

    # Generate a summary table for the cluster volume data
    cluster_volume_summary_df = generate_summary_table(csv_files, 'cluster_volume')

    # Generate a summary table for the cell_density or label_density data
    density_col_summary_df = generate_summary_table(csv_files, density_col)

    # Exclude clusters that are not in the list of valid clusters
    if args.clusters is not None:
        data_col_summary_df = data_col_summary_df[data_col_summary_df['cluster_ID'].isin(args.clusters)]
        cluster_volume_summary_df = cluster_volume_summary_df[cluster_volume_summary_df['cluster_ID'].isin(args.clusters)]
        density_col_summary_df = density_col_summary_df[density_col_summary_df['cluster_ID'].isin(args.clusters)]

    # Sum each column in the summary tables other than the 'cluster_ID' column, which could be dropped
    data_col_summary_df_sum = data_col_summary_df.sum()
    cluster_volume_summary_df_sum = cluster_volume_summary_df.sum()

    # Calculate the density sum from the sum of the cell_count or label_volume and cluster_volume sums
    if 'cell_count' in first_df.columns:
        density_col_summary_df_sum = data_col_summary_df_sum / cluster_volume_summary_df_sum
    elif 'label_volume' in first_df.columns:
        density_col_summary_df_sum = data_col_summary_df_sum / cluster_volume_summary_df_sum * 100

    # Organize the df like the original summary tables
    multi_index = data_col_summary_df.columns
    density_col_summary_df_sum.columns = multi_index
    density_col_summary_df_sum = density_col_summary_df_sum.drop('cluster_ID').reset_index().T

    # Save the summary tables to .csv files
    if args.all:
        data_col_summary_df.to_csv(Path('cluster_validation_summary') / f'{data_col}_summary.csv', index=False)
        cluster_volume_summary_df.to_csv(Path('cluster_validation_summary') / 'cluster_volume_summary.csv', index=False)
    density_col_summary_df.to_csv(Path('cluster_validation_summary') / f'{density_col}_summary.csv', index=False)
    density_col_summary_df_sum.to_csv(Path('cluster_validation_summary') / f'{density_col}_summary_across_clusters.csv', index=False)

    print(f"Saved results in [bright_magenta]./cluster_validation_summary/")

if __name__ == '__main__':
    install()
    main()