#!/usr/bin/env python3

"""
Use ``cstats`` (``cs``) from UNRAVEL to validate clusters based on differences in validation metrics across groups.

Input files:
    - `*_data.csv` from ``cstats_validation`` (e.g., cell_density_data.csv, label_density_data.csv,
      mean_in_cluster_data.csv, or mean_in_seg_in_cluster_data.csv)

Outputs:
    - ./_valid_clusters_stats/

Note:
    - Organize data in directories for each comparison (e.g., psilocybin > saline, etc.)
    - This script loops through all subdirectories in the current working directory.
    - Each subdir should contain CSV files with cluster-level validation metric data.
    - The first 2 groups reflect the main comparison for validation rates.
    - Clusters are not considered valid if the effect direction does not match the expected direction.

Columns in .csv files from ``cstats_validation``:
    sample, cluster_ID, metric, value, value_type, support, support_type, aggregation_method, cluster_volume, ...

Columns in the older .csv files (still works):
    sample, cluster_ID, <cell_count|label_volume>, cluster_volume, <cell_density|label_density>, ...

CSV naming conventions:
    - Condition: first word before '_' in the file name
    - Side: last word before .csv (LH or RH)

Example unilateral inputs in the subdirs:
    - condition1_sample01_<cell|label>_density_data.csv 
    - condition1_sample02_<cell|label>_density_data.csv
    - condition2_sample03_<cell|label>_density_data.csv
    - condition2_sample04_<cell|label>_density_data.csv

Example bilateral inputs (if any file has _LH.csv or _RH.csv, the command will attempt to pool LH/RH data per sample when both sides are present):
    - condition1_sample01_<cell|label>_density_data_LH.csv
    - condition1_sample01_<cell|label>_density_data_RH.csv

Examples:
    - Grouping data by condition prefixes: 
        ``cstats`` --groups psilocybin saline --condition_prefixes saline psilocybin
        - This will treat all 'psilocybin*' conditions as one group and all 'saline*' conditions as another
        - Since there will then effectively be two conditions in this case, they will be compared using a t-test

Usage for t-tests:
------------------
    cstats --groups <group1> <group2> -hg <group1|group2> [-cp <condition_prefixes>] [-alt <two-sided|less|greater>] [-pvt <p_value_threshold.txt>] [-v]

Usage for Tukey's tests:
------------------------
    cstats --groups <group1> <group2> <group3> <group4> ... -hg <group1|group2> [-cp <condition_prefixes>] [-alt <two-sided|less|greater>] [-pvt <p_value_threshold.txt>] [-v]
"""

import re

import numpy as np
import pandas as pd
from glob import glob
from pathlib import Path
from rich import print
from rich.traceback import install
from rich.live import Live
from scipy.stats import ttest_ind
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar

