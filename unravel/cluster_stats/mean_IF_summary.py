#!/usr/bin/env python3

"""
Use ``cluster_mean_IF_summary`` from UNRAVEL to output plots of mean IF intensities for each cluster in atlas space.

Usage for t-tests:
------------------
    cluster_mean_IF_summary --order Control Treatment --labels Control Treatment -t ttest

Usage for Tukey's tests w/ reordering and renaming of conditions:
-----------------------------------------------------------------
    cluster_mean_IF_summary --order group3 group2 group1 --labels Group_3 Group_2 Group_1

Note:
    - The first word of the csv inputs is used for the the group names (underscore separated).

Inputs: 
    - <asterisk>.csv files in the working dir with these columns: sample, cluster_ID, mean_IF_intensity

Prereqs:
    - Generate CSV inputs withs ``cluster_IF_mean``
    - Add conditions to input CSV file names: ``utils_prepend`` -sk $SAMPLE_KEY -f

Outputs:
    - cluster_mean_IF_summary/cluster_<cluster_id>.pdf for each cluster
    - If significant differences are found, a prefix '_' is added to the filename to sort the files
"""

import argparse
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import seaborn as sns
import textwrap
from rich import print
from rich.traceback import install
from pathlib import Path
from scipy.stats import ttest_ind, dunnett
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('--cluster_ids', help='List of cluster IDs to process (Default: process all clusters)', nargs='*', type=int, action=SM)
    parser.add_argument('--order', nargs='*', help='Group Order for plotting (must match 1st word of CSVs)', action=SM)
    parser.add_argument('--labels', nargs='*', help='Group Labels in same order', action=SM)
    parser.add_argument('-t', '--test', help='Choose between "tukey", "dunnett", and "ttest" post-hoc tests. (Default: tukey)', default='tukey', choices=['tukey', 'dunnett', 'ttest'], action=SM)
    parser.add_argument('-alt', "--alternate", help="Number of tails and direction for Dunnett's test {'two-sided', 'less' (means < ctrl), 'greater'}. Default: two-sided", default='two-sided', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: Also output csv to summarise t-test/Tukey/Dunnett results like in ``cluster_stats``. Make symbols transparent. Add option to pass in symbol colors for each group. Add ABA coloring to plots. 
# TODO: CSVs are loaded for each cluster. It would be more efficient to load them once for processing all clusters. 
# TODO: Perhaps functions in this script could be made more generic and used in rstats_mean_IF_summary.py as well.
# TODO: Save a CSV with the results for each cluster.
# TODO: Check that this works for other test types (tested with t-tests).


# Set Arial as the font
mpl.rcParams['font.family'] = 'Arial'

def load_data(cluster_id):
    data = []
    
    # Load all CSVs in the directory
    for filename in os.listdir():
        if filename.endswith('.csv'):
            group_name = filename.split("_")[0]
            df = pd.read_csv(filename)

            # Filter by the cluster ID
            mean_intensity = df[df["cluster_ID"] == cluster_id]["mean_IF_intensity"].values

            if len(mean_intensity) > 0:
                data.append({
                    'group': group_name,
                    'mean_intensity': mean_intensity[0]
                })
    
    if data:
        return pd.DataFrame(data)
    else:
        raise ValueError(f"    [red1]No data found for cluster ID: {cluster_id}")

def perform_t_tests(df, order):
    """Perform t-tests between groups in the DataFrame."""
    comparisons = []
    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            group1, group2 = order[i], order[j]
            data1 = df[df['group'] == group1]['mean_intensity']
            data2 = df[df['group'] == group2]['mean_intensity']
            t_stat, p_value = ttest_ind(data1, data2)
            comparisons.append({
                'group1': group1,
                'group2': group2,
                'p-adj': p_value
            })
    return pd.DataFrame(comparisons)

def plot_data(cluster_id, order=None, labels=None, test_type='tukey', alt='two-sided'):
    df = load_data(cluster_id)

    if 'group' not in df.columns:
        raise KeyError(f"    [red1]'group' column not found in the DataFrame for {cluster_id}. Ensure the CSV files contain the correct data.")
    
    # Define a list of potential colors
    predefined_colors = [
        '#2D67C8', # blue
        '#D32525', # red
        '#27AF2E', # green
        '#FFD700', # gold
        '#FF6347', # tomato
        '#8A2BE2', # blueviolet
        # ... add more colors if needed
    ]
    
    # Check if order is provided and slice the color list accordingly
    if order:
        selected_colors = predefined_colors[:len(order)]
        group_colors = dict(zip(order, selected_colors))
    else:
        groups_in_df = df['group'].unique().tolist()
        selected_colors = predefined_colors[:len(groups_in_df)]
        group_colors = dict(zip(groups_in_df, selected_colors))

    # If group order and labels are provided, update the DataFrame
    if order and labels:
        df['group'] = df['group'].astype(pd.CategoricalDtype(categories=order, ordered=True))
        df = df.sort_values('group')
        labels_mapping = dict(zip(order, labels))
        df['group_label'] = df['group'].map(labels_mapping)
    else:
        df['group_label'] = df['group']
    
    # Bar plot
    plt.figure(figsize=(4, 4))
    ax = sns.barplot(x='group_label', y='mean_intensity', data=df, color='white', errorbar=('se'), capsize=0.1, linewidth=2, edgecolor='black')

    # Formatting
    ax.set_ylabel('Mean IF Intensity', weight='bold')
    ax.set_xticks(np.arange(len(df['group_label'].unique())))
    ax.set_xticklabels(ax.get_xticklabels(), weight='bold')
    ax.tick_params(axis='both', which='major', width=2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_linewidth(2)
    ax.spines['left'].set_linewidth(2)

    # Swarm plot
    sns.swarmplot(x='group_label', y='mean_intensity', hue='group', data=df, palette=group_colors, size=8, linewidth=1, edgecolor='black')
    
    # Remove the legend created by hue
    if ax.legend_:
        ax.legend_.remove()

    # Perform the chosen post-hoc test
    if test_type == 'tukey':
        test_results = pairwise_tukeyhsd(df['mean_intensity'], df['group']).summary()
        test_df = pd.DataFrame(test_results.data[1:], columns=test_results.data[0])
    elif test_type == 'dunnett':
        # Assuming control is the first group in the order (change as needed)
        control_data = df[df['group'] == order[0]]['mean_intensity'].values
        experimental_data = [df[df['group'] == group]['mean_intensity'].values for group in order[1:]]
        test_stats = dunnett(*experimental_data, control=control_data, alternative=alt)
        # Convert the result to a DataFrame similar to the Tukey output for easier handling
        test_df = pd.DataFrame({
            'group1': [order[0]] * len(test_stats.pvalue),
            'group2': order[1:],
            'p-adj': test_stats.pvalue
        })
        test_df['reject'] = test_df['p-adj'] < 0.05
    elif test_type == 'ttest':
        test_df = perform_t_tests(df, order)
        test_df['reject'] = test_df['p-adj'] < 0.05

    significant_comparisons = test_df[test_df['reject'] == True]
    y_max = df['mean_intensity'].max()
    y_min = df['mean_intensity'].min()
    height_diff = (y_max - y_min) * 0.1
    y_pos = y_max + 0.5 * height_diff

    groups = df['group'].unique()

    for _, row in significant_comparisons.iterrows():
        group1, group2 = row['group1'], row['group2']
        x1 = np.where(groups == group1)[0][0]
        x2 = np.where(groups == group2)[0][0]

        plt.plot([x1, x1, x2, x2], [y_pos, y_pos + height_diff, y_pos + height_diff, y_pos], lw=1.5, c='black')
        
        if row['p-adj'] < 0.0001:
            sig = '****'
        elif row['p-adj'] < 0.001:
            sig = '***'
        elif row['p-adj'] < 0.01:
            sig = '**'
        else:
            sig = '*'
            
        plt.text((x1+x2)*.5, y_pos + 0.8*height_diff, sig, horizontalalignment='center', size='xx-large', color='black', weight='bold')
        y_pos += 3 * height_diff

    # Calculate y-axis limits
    y_max = df['mean_intensity'].max()
    y_min = df['mean_intensity'].min()
    height_diff = (y_max - y_min) * 0.1
    y_pos = y_max + 0.5 * height_diff

    # Ensure the y-axis starts from the minimum value, allowing for negative values
    plt.ylim(y_min - 2 * height_diff, y_pos + 2 * height_diff)

    # plt.ylim(0, y_pos + 2*height_diff)
    ax.set_xlabel(None)

    # Save the plot
    output_folder = Path('cluster_mean_IF_summary')
    output_folder.mkdir(parents=True, exist_ok=True)

    title = f"Cluster: {cluster_id}"
    wrapped_title = textwrap.fill(title, 42)  # wraps at x characters. Adjust as needed.
    plt.title(wrapped_title)
    plt.tight_layout()

    is_significant = not significant_comparisons.empty
    file_prefix = '_' if is_significant else ''
    file_name = f"{file_prefix}cluster_{cluster_id}.pdf"
    plt.savefig(output_folder / file_name)

    plt.close()

    return test_df


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if (args.order and not args.labels) or (not args.order and args.labels):
        raise ValueError("Both --order and --labels must be provided together.")

    if args.order and args.labels and len(args.order) != len(args.labels):
        raise ValueError("The number of entries in --order and --labels must match.")
    
    # Print CSVs in the working dir
    print(f'\n[bold]CSVs in the working dir to process (the first word defines the groups): \n')
    for filename in os.listdir():
        if filename.endswith('.csv'):
            print(f'    {filename}')
    print()

    # If cluster IDs are provided, use them; otherwise, get all cluster IDs from the first CSV
    clusters_to_process = args.cluster_ids if args.cluster_ids else pd.read_csv(next(Path().glob('*.csv'))).cluster_ID.unique()

    # Process each cluster ID
    test_df_all = pd.DataFrame()
    for cluster_id in clusters_to_process:
        test_df = plot_data(cluster_id, args.order, args.labels, test_type=args.test, alt=args.alternate)

        # Add the cluster ID to the DataFrame
        test_df['cluster_ID'] = cluster_id

        # Make cluster_ID the first column
        test_df = test_df[['cluster_ID', 'group1', 'group2', 'p-adj', 'reject']]

        # Concat the results for each cluster
        test_df_all = pd.concat([test_df_all, test_df], ignore_index=True)
    
    test_df_all['significance'] = test_df_all['p-adj'].apply(lambda p: '****' if p < 0.0001 else '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'n.s.')
    
    # Drop the reject column
    test_df_all = test_df_all.drop(columns='reject')

    # Save the results to a CSV
    output_folder = Path('cluster_mean_IF_summary')
    output_folder.mkdir(parents=True, exist_ok=True)
    if args.test == 'tukey':
        test_df_all.to_csv(output_folder / 'cluster_mean_IF_summary_tukey.csv', index=False)
    elif args.test == 'dunnett':
        test_df_all.to_csv(output_folder / 'cluster_mean_IF_summary_dunnett.csv', index=False)
    elif args.test == 'ttest':
        test_df_all.to_csv(output_folder / 'cluster_mean_IF_summary_ttest.csv', index=False)

    print(f'\n{test_df_all}\n')

    verbose_end_msg()
    

if __name__ == '__main__':
    main()