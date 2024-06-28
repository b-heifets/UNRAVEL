#!/usr/bin/env python3

"""
Use ``effect_sizes_sex_rel`` from UNRAVEL to calculate the relative effect size for (comparing sexes) for a comparison between two groups for each cluster [or a valid cluster list].
    
Usage
-----
    effect_sizes_sex_rel -i densities.csv -c1 saline -c2 psilocybin

Inputs:
    - CSV with densities (Columns: Samples, Sex, Conditions, Cluster_1, Cluster_2, ...)
    - Enter M or F in the Sex column.

Arguments:
    - -c1 and -c2 should match the condition name in the Conditions column of the input CSV or be a prefix of the condition name.
    
Outputs CSV w/ the relative effect size (F>M) and CI for each cluster:
    <input>_Hedges_g_<condition_1>_<condition_2>_F_gt_M.csv

If -c is used, outputs a CSV with the effect sizes and CI for valid clusters:
    <input>_Hedges_g_<condition_1>_<condition_2>_F_gt_M_valid_clusters.csv

The effect size is calculated as the unbiased Hedge\'s g effect sizes (corrected for sample size): 
    Hedges' g = ((c2-c1)/spooled*corr_factor)
    CI = Hedges' g +/- t * SE
    0.2 - 0.5 = small effect; 0.5 - 0.8 = medium; 0.8+ = large
"""

import argparse
import os
import pandas as pd
from rich.traceback import install
from scipy.stats import t
from termcolor import colored

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input_csv', help='CSV with densities (Columns: Samples, Sex, Conditions, Cluster_1, Cluster_2, ...)', action=SM)
    parser.add_argument('-c1', '--condition_1', help='First condition of interest from csv (e.g., saline [data matching prefix pooled])', action=SM)
    parser.add_argument('-c2', '--condition_2', help='Second condition (e.g, psilocybin [data matching prefix pooled])', action=SM)
    parser.add_argument('-c', '--clusters', help='Space separated list of valid cluster IDs (default: process all clusters)', default=None, nargs='*', type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


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
        raise ValueError(colored(f"Condition {condition} not recognized!", 'red'))

def filter_dataframe(df, cluster_list):
    # If no clusters provided, return the original DataFrame
    if cluster_list is None:
        return df
    
    # Keep only rows where 'Cluster' value after removing "Cluster_" matches an integer in the cluster list
    return df[df['Cluster'].str.replace('Cluster_', '').astype(int).isin(cluster_list)]

# Create a series with the mean, std, and count for each cluster
def mean_std_count(df, sex, selector, cluster_columns):
    mean = df[(df['Sex'] == sex) & selector][cluster_columns].mean()
    std = df[(df['Sex'] == sex) & selector][cluster_columns].std()
    count = df[(df['Sex'] == sex) & selector][cluster_columns].count()
    return mean, std, count

# Calculate the relative effect size between sexes for each cluster
def relative_hedges_g(df, condition_1, condition_2): 

    df = pd.read_csv(df)
    cluster_columns = [col for col in df if col.startswith('Cluster')]
    
    # Create a list of unique values in 'Conditions'
    unique_conditions = df['Conditions'].unique().tolist()

    # Adjust condition selectors based on potential pooling
    cond1_selector = condition_selector(df, condition_1, unique_conditions)
    cond2_selector = condition_selector(df, condition_2, unique_conditions)

    # Create a series with the mean, std, and count for each cluster
    mean_F_cond1, std_F_cond1, count_F_cond1 = mean_std_count(df, 'F', cond1_selector, cluster_columns)
    mean_M_cond1, std_M_cond1, count_M_cond1 = mean_std_count(df, 'M', cond1_selector, cluster_columns)
    mean_F_cond2, std_F_cond2, count_F_cond2 = mean_std_count(df, 'F', cond2_selector, cluster_columns)
    mean_M_cond2, std_M_cond2, count_M_cond2 = mean_std_count(df, 'M', cond2_selector, cluster_columns)
    
    # Calculate the N for each sex
    n_F = count_F_cond1 + count_F_cond2
    n_M = count_M_cond1 + count_M_cond2

    # Calulate the standard deviation of F_diff and M_diff
    std_F_diff = (std_F_cond1**2 + std_F_cond2**2)**0.5
    std_M_diff = (std_M_cond1**2 + std_M_cond2**2)**0.5

    # Calculate pooled standard deviation for each cluster
    spooled = (((n_F -1) * std_F_diff**2 + (n_M -1) * std_M_diff**2)/(n_F + n_M - 2))**0.5

    # Calculate the mean difference between conditions
    F_diff = mean_F_cond2 - mean_F_cond1
    M_diff = mean_M_cond2 - mean_M_cond1

    # Calculate Hedges' g
    g = (F_diff - M_diff) / spooled

    # Calculate the correction factor
    correction_factor = 1 - 3 / (4 * (n_F + n_M) - 9)

    # Apply the correction factor to Hedges' g
    d = g * correction_factor

    # Calculate the standard error of Hedges' g
    se = (((n_F + n_M) / (n_F * n_M)) + ((d**2) / (2 * (n_F + n_M - 2)))) ** 0.5

    # For a two-tailed t-test, you want the critical value for alpha/2 in one tail
    alpha = 0.05
    degrees_of_freedom = (n_F + n_M) - 2

    # Get the critical t-value for alpha/2
    critical_t_value = t.ppf(1 - alpha/2, degrees_of_freedom)

    # Calculate the confidence interval
    ci = critical_t_value * se

    # Calculate the lower and upper bounds of the confidence interval
    lower = d - ci
    upper = d + ci

    # Create a dataframe combining Hedges' g, lower and upper CIs (organized for plotting w/ Prism --> Grouped data)
    results_df = pd.DataFrame({
    'Cluster': cluster_columns,
    'Hedges_g': d,
    'Upper_Limit': upper,
    'Lower_Limit': lower,
    })

    # Replace "Cluster_" with an empty string in the "Cluster" column
    results_df['Cluster'] = results_df['Cluster'].str.replace('Cluster_', '')

    # Reverse the order of the rows (so that the first cluster is at the top when graphed in Prism)
    results_df = results_df.iloc[::-1]

    return results_df


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Generate CSVs with relative sex effect sizes
    f_gt_m_effect_sizes = relative_hedges_g(args.input_csv, args.condition_1, args.condition_2)
    output = f"{os.path.splitext(args.input_csv)[0]}_Hedges_g_{args.condition_1}_{args.condition_2}_F_gt_M.csv"
    f_gt_m_effect_sizes.to_csv(output, index=False)

    if args.clusters is not None:
        # Filter DataFrame based on valid clusters list
        relative_effect_sizes_filtered = filter_dataframe(f_gt_m_effect_sizes, args.clusters)
        output = f"{os.path.splitext(args.input_csv)[0]}_Hedges_g_{args.condition_1}_{args.condition_2}_F_gt_M_valid_clusters.csv"
        relative_effect_sizes_filtered.to_csv(output, index=False)

    verbose_end_msg()


if __name__ == '__main__':
    main()