from unravel.cluster_stats.stats_table import cluster_summary

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('--groups', help='List of group prefixes. 2 groups --> t-test. >2 --> Tukey\'s tests (The first 2 groups reflect the main comparison for validation rates)', nargs='*', required=True, action=SM)
    reqs.add_argument('-hg', '--higher_group', help='Specify the group that is expected to have a higher mean based on the direction of the p value map', required=True)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-cp', '--condition_prefixes', help='Condition prefixes to group data (e.g., see info for examples)',  nargs='*', default=None, action=SM)
    opts.add_argument('-alt', "--alternate", help="Number of tails and direction ('two-sided' \[default], 'less' [group1 < group2], or 'greater')", default='two-sided', action=SM)
    opts.add_argument('-pvt', '--p_val_txt', help='Name of the file w/ the corrected p value thresh (e.g., from cstats_fdr). Default: p_value_threshold.txt', default='p_value_threshold.txt', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Test grouping of conditions. Test w/ label densities data. Could set up dunnett's tests and/or holm sidak tests.

def detect_metric_schema(first_df):
    """Detect whether input CSVs use the new generic metric schema or the older density schema.

    Returns:
        dict with:
            metric_name
            value_col
            support_col
            support_type
            aggregation_method
            value_type
            schema_type
    """
    # New generic schema from cstats_validation
    if {'metric', 'value', 'support', 'support_type', 'aggregation_method'}.issubset(first_df.columns):
        return {
            'metric_name': first_df['metric'].iloc[0],
            'value_col': 'value',
            'support_col': 'support',
            'support_type': first_df['support_type'].iloc[0],
            'aggregation_method': first_df['aggregation_method'].iloc[0],
            'value_type': first_df['value_type'].iloc[0] if 'value_type' in first_df.columns else None,
            'schema_type': 'generic'
        }

    # Backward-compatible fallback
    if 'cell_count' in first_df.columns and 'cell_density' in first_df.columns:
        return {
            'metric_name': 'cell_density',
            'value_col': 'cell_density',
            'support_col': 'cell_count',
            'support_type': 'cell_count',
            'aggregation_method': 'recompute_from_support_and_volume',
            'value_type': 'density',
            'schema_type': 'legacy'
        }

    if 'label_volume' in first_df.columns and 'label_density' in first_df.columns:
        return {
            'metric_name': 'label_density',
            'value_col': 'label_density',
            'support_col': 'label_volume',
            'support_type': 'label_volume',
            'aggregation_method': 'recompute_from_support_and_volume',
            'value_type': 'density',
            'schema_type': 'legacy'
        }

    raise ValueError("Unrecognized data columns in input files.")

def load_metric_csv_for_stats(file, schema):
    """Load one metric CSV and normalize it to a standard schema for stats.

    Returns DataFrame with columns:
        condition, sample, side, cluster_ID, value, support, cluster_volume
    """
    df = pd.read_csv(file)

    condition_name = Path(file).name.split('_')[0]
    side = None
    if str(file).endswith('_LH.csv'):
        side = 'LH'
    elif str(file).endswith('_RH.csv'):
        side = 'RH'

    df['condition'] = condition_name
    df['side'] = side

    if schema['schema_type'] == 'generic':
        keep_cols = ['condition', 'sample', 'side', 'cluster_ID', 'value', 'support']
        if 'cluster_volume' in df.columns:
            keep_cols.append('cluster_volume')
        out = df[keep_cols].copy()

    else:
        keep_cols = ['condition', 'sample', 'side', 'cluster_ID', schema['support_col'], schema['value_col']]
        if 'cluster_volume' in df.columns:
            keep_cols.append('cluster_volume')
        out = df[keep_cols].copy()
        out = out.rename(columns={
            schema['support_col']: 'support',
            schema['value_col']: 'value'
        })

    return out

def condition_selector(df, condition, unique_conditions, condition_column='condition'):
    """Create a condition selector to handle pooling of data in a DataFrame based on specified conditions.
    This function checks if the 'condition' is exactly present in the 'condition' column or is a prefix of any condition in this column. 
    If the exact condition is found, it selects those rows.
    If the condition is a prefix (e.g., 'saline' matches 'saline-1', 'saline-2'), it selects all rows where the 'condition' column starts with this prefix.
    An error is raised if the condition is neither found as an exact match nor as a prefix.
    
    Args:
        df (pd.DataFrame): DataFrame whose 'condition' column contains the conditions of interest.
        condition (str): The condition or prefix of interest.
        unique_conditions (list): List of unique conditions in the 'condition' column to validate against.
        
    Returns:
        pd.Series: A boolean Series to select rows based on the condition."""
    
    if condition in unique_conditions:
        return (df[condition_column] == condition)
    elif any(cond.startswith(condition) for cond in unique_conditions):
        return df[condition_column].str.startswith(condition)
    else:
        raise ValueError(f"    [red]Condition {condition} not recognized!")

def pool_sample_metric(sample_df, metric_name, aggregation_method):
    """Pool LH/RH rows for one sample+condition+cluster if both sides are present.

    If only one side is present, return that side unchanged.
    """
    sides_present = set(sample_df['side'].dropna().tolist())

    # If both sides are present, pool them
    if sides_present == {'LH', 'RH'}:
        support_sum = sample_df['support'].sum()
        cluster_volume_sum = sample_df['cluster_volume'].sum() if 'cluster_volume' in sample_df.columns else np.nan

        if aggregation_method == 'recompute_from_support_and_volume':
            if cluster_volume_sum == 0 or pd.isna(cluster_volume_sum):
                pooled_value = np.nan
            else:
                pooled_value = support_sum / cluster_volume_sum
                if metric_name == 'label_density':
                    pooled_value *= 100

        elif aggregation_method == 'weighted_mean_by_support':
            if support_sum == 0 or pd.isna(support_sum):
                pooled_value = np.nan
            else:
                pooled_value = np.average(sample_df['value'], weights=sample_df['support'])

        else:
            raise ValueError(
                f"Unsupported aggregation_method: {aggregation_method}. "
                "Expected 'recompute_from_support_and_volume' or 'weighted_mean_by_support'."
            )

        return pd.DataFrame([{
            'condition': sample_df['condition'].iloc[0],
            'sample': sample_df['sample'].iloc[0],
            'side': 'pooled',
            'cluster_ID': sample_df['cluster_ID'].iloc[0],
            'support': support_sum,
            'cluster_volume': cluster_volume_sum,
            'value': pooled_value
        }])

    # If there's a mix of sides (e.g., LH and no side), this is unexpected. Raise an error.
    if len(sample_df) > 1:
        raise ValueError(
            "Unexpected duplicate rows for one-sided data for "
            f"condition={sample_df['condition'].iloc[0]}, "
            f"sample={sample_df['sample'].iloc[0]}, "
            f"cluster_ID={sample_df['cluster_ID'].iloc[0]}. "
            "Expected either one row, or exactly one LH and one RH row."
        )

    # If only one side is present, keep it as-is
    return sample_df.copy()

def cluster_validation_data_df(metric_name, value_col, support_col, support_type,
                               aggregation_method, has_hemisphere, csv_files,
                               groups, condition_prefixes=None):
    """Aggregate metric data from all CSVs, optionally pool bilateral data per sample,
    optionally group conditions by prefix, and return a standardized DataFrame.

    Returns DataFrame with columns:
        condition, sample, side, cluster_ID, support, cluster_volume, value
    """

    # Build a schema object for load_metric_csv_for_stats()
    schema = {
        'metric_name': metric_name,
        'value_col': value_col,
        'support_col': support_col,
        'support_type': support_type,
        'aggregation_method': aggregation_method,
        'schema_type': 'generic' if value_col == 'value' and support_col == 'support' else 'legacy'
    }

    rows = []

    if has_hemisphere:
        print(f"Organizing [red1 bold]hemisphere-aware[/red1 bold] [dark_orange bold]{metric_name}[/] data...")
    else:
        print(f"Organizing [red1 bold]unilateral[/] [dark_orange bold]{metric_name}[/] data...")

    for file in csv_files:
        condition_name = Path(file).name.split('_')[0]
        if condition_name not in groups:
            continue

        temp = load_metric_csv_for_stats(file, schema)
        rows.append(temp)

    if not rows:
        return pd.DataFrame()

    data_df = pd.concat(rows, ignore_index=True)

    if condition_prefixes is not None:
        unique_conditions = data_df['condition'].unique().tolist()
        print(f"Unique conditions before grouping with condition_prefixes: {unique_conditions}")

        for condition_prefix in condition_prefixes:
            cond_selector = condition_selector(data_df, condition_prefix, unique_conditions, condition_column='condition')
            data_df.loc[cond_selector, 'condition'] = condition_prefix

        unique_conditions = data_df['condition'].unique().tolist()
        print(f"Unique conditions after grouping with condition_prefixes: {unique_conditions}")

    # If no hemisphere tags exist at all, do not pool
    if not has_hemisphere:
        return data_df

    # Pool per condition+sample+cluster only when both LH and RH are present
    pooled_rows = []
    grouped = data_df.groupby(['condition', 'sample', 'cluster_ID'], dropna=False)

    for _, sample_df in grouped:
        pooled_rows.append(
            pool_sample_metric(
                sample_df=sample_df,
                metric_name=metric_name,
                aggregation_method=aggregation_method
            )
        )

    pooled_df = pd.concat(pooled_rows, ignore_index=True)
    return pooled_df


def valid_clusters_t_test(df, group1, group2, value_col='value', alternative='two-sided'):
    """Perform unpaired t-tests for each cluster in the DataFrame and return the results as a DataFrame.
    
    Args:
        - df (pd.DataFrame): the DataFrame containing the cluster data
            - Columns: 'condition', 'sample', 'cluster_ID', value_col, support, cluster_volume
        - group1 (str): the name of the first group
        - group2 (str): the name of the second group
        - value_col (str): the column name for the metric values to compare
        - alternative (str): the alternative hypothesis ('two-sided', 'less', or 'greater') for the t-test
    
    Returns:
        - stats_df (pd.DataFrame): the DataFrame containing the t-test results
            - Columns: 'cluster_ID', 'comparison', 'higher_mean_group', 'p-value', 'significance'
    """
    stats_df = pd.DataFrame()

    for cluster_id in df['cluster_ID'].unique():
        cluster_data = df[df['cluster_ID'] == cluster_id]
        group1_data = np.array(cluster_data[cluster_data['condition'] == group1][value_col].values.ravel())
        group2_data = np.array(cluster_data[cluster_data['condition'] == group2][value_col].values.ravel())

        if len(group1_data) == 0 or len(group2_data) == 0:
            temp_df = pd.DataFrame({'cluster_ID': [cluster_id], 'p-value': [np.nan]})
            stats_df = pd.concat([stats_df, temp_df], ignore_index=True)
            continue

        t_stat, p_value = ttest_ind(group1_data, group2_data, equal_var=True, alternative=alternative)
        p_value = float(f"{p_value:.6f}")

        temp_df = pd.DataFrame({'cluster_ID': [cluster_id], 'p-value': [p_value]})
        stats_df = pd.concat([stats_df, temp_df], ignore_index=True)

    stats_df['group1'] = group1
    stats_df['group2'] = group2
    stats_df['comparison'] = stats_df['group1'] + ' vs ' + stats_df['group2']
    stats_df['group1_mean'] = stats_df['cluster_ID'].apply(
        lambda cluster_id: df[(df['cluster_ID'] == cluster_id) & (df['condition'] == group1)][value_col].mean()
    )
    stats_df['group2_mean'] = stats_df['cluster_ID'].apply(
        lambda cluster_id: df[(df['cluster_ID'] == cluster_id) & (df['condition'] == group2)][value_col].mean()
    )
    stats_df['meandiff'] = stats_df['group1_mean'] - stats_df['group2_mean']
    stats_df['higher_mean_group'] = stats_df['meandiff'].apply(lambda diff: group1 if diff > 0 else group2)
    stats_df['significance'] = stats_df['p-value'].apply(
        lambda p: '****' if p < 0.0001 else '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'n.s.'
    )

    stats_df.drop(columns=['group1_mean', 'group2_mean', 'meandiff', 'group1', 'group2'], inplace=True)
    stats_df = stats_df[['cluster_ID', 'comparison', 'higher_mean_group', 'p-value', 'significance']]

    return stats_df

def perform_tukey_test(df, value_col='value'):
    """Perform Tukey's HSD test for each cluster in the DataFrame and return the results as a DataFrame."""
    stats_df = pd.DataFrame()
    progress, task_id = initialize_progress_bar(len(df['cluster_ID'].unique()), "[default]Processing clusters...")

    with Live(progress):
        for cluster_id in df['cluster_ID'].unique():
            cluster_data = df[df['cluster_ID'] == cluster_id]
            if not cluster_data.empty:
                values = np.array(cluster_data[value_col].values.ravel())
                group_labels = np.array(cluster_data['condition'].values.ravel())

                if len(np.unique(group_labels)) < 2:
                    progress.update(task_id, advance=1)
                    continue

                tukey_results = pairwise_tukeyhsd(endog=values, groups=group_labels, alpha=0.05)
                test_results_df = pd.DataFrame(data=tukey_results.summary().data[1:], columns=tukey_results.summary().data[0])
                test_results_df['cluster_ID'] = cluster_id
                test_results_df['higher_mean_group'] = test_results_df.apply(
                    lambda row: row['group1'] if row['meandiff'] < 0 else row['group2'],
                    axis=1
                )
                stats_df = pd.concat([stats_df, test_results_df], ignore_index=True)

            progress.update(task_id, advance=1)

    stats_df.rename(columns={'p-adj': 'p-value'}, inplace=True)
    stats_df['comparison'] = stats_df['group1'] + ' vs ' + stats_df['group2']
    stats_df.drop(columns=['lower', 'upper', 'reject', 'meandiff', 'group1', 'group2'], inplace=True)
    stats_df['significance'] = stats_df['p-value'].apply(
        lambda p: '****' if p < 0.0001 else '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'n.s.'
    )
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
    if len(subdirs) == 1 and subdirs[0].name == '_valid_clusters_stats':
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

        first_df = pd.read_csv(csv_files[0])

        try:
            schema = detect_metric_schema(first_df)
        except ValueError as e:
            print(f"Error: {e}")
            return

        metric_name = schema['metric_name']
        value_col = schema['value_col']
        support_col = schema['support_col']
        support_type = schema['support_type']
        aggregation_method = schema['aggregation_method']

        # Get the total number of clusters
        total_clusters = len(first_df['cluster_ID'].unique())

        # Check if any files contain hemisphere indicators
        has_hemisphere = any('_LH.csv' in str(file.name) or '_RH.csv' in str(file.name) for file in csv_files)

        # Aggregate the data from all .csv files and pool the data if hemispheres are present
        data_df = cluster_validation_data_df(
            metric_name=metric_name,
            value_col=value_col,
            support_col=support_col,
            support_type=support_type,
            aggregation_method=aggregation_method,
            has_hemisphere=has_hemisphere,
            csv_files=csv_files,
            groups=args.groups,
            condition_prefixes=args.condition_prefixes
        )
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
            stats_df = valid_clusters_t_test(
                data_df,
                args.groups[0],
                args.groups[1],
                value_col='value',
                alternative=args.alternate
            )
        else:
            # Perform a Tukey's test
            print(f"Running [gold1 bold]Tukey's tests")
            stats_df = perform_tukey_test(data_df, value_col='value')

        # Validate the clusters based on the expected direction of the effect
        if args.higher_group not in args.groups:
            print(f"    [red1]Error: The specified higher group '{args.higher_group}' is not one of the groups.")
            return
        expected_direction = '>' if args.higher_group == args.groups[0] else '<'
        incongruent_clusters = stats_df[(stats_df['higher_mean_group'] != args.higher_group) & (stats_df['significance'] != 'n.s.')]['cluster_ID'].tolist()
        with open(output_dir / 'incongruent_clusters.txt', 'w') as f:
            f.write('\n'.join(map(str, incongruent_clusters)))
        print(f"Expected effect direction: [green bold]{args.groups[0]} {expected_direction} {args.groups[1]}")

        pre_invalid_significant_clusters = stats_df[stats_df['significance'] != 'n.s.']['cluster_ID']

        if not incongruent_clusters and len(pre_invalid_significant_clusters) > 0:
            print("All significant clusters are congruent with the expected direction")
        elif not incongruent_clusters and len(pre_invalid_significant_clusters) == 0:
            print("[red1 bold]No significant clusters found.")
        else:
            print(f"{len(incongruent_clusters)} of {total_clusters} clusters are incongruent with the expected direction.")
            print("Although they had a significant difference, they are not considered valid.")
            print("'incongruent_clusters.txt' lists cluster IDs for incongruent clusters.")

        # Invalidate incongruent clusters
        stats_df['significance'] = stats_df.apply(
            lambda row: 'n.s.' if row['cluster_ID'] in incongruent_clusters else row['significance'],
            axis=1
        )

        # Recompute significant clusters after invalidation
        significant_cluster_ids = stats_df[stats_df['significance'] != 'n.s.']['cluster_ID'].unique().tolist()
        significant_cluster_ids_str = ' '.join(map(str, significant_cluster_ids))

        # Save the results to a .csv file
        stats_results_csv = output_dir / 't-test_results.csv' if len(args.groups) == 2 else output_dir / 'tukey_results.csv'
        stats_df.to_csv(stats_results_csv, index=False)

        # Extract the FDR q value from the first csv file (float after 'FDR' or 'q' in the file name)
        first_csv_name = csv_files[0]
        if 'FDR' in first_csv_name.name or 'q' in first_csv_name.name:
            stem = first_csv_name.stem  # removes .csv
            match = re.search(r'(?:FDR|q)(\d*\.?\d+)', stem)
            fdr_q = float(match.group(1)) if match else None
        else:
            fdr_q = None  # No FDR/q value found
        
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

        # Print validation info
        if fdr_q is not None:
            print(f"FDR q: [cyan bold]{fdr_q}[/] == p-value threshold: [cyan bold]{p_value_thresh}")
        else:
            print(f"P-value threshold: [cyan bold]{p_value_thresh}")
        print(f"Valid cluster IDs: {significant_cluster_ids_str}")
        print(f"[default]# of valid / total #: [bright_magenta]{len(significant_cluster_ids)} / {total_clusters}")
        validation_rate = len(significant_cluster_ids) / total_clusters * 100
        print(f"Cluster validation rate: [purple bold]{validation_rate:.2f}%")

        # Save the raw data dataframe as a .csv file
        if len(args.groups) == 2:
            raw_data_csv = output_dir / 'raw_data_for_t-test.csv'
        else:
            raw_data_csv = output_dir / 'raw_data_for_tukey.csv'

        data_df.to_csv(raw_data_csv, index=False)

        # Save the # of sig. clusters, total clusters, and cluster validation rate to a .txt file
        validation_inf_txt = output_dir / 'cluster_validation_info_t-test.txt' if len(args.groups) == 2 else output_dir / 'cluster_validation_info_tukey.txt'
        with open(validation_inf_txt, 'w') as f:
            f.write(f"Direction: {args.groups[0]} {expected_direction} {args.groups[1]}\n")
            if fdr_q is not None:
                f.write(f"FDR q: {fdr_q} == p-value threshold {p_value_thresh}\n")
            else:
                f.write(f"P-value threshold: {p_value_thresh}\n")
            f.write(f"Valid cluster IDs: {significant_cluster_ids_str}\n")
            f.write(f"# of valid / total #: {len(significant_cluster_ids)} / {total_clusters}\n")
            f.write(f"Cluster validation rate: {validation_rate:.2f}%\n")

        # Save the valid cluster IDs to a .txt file
        valid_cluster_IDs = output_dir / 'valid_cluster_IDs_t-test.txt' if len(args.groups) == 2 else output_dir / 'valid_cluster_IDs_tukey.txt'
        with open(valid_cluster_IDs, 'w') as f:
            f.write(significant_cluster_ids_str)
        
        # Save cluster validation info for ``cstats_summary`` 
        data_df = pd.DataFrame({
            'Direction': [f"{args.groups[0]} {expected_direction} {args.groups[1]}"],
            'P value thresh': [p_value_thresh],
            'Valid clusters': [significant_cluster_ids_str],
            '# of valid clusters': [len(significant_cluster_ids)],
            '# of clusters': [total_clusters],
            'Validation rate': [f"{validation_rate}%"]
        })
        if fdr_q is not None:
            data_df['FDR q'] = fdr_q

        data_df.to_csv(validation_info_csv, index=False)

    # Concat all cluster_validation_info.csv files
    if len(args.groups) == 2:
        cluster_summary('cluster_validation_info_t-test.csv', 'cluster_validation_summary_t-test.csv')
    else:
        cluster_summary('cluster_validation_info_tukey.csv', 'cluster_validation_summary_tukey.csv')

    verbose_end_msg()


if __name__ == '__main__':
    main()