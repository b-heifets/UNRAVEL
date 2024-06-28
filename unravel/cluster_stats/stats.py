#!/usr/bin/env python3

"""
Use ``cluster_stats`` from UNRAVEL to validate clusters based on differences in cell/object or label density w/ t-tests.    

T-test usage:  
------------- 
    cluster_stats --groups <group1> <group2> -hg <group1|group2>

Tukey's test usage: 
-------------------
    cluster_stats --groups <group1> <group2> <group3> <group4> ... -hg <group1|group2>

Note: 
    - Organize data in directories for each comparison (e.g., psilocybin > saline, etc.)
    - This script will loop through all directories in the current working dir and process the data in each subdir.
    - Each subdir should contain .csv files with the density data for each cluster.
    - The first 2 groups reflect the main comparison for validation rates.
    - Clusters are not considered valid if the effect direction does not match the expected direction.

Input files: 
    <asterisk>_density_data.csv from ``cluster_validation`` (e.g., in each subdir named after the rev_cluster_index.nii.gz file)    

CSV naming conventions:
    - Condition: first word before '_' in the file name
    - Side: last word before .csv (LH or RH)

Example unilateral inputs in the subdirs:
    - condition1_sample01_<cell|label>_density_data.csv 
    - condition1_sample02_<cell|label>_density_data.csv
    - condition2_sample03_<cell|label>_density_data.csv
    - condition2_sample04_<cell|label>_density_data.csv

Example bilateral inputs (if any file has _LH.csv or _RH.csv, the command will attempt to pool data):
    - condition1_sample01_<cell|label>_density_data_LH.csv
    - condition1_sample01_<cell|label>_density_data_RH.csv

Examples:
    - Grouping data by condition prefixes: 
        ``cluster_stats`` --groups psilocybin saline --condition_prefixes saline psilocybin
        - This will treat all 'psilocybin*' conditions as one group and all 'saline*' conditions as another
        - Since there will then effectively be two conditions in this case, they will be compared using a t-test

Columns in the .csv files:
    sample, cluster_ID, <cell_count|label_volume>, cluster_volume, <cell_density|label_density>, ...

Outputs:
    - ./_valid_clusters_stats/
"""

import argparse
import numpy as np
import pandas as pd
from glob import glob
from pathlib import Path
from rich import print
from rich.traceback import install
from rich.live import Live
from scipy.stats import ttest_ind
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar

from unravel.cluster_stats.stats_table import cluster_summary

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('--groups', help='List of group prefixes. 2 groups --> t-test. >2 --> Tukey\'s tests (The first 2 groups reflect the main comparison for validation rates)',  nargs='+', required=True)
    parser.add_argument('-cp', '--condition_prefixes', help='Condition prefixes to group data (e.g., see info for examples)',  nargs='*', default=None, action=SM)
    parser.add_argument('-hg', '--higher_group', help='Specify the group that is expected to have a higher mean based on the direction of the p value map', required=True)
    parser.add_argument('-alt', "--alternate", help="Number of tails and direction ('two-sided' [default], 'less' [group1 < group2], or 'greater')", default='two-sided', action=SM)
    parser.add_argument('-pvt', '--p_val_txt', help='Name of the file w/ the corrected p value thresh (e.g., from cluster_fdr). Default: p_value_threshold.txt', default='p_value_threshold.txt', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: Test grouping of conditions. Test w/ label densities data. Could set up dunnett's tests and/or holm sidak tests.


def condition_selector(df, condition, unique_conditions, condition_column='Conditions'):
    """Create a condition selector to handle pooling of data in a DataFrame based on specified conditions.
    This function checks if the 'condition' is exactly present in the 'Conditions' column or is a prefix of any condition in this column. 
    If the exact condition is found, it selects those rows.
    If the condition is a prefix (e.g., 'saline' matches 'saline-1', 'saline-2'), it selects all rows where the 'Conditions' column starts with this prefix.
    An error is raised if the condition is neither found as an exact match nor as a prefix.
    
    Args:
        df (pd.DataFrame): DataFrame whose 'Conditions' column contains the conditions of interest.
        condition (str): The condition or prefix of interest.
        unique_conditions (list): List of unique conditions in the 'Conditions' column to validate against.
        
    Returns:
        pd.Series: A boolean Series to select rows based on the condition."""
    
    if condition in unique_conditions:
        return (df[condition_column] == condition)
    elif any(cond.startswith(condition) for cond in unique_conditions):
        return df[condition_column].str.startswith(condition)
    else:
        raise ValueError(f"    [red]Condition {condition} not recognized!")

def cluster_validation_data_df(density_col, has_hemisphere, csv_files, groups, data_col, data_col_pooled, condition_prefixes=None):
    """Aggregate the data from all .csv files, pool bilateral data if hemispheres are present, optionally pool data by condition, and return the DataFrame.
    
    Args:
        - density_col (str): the column name for the density data
        - has_hemisphere (bool): whether the data files contain hemisphere indicators (e.g., _LH.csv or _RH.csv)
        - csv_files (list): a list of .csv files
        - groups (list): a list of group names
        - data_col (str): the column name for the data (cell_count or label_volume)
        - data_col_pooled (str): the column name for the pooled data
        
    Returns:    
        - data_df (pd.DataFrame): the DataFrame containing the cluster data
            - Columns: 'condition', 'sample', 'cluster_ID', 'cell_count', 'cluster_volume', 'cell_density'"""

    # Create a results dataframe
    data_df = pd.DataFrame(columns=['condition', 'sample', 'side', 'cluster_ID', data_col, 'cluster_volume', density_col])

    if has_hemisphere:
        # Process files with hemisphere pooling
        print(f"Organizing [red1 bold]bilateral[/red1 bold] [dark_orange bold]{density_col}[/] data from [orange1 bold]_LH.csv[/] and [orange1 bold]_RH.csv[/] files...")
        for file in csv_files:
            condition_name = str(file.name).split('_')[0]
            if condition_name in groups:
                side = str(file.name).split('_')[-1].split('.')[0]
                df = pd.read_csv(file)
                df = df.drop(columns=['xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax'])
                df['condition'] = condition_name  # Add the condition to the df
                df['side'] = side  # Add the side 
                data_df = pd.concat([data_df, df], ignore_index=True)

        # Pool data by condition, sample, and cluster_ID
        data_df = data_df.groupby(['condition', 'sample', 'cluster_ID']).agg(  # Group by condition, sample, and cluster_ID
            **{data_col_pooled: pd.NamedAgg(column=data_col, aggfunc='sum'),  # Sum cell_count or label_volume, unpacking the dict into keyword arguments for the .agg() method 
            'pooled_cluster_volume': pd.NamedAgg(column='cluster_volume', aggfunc='sum')}  # Sum cluster_volume
        ).reset_index() # Reset the index to avoid a multi-index dataframe

        data_df[density_col] = data_df[data_col_pooled] / data_df['pooled_cluster_volume']  # Add a column for cell/label density
    else:
        # Process files without hemisphere pooling
        print(f"Organizing [red1 bold]unilateral[/] [dark_orange bold]{density_col}[/] data...")
        for file in csv_files:
            df = pd.read_csv(file)
            condition_name = file.stem.split('_')[0]
            if condition_name in groups:
                df['condition'] = str(file.name).split('_')[0]
                df = df.drop(columns=[data_col, 'cluster_volume', 'xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax'])
                data_df = pd.concat([data_df, df], ignore_index=True)

    if condition_prefixes is not None:
        unique_conditions = data_df['condition'].unique().tolist()
        print(f"Unique conditions before grouping with condition_prefixes: {unique_conditions}")

        # Iterate over the condition prefixes
        for condition_prefix in condition_prefixes:
            # Adjust condition selectors based on potential pooling (return a boolean Series to select rows based on the condition)
            cond_selector = condition_selector(data_df, condition_prefix, unique_conditions)

            # Update the conditions in 'condition' column to reflect the pooled conditions
            data_df.loc[cond_selector, 'condition'] = condition_prefix

        unique_conditions = data_df['condition'].unique().tolist()
        print(f"Unique conditions after grouping with condition_prefixes: {unique_conditions}")

    return data_df

def valid_clusters_t_test(df, group1, group2, density_col, alternative='two-sided'):
    """Perform unpaired t-tests for each cluster in the DataFrame and return the results as a DataFrame.
    
    Args:
        - df (pd.DataFrame): the DataFrame containing the cluster data
            - Columns: 'condition', 'sample', 'cluster_ID', 'cell_count', 'cluster_volume', 'cell_density'
        - group1 (str): the name of the first group
        - group2 (str): the name of the second group
        - density_col (str): the column name for the density data
        - alternative (str): the alternative hypothesis ('two-sided', 'less', or 'greater')
        
    Returns:
        - stats_df (pd.DataFrame): the DataFrame containing the t-test results
            - Columns: 'cluster_ID', 'comparison', 'higher_mean_group', 'p-value', 'significance'
    """

    stats_df = pd.DataFrame()
    for cluster_id in df['cluster_ID'].unique():
        cluster_data = df[df['cluster_ID'] == cluster_id]
        group1_data = np.array([value for value in cluster_data[cluster_data['condition'] == group1][density_col].values.ravel()])
        group2_data = np.array([value for value in cluster_data[cluster_data['condition'] == group2][density_col].values.ravel()])
        
        # Perform unpaired two-tailed t-test
        t_stat, p_value = ttest_ind(group1_data, group2_data, equal_var=True, alternative=alternative)
        p_value = float(f"{p_value:.6f}")

        # Create a temporary DataFrame for the current t-test result
        temp_df = pd.DataFrame({'cluster_ID': [cluster_id], 'p-value': [p_value]})

        # Use pd.concat to append the temporary DataFrame
        stats_df = pd.concat([stats_df, temp_df], ignore_index=True)

    # Add a column the higher mean group
    stats_df['group1'] = group1  # Add columns for the group names
    stats_df['group2'] = group2
    stats_df['comparison'] = stats_df['group1'] + ' vs ' + stats_df['group2']
    stats_df['group1_mean'] = stats_df['cluster_ID'].apply(lambda cluster_id: df[(df['cluster_ID'] == cluster_id) & (df['condition'] == group1)][density_col].mean())
    stats_df['group2_mean'] = stats_df['cluster_ID'].apply(lambda cluster_id: df[(df['cluster_ID'] == cluster_id) & (df['condition'] == group2)][density_col].mean())
    stats_df['meandiff'] = stats_df['group1_mean'] - stats_df['group2_mean']
    stats_df['higher_mean_group'] = stats_df['meandiff'].apply(lambda diff: group1 if diff > 0 else group2)
    stats_df['significance'] = stats_df['p-value'].apply(lambda p: '****' if p < 0.0001 else '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'n.s.')

    # Update columns
    stats_df.drop(columns=['group1_mean', 'group2_mean', 'meandiff', 'group1', 'group2'], inplace=True)
    stats_df = stats_df[['cluster_ID', 'comparison', 'higher_mean_group', 'p-value', 'significance']]

    return stats_df

def perform_tukey_test(df, groups, density_col):
    """Perform Tukey's HSD test for each cluster in the DataFrame and return the results as a DataFrame

    Args:
        - df (pd.DataFrame): the DataFrame containing the cluster data
            - Columns: 'condition', 'sample', 'cluster_ID', 'cell_count', 'cluster_volume', 'cell_density'
        - groups (list): a list of group names
        - density_col (str): the column name for the density data

    Returns:
        - stats_df (pd.DataFrame): the DataFrame containing the Tukey's HSD test results
            - Columns: 'cluster_ID', 'comparison', 'higher_mean_group', 'p-value', 'significance'
    """

    stats_df = pd.DataFrame()
    progress, task_id = initialize_progress_bar(len(df['cluster_ID'].unique()), "[default]Processing clusters...")
    with Live(progress):
        for cluster_id in df['cluster_ID'].unique():
            cluster_data = df[df['cluster_ID'] == cluster_id]
            if not cluster_data.empty:
                # Flatten the data
                densities = np.array([value for value in cluster_data[density_col].values.ravel()])
                groups = np.array([value for value in cluster_data['condition'].values.ravel()])

                # Perform Tukey's HSD test
                tukey_results = pairwise_tukeyhsd(endog=densities, groups=groups, alpha=0.05)

                # Extract significant comparisons from Tukey's results 
                # Columns: group1, group2, meandiff, p-adj, lower, upper, reject, cluster_ID
                test_results_df = pd.DataFrame(data=tukey_results.summary().data[1:], columns=tukey_results.summary().data[0])

                # Add the cluster ID to the DataFrame
                test_results_df['cluster_ID'] = cluster_id

                # Add a column for the group with the higher mean density
                test_results_df['higher_mean_group'] = test_results_df.apply(lambda row: row['group1'] if row['meandiff'] < 0 else row['group2'], axis=1)

                # Append the current test results to the overall DataFrame 
                stats_df = pd.concat([stats_df, test_results_df], ignore_index=True)

            progress.update(task_id, advance=1)

    # Update columns
    stats_df.rename(columns={'p-adj': 'p-value'}, inplace=True)
    stats_df['comparison'] = stats_df['group1'] + ' vs ' + stats_df['group2']
    stats_df.drop(columns=['lower', 'upper', 'reject', 'meandiff', 'group1', 'group2'], inplace=True)
    stats_df['significance'] = stats_df['p-value'].apply(lambda p: '****' if p < 0.0001 else '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'n.s.')
    stats_df = stats_df[['cluster_ID', 'comparison', 'higher_mean_group', 'p-value', 'significance']]

    return stats_df 

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    current_dir = Path.cwd()

    # Check for subdirectories in the current working directory
    subdirs = [d for d in current_dir.iterdir() if d.is_dir()]
    if not subdirs:
        print(f"    [red1]No directories found in the current working directory: {current_dir}")
        return
    if subdirs[0].name == '_valid_clusters_stats':
        print(f"    [red1]Only the '_valid_clusters_stats' directory found in the current working directory: {current_dir}")
        print("    [red1]The script was likely run from a subdirectory instead of a directory containing subdirectories.")
        return

    # Iterate over all subdirectories in the current working directory
    for subdir in subdirs:
        print(f"\nProcessing directory: [default bold]{subdir.name}[/]")

        # Load all .csv files in the current subdirectory
        csv_files = list(subdir.glob('*.csv'))
        if not csv_files:
            continue  # Skip directories with no CSV files

        # Make output dir
        output_dir = Path(subdir) / '_valid_clusters_stats'
        output_dir.mkdir(exist_ok=True)
        validation_info_csv = output_dir / 'cluster_validation_info_t-test.csv' if len(args.groups) == 2 else output_dir / 'cluster_validation_info_tukey.csv'
        if validation_info_csv.exists():
            continue

        # Load the first .csv file to check for data columns and set the appropriate column names
        first_df = pd.read_csv(csv_files[0])
        if 'cell_count' in first_df.columns:
            data_col, data_col_pooled, density_col = 'cell_count', 'pooled_cell_count', 'cell_density'
        elif 'label_volume' in first_df.columns:
            data_col, data_col_pooled, density_col = 'label_volume', 'pooled_label_volume', 'label_density'
        else:
            print("Error: Unrecognized data columns in input files.")
            return
        
        # Get the total number of clusters
        total_clusters = len(first_df['cluster_ID'].unique())

        # Check if any files contain hemisphere indicators
        has_hemisphere = any('_LH.csv' in str(file.name) or '_RH.csv' in str(file.name) for file in csv_files)

        # Aggregate the data from all .csv files and pool the data if hemispheres are present
        data_df = cluster_validation_data_df(density_col, has_hemisphere, csv_files, args.groups, data_col, data_col_pooled, args.condition_prefixes)
        if data_df.empty:
            print("    [red1]No data files match the specified groups. The prefixes of the csv files must match the group names.")
            continue

        # Check the number of groups and perform the appropriate statistical test
        if len(args.groups) == 2:
            # Perform a t-test
            if args.alternate not in ['two-sided', 'less', 'greater']:
                print("Error: Invalid alternative hypothesis. Please specify 'two-sided', 'less', or 'greater'.")
                return
            elif args.alternate == 'two-sided':
                print(f"Running [gold1 bold]{args.alternate} unpaired t-tests")
            else:
                print(f"Running [gold1 bold]one-sided unpaired t-tests")
            stats_df = valid_clusters_t_test(data_df, args.groups[0], args.groups[1], density_col, args.alternate)
        else:
            # Perform a Tukey's test
            print(f"Running [gold1 bold]Tukey's tests")
            stats_df = perform_tukey_test(data_df, args.groups, density_col)

        # Validate the clusters based on the expected direction of the effect
        if args.higher_group not in args.groups:
            print(f"    [red1]Error: The specified higher group '{args.higher_group}' is not one of the groups.")
            return
        expected_direction = '>' if args.higher_group == args.groups[0] else '<'
        incongruent_clusters = stats_df[(stats_df['higher_mean_group'] != args.higher_group) & (stats_df['significance'] != 'n.s.')]['cluster_ID'].tolist()

        with open(output_dir / 'incongruent_clusters.txt', 'w') as f:
            f.write('\n'.join(map(str, incongruent_clusters)))
        
        print(f"Expected effect direction: [green bold]{args.groups[0]} {expected_direction} {args.groups[1]}")

        if not incongruent_clusters:
            print("All significant clusters are congruent with the expected direction")
        else:
            print(f"{len(incongruent_clusters)} of {total_clusters} clusters are incongruent with the expected direction.")
            print (f"Although they had a significant difference, they not considered valid.")
            print (f"'incongruent_clusters.txt' lists cluster IDs for incongruent clusters.")

        # Invalidate clusters that are incongruent with the expected direction
        stats_df['significance'] = stats_df.apply(lambda row: 'n.s.' if row['cluster_ID'] in incongruent_clusters else row['significance'], axis=1)

        # Remove invalidated clusters from the list of significant clusters
        significant_clusters = stats_df[stats_df['significance'] != 'n.s.']['cluster_ID']
        significant_cluster_ids = significant_clusters.unique().tolist()
        significant_cluster_ids_str = ' '.join(map(str, significant_cluster_ids))

        # Save the results to a .csv file
        stats_results_csv = output_dir / 't-test_results.csv' if len(args.groups) == 2 else output_dir / 'tukey_results.csv'
        stats_df.to_csv(stats_results_csv, index=False)

        # Extract the FDR q value from the first csv file (float after 'FDR' or 'q' in the file name)
        first_csv_name = csv_files[0]
        fdr_q = float(str(first_csv_name).split('FDR')[-1].split('q')[-1].split('_')[0])
        
        # Extract the p-value threshold from the specified .txt file
        try:
            p_val_txt = next(Path(subdir).glob('**/*' + args.p_val_txt), None)
            if p_val_txt is None:
                # If no file is found, print an error message and skip further processing for this directory
                print(f"    [red1]No p-value file found matching '{args.p_val_txt}' in directory {subdir}. Please check the file name and path.")
                import sys ; sys.exit()
            with open(p_val_txt, 'r') as f:
                p_value_thresh = float(f.read())
        except Exception as e:
            # Handle other exceptions that may occur during file opening or reading
            print(f"An error occurred while processing the p-value file: {e}")
            import sys ; sys.exit()

        # Print validation info: 
        print(f"FDR q: [cyan bold]{fdr_q}[/] == p-value threshold: [cyan bold]{p_value_thresh}")
        print(f"Valid cluster IDs: {significant_cluster_ids_str}")
        print(f"[default]# of valid / total #: [bright_magenta]{len(significant_cluster_ids)} / {total_clusters}")
        validation_rate = len(significant_cluster_ids) / total_clusters * 100
        print(f"Cluster validation rate: [purple bold]{validation_rate:.2f}%")

        # Save the raw data dataframe as a .csv file
        raw_data_csv_prefix = output_dir / 'raw_data_for_t-test' if len(args.groups) == 2 else output_dir / 'raw_data_for_tukey'
        if has_hemisphere:
            data_df.to_csv(output_dir / f'{raw_data_csv_prefix}_pooled.csv', index=False)
        else: 
            data_df.to_csv(output_dir / f'{raw_data_csv_prefix}.csv', index=False)

        # Save the # of sig. clusters, total clusters, and cluster validation rate to a .txt file
        validation_inf_txt = output_dir / 'cluster_validation_info_t-test.txt' if len(args.groups) == 2 else output_dir / 'cluster_validation_info_tukey.txt'
        with open(validation_inf_txt, 'w') as f:
            f.write(f"Direction: {args.groups[0]} {expected_direction} {args.groups[1]}\n")
            f.write(f"FDR q: {fdr_q} == p-value threshold {p_value_thresh}\n")
            f.write(f"Valid cluster IDs: {significant_cluster_ids_str}\n")
            f.write(f"# of valid / total #: {len(significant_cluster_ids)} / {total_clusters}\n")
            f.write(f"Cluster validation rate: {validation_rate:.2f}%\n")

        # Save the valid cluster IDs to a .txt file
        valid_cluster_IDs = output_dir / 'valid_cluster_IDs_t-test.txt' if len(args.groups) == 2 else output_dir / 'valid_cluster_IDs_tukey.txt'
        with open(valid_cluster_IDs, 'w') as f:
            f.write(significant_cluster_ids_str)
        
        # Save cluster validation info for ``cluster_summary`` 
        data_df = pd.DataFrame({
            'Direction': [f"{args.groups[0]} {expected_direction} {args.groups[1]}"],
            'FDR q': [fdr_q],
            'P value thresh': [p_value_thresh],
            'Valid clusters': [significant_cluster_ids_str],
            '# of valid clusters': [len(significant_cluster_ids)],
            '# of clusters': [total_clusters],
            'Validation rate': [f"{len(significant_cluster_ids) / total_clusters * 100}%"]
        })
        
        data_df.to_csv(validation_info_csv, index=False)

    # Concat all cluster_validation_info.csv files
    if len(args.groups) == 2:
        cluster_summary('cluster_validation_info_t-test.csv', 'cluster_validation_summary_t-test.csv')
    else:
        cluster_summary('cluster_validation_info_tukey.csv', 'cluster_validation_summary_tukey.csv')

    verbose_end_msg()


if __name__ == '__main__':
    main()