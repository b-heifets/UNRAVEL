#!/usr/bin/env python3

import argparse
import pandas as pd
import scipy.stats as stats
from glob import glob
from pathlib import Path
from rich import print
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM


def parse_args():
    parser = argparse.ArgumentParser(description='Validate clusters based on differences in cell/object or label density w/ t-tests.', formatter_class=SuppressMetavar)
    parser.add_argument('-t', '--tail', help="Specify '1' for a one-tailed test or '2' for a two-tailed test (default: 2).", default='2', type=str, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Inputs: *.csv from validate_clusters.py (e.g., in working dir named after the rev_cluster_index.nii.gz file)

CSV naming conventions:
- Condition: first word before '_' in the file name
- Side: last word before .csv (LH or RH)

Example unilateral inputs: 
- condition1_sample01_<cell|label>_density_data.csv 
- condition1_sample02_<cell|label>_density_data.csv
- condition2_sample03_<cell|label>_density_data.csv
- condition2_sample04_<cell|label>_density_data.csv

Example bilateral inputs (if any file has _LH.csv or _RH.csv, the script will attempt to pool data):
- condition1_sample01_<cell|label>_density_data_LH.csv
- condition1_sample01_<cell|label>_density_data_RH.csv
...

Columns in the .csv files:
sample, cluster_ID, <cell_count|label_volume>, cluster_volume, <cell_density|label_density>, ...

Outputs: ./cluster_validation_summary/ with cluster_validation_summary.csv, cluster_t_test_results.csv, cluster_validation_summary.txt, significant_cluster_IDs.txt"""
    return parser.parse_args()


def main():
    args = parse_args()

    # Load all .csv files in the current directory
    csv_files = glob('*.csv')

    # Load the first .csv file to check for data columns and set the appropriate column names
    first_df = pd.read_csv(csv_files[0])
    if 'cell_count' in first_df.columns:
        data_col, data_col_pooled, density_col = 'cell_count', 'pooled_cell_count', 'cell_density'
    elif 'label_volume' in first_df.columns:
        data_col, data_col_pooled, density_col = 'label_volume', 'pooled_label_volume', 'label_density'
    else:
        print("Error: Unrecognized data columns in input files.")
        return
    
    # Create a summary dataframe
    summary_df = pd.DataFrame(columns=['condition', 'sample', 'side', 'cluster_ID', data_col, 'cluster_volume', density_col])
    
    # Check if any files contain hemisphere indicators
    has_hemisphere = any('_LH.csv' in file or '_RH.csv' in file for file in csv_files)

    if has_hemisphere:
        # Process files with hemisphere pooling
        print(f"\nProcessing [red1 bold]bilateral[/red1 bold] [dark_orange bold]{density_col}[/ dark_orange bold] data from _LH.csv and _RH.csv files with [gold1 bold]{str(args.tail)}[/gold1 bold]-tailed t-tests...")
        for file in csv_files:
            condition_name = file.split('_')[0]
            side = file.split('_')[-1].split('.')[0]

            df = pd.read_csv(file)
            df = df.drop(columns=['xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax'])
            df['condition'] = condition_name # Add the condition to the df
            df['side'] = side # Add the side 

            summary_df = pd.concat([summary_df, df], ignore_index=True)

        # Pool data by condition, sample, and cluster_ID
        summary_df = summary_df.groupby(['condition', 'sample', 'cluster_ID']).agg( # Group by condition, sample, and cluster_ID
            **{data_col_pooled: pd.NamedAgg(column=data_col, aggfunc='sum'), # Sum cell_count or label_volume, unpacking the dict into keyword arguments for the .agg() method 
            'pooled_cluster_volume': pd.NamedAgg(column='cluster_volume', aggfunc='sum')} # Sum cluster_volume
        ).reset_index() # Reset the index to avoid a multi-index dataframe
 
        summary_df[density_col] = summary_df[data_col_pooled] / summary_df['pooled_cluster_volume'] # Add a column for cell/lable density
    else:
        # Process files without hemisphere pooling
        print(f"\nProcessing [red1 bold]unilateral[/red1 bold] [dark_orange bold]{density_col}[/ dark_orange bold] data with [gold1 bold]{str(args.tail)}[/gold1 bold]-tailed t-tests...")
        for file in csv_files:
            df = pd.read_csv(file)
            df['condition'] = file.split('_')[0]
            df = df.drop(columns=[data_col, 'cluster_volume', 'xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax'])
            summary_df = pd.concat([summary_df, df], ignore_index=True)

    # Initialize df for unpaired 2-tailed t-tests for each cluster
    t_test_results = pd.DataFrame(columns=['cluster_ID', 'p_value', 'significance'])

    # Get the condition names
    condition_names = summary_df['condition'].unique()
    if len(condition_names) != 2:
        print("Error: The script requires exactly two conditions for comparison.")
        return
    group_one, group_two = condition_names

    # Iterate over each unique cluster ID
    for cluster_id in summary_df['cluster_ID'].unique():
        cluster_data = summary_df[summary_df['cluster_ID'] == cluster_id]

        # Extract data for each condition
        group_one_data = pd.to_numeric(cluster_data[cluster_data['condition'] == group_one][density_col], errors='coerce') # coerce to NaN if not numeric
        group_two_data = pd.to_numeric(cluster_data[cluster_data['condition'] == group_two][density_col], errors='coerce')
  
        # Perform unpaired two-tailed t-test
        t_stat, p_value = stats.ttest_ind(group_one_data.dropna(), group_two_data.dropna(), equal_var=False)

        # Adjust p_value for one-tailed test if specified
        if args.tail == '1':
            p_value /= 2  # Halve the p-value for a one-tailed test

        # Create a temporary DataFrame for the current t-test result
        temp_df = pd.DataFrame({'cluster_ID': [cluster_id], 'p_value': [p_value]})

        # Use pd.concat to append the temporary DataFrame to t_test_results
        t_test_results = pd.concat([t_test_results, temp_df], ignore_index=True)

    t_test_results['significance'] = t_test_results['p_value'].apply(lambda p: '****' if p < 0.0001 else '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'n.s.')

    # Print the name of the working directory
    print(f"Current working directory: [bold green]{Path.cwd().name}")

    if args.verbose:
        # Output results
        print(f'\n{t_test_results}\n')

    # Print the number of clusters with significant differences
    print(f"Number of sig. clusters: {len(t_test_results[t_test_results['p_value'] < 0.05])}")

    # Print the total number of clusters
    print(f"Total number of clusters: {len(t_test_results)}")

    # Print the cluster validation rate
    print(f"Cluster validation rate: {len(t_test_results[t_test_results['p_value'] < 0.05]) / len(t_test_results) * 100:.2f}%")

    # Print a space separated list of significant cluster IDs
    significant_clusters = t_test_results[t_test_results['p_value'] < 0.05]['cluster_ID']
    significant_cluster_ids = significant_clusters.tolist()
    significant_cluster_ids_str = ' '.join(map(str, significant_cluster_ids)) + '\n'
    print(f"Significant cluster IDs: {significant_cluster_ids_str}")

    # Make output dir
    output_dir = 'cluster_validation_summary'
    Path(output_dir).mkdir(exist_ok=True)

    # Save the summary dataframe as a .csv file
    summary_df.to_csv(Path(output_dir) / 'cluster_validation_summary.csv', index=False)

    # Save the t-test results as a .csv file
    t_test_results.to_csv(Path(output_dir) / 'cluster_t_test_results.csv', index=False)

    # Save the # of sig. clusters, total clusters, and cluster validation rate to a .txt file
    with open(Path(output_dir) / 'cluster_validation_summary.txt', 'w') as f:
        f.write(f"Number of sig. clusters: {len(t_test_results[t_test_results['p_value'] < 0.05])}\n")
        f.write(f"Total number of clusters: {len(t_test_results)}\n")
        f.write(f"Cluster validation rate: {len(t_test_results[t_test_results['p_value'] < 0.05]) / len(t_test_results) * 100:.2f}%\n")
        f.write(f"Significant cluster IDs: {significant_cluster_ids_str}\n")

    # Save the valid cluster IDs to a .txt file
    with open(Path(output_dir) / 'significant_cluster_IDs.txt', 'w') as f:
        f.write(significant_cluster_ids_str)
    
    print(f"Saved results in [bright_magenta]./cluster_validation_summary/")

if __name__ == '__main__':
    install()
    main()