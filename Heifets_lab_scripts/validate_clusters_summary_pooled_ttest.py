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
    parser = argparse.ArgumentParser(description='Validate clusters with t-tests after pooling data from left and right hemispheres', formatter_class=SuppressMetavar)
    parser.epilog = """Inputs: *.csv from validate_clusters.py (they must be in the working directory)

Naming conventions:
- Condition: first word before '_' in the file name
- Side: last word before .csv

Example input: 
- condition1_sample01_LH.csv

Outputs: cluster_validation_summary.csv"""
    return parser.parse_args()


def main():


    # Load all .csv files in the current directory
    csv_files = glob('*.csv')

    # Create a summary dataframe
    summary_df = pd.DataFrame(columns=['condition', 'sample', 'side', 'cluster_ID', 'cell_count', 'cluster_volume', 'cell_density'])

    for file in csv_files:
        # Get the condition name and side from the file name
        condition_name = file.split('_')[0]
        side = file.split('_')[-1].split('.')[0]

        # Load the .csv file into a dataframe
        df = pd.read_csv(file)

        # Add the condition and side to the dataframe
        df['condition'] = condition_name
        df['side'] = side

        # Add the dataframe to the summary dataframe
        summary_df = pd.concat([summary_df, df], ignore_index=True)

    # Pool cell counts and cluster volumes by condition, sample, and cluster_ID
    pooled_df = summary_df.groupby(['condition', 'sample', 'cluster_ID']).agg(
        pooled_cell_count=pd.NamedAgg(column='cell_count', aggfunc='sum'),
        pooled_cluster_volume=pd.NamedAgg(column='cluster_volume', aggfunc='sum')
    ).reset_index()

    # Calculate cell density for each pooled cluster
    pooled_df['cell_density'] = pooled_df['pooled_cell_count'] / pooled_df['pooled_cluster_volume']

    # Calculate unpaied 2-tailed t-tests for each cluster

    # Create an empty DataFrame to store t-test results
    t_test_results = pd.DataFrame(columns=['cluster_ID', 'p_value'])

    # Get the unique condition names
    condition_names = pooled_df['condition'].unique()
    group_one, group_two = condition_names[0], condition_names[1]

    # Iterate over each unique cluster ID
    for cluster_id in pooled_df['cluster_ID'].unique():
        # Filter data for this cluster ID
        cluster_data = pooled_df[pooled_df['cluster_ID'] == cluster_id]
    
        # Assuming you have two conditions, group_one and group_two
        group_one_data = pd.to_numeric(cluster_data[cluster_data['condition'] == group_one]['cell_density'], errors='coerce') # coerce to NaN if not numeric
        group_two_data = pd.to_numeric(cluster_data[cluster_data['condition'] == group_two]['cell_density'], errors='coerce')

        # Perform unpaired two-tailed t-test
        t_stat, p_value = stats.ttest_ind(group_one_data.dropna(), group_two_data.dropna(), equal_var=False)  # equal_var=False for Welch's t-test

        # Create a temporary DataFrame for the current t-test result
        temp_df = pd.DataFrame({'cluster_ID': [cluster_id], 'p_value': [p_value]})

        # Use pd.concat to append the temporary DataFrame to t_test_results
        t_test_results = pd.concat([t_test_results, temp_df], ignore_index=True)

        # Add column with askerisks for significance (* for p < 0.05, ** for p < 0.01, *** for p < 0.001, **** for p < 0.0001, n.s. for p > 0.05)
        t_test_results['significance'] = t_test_results['p_value'].apply(lambda p: '****' if p < 0.0001 else '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'n.s.')
        

    # Display t-test results
    print(f'\n{t_test_results}')

    # Print the number of clusters with significant differences
    print(f"\nNumber of sig. clusters: {len(t_test_results[t_test_results['p_value'] < 0.05])}")

    # Print the total number of clusters
    print(f"Total number of clusters: {len(t_test_results)}")

    # Print the cluster validation rate
    print(f"Cluster validation rate: {len(t_test_results[t_test_results['p_value'] < 0.05]) / len(t_test_results) * 100:.2f}%")

    # Print a space separated list of significant cluster IDs
    significant_clusters = t_test_results[t_test_results['p_value'] < 0.05]['cluster_ID']
    significant_cluster_ids = significant_clusters.tolist()
    significant_cluster_ids_str = ' '.join(map(str, significant_cluster_ids))
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
    
    print(f"\nSaved results in ./{output_dir}/\n")
    

if __name__ == '__main__':
    install()
    main()
