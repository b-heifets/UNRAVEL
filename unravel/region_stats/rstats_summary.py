#!/usr/bin/env python3

"""
Use ``rstats_summary`` from UNRAVEL to plot cell densensities for each region and summarize results.\n CSV columns: Region_ID,Side,Name,Abbr,Saline_sample06,Saline_sample07,...,MDMA_sample01,...,Meth_sample23,...

Usage:
------
    rstats_summary --groups Saline MDMA Meth -d 10000 -hemi r

To do: 
    Add module for Dunnett's tests (don't use this option for now)

Outputs:
    Plots and a summary CSV to the current directory.    

Example hex code list (flank arg w/ double quotes): ['#2D67C8', '#27AF2E', '#D32525', '#7F25D3']

Note: 
    - regional_summary_CCFv3-2020.csv is in UNRAVEL/unravel/core/csvs/
    - It has columns: Region_ID, ID_Path, Region, Abbr, General_Region, R, G, B
    - Alternatively, use regional_summary.csv or provide a custom CSV with the same columns.
"""

import argparse
import ast
import os
from pathlib import Path
import re
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import textwrap
from rich import print
from rich.live import Live
from rich.traceback import install
from scipy.stats import ttest_ind
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('--groups', nargs='*', help='Group prefixes (e.g., saline meth cbsMeth)', action=SM)
    parser.add_argument('-t', '--test_type', help="Type of statistical test to use: 'tukey' (default), 'dunnett', or 't-test'", choices=['tukey', 'dunnett', 't-test'], default='tukey', action=SM)
    parser.add_argument('-hemi', help="Hemisphere(s) to process (r, l or both)", choices=['r', 'l', 'both'], required=True, action=SM)
    parser.add_argument('-c', '--ctrl_group', help="Control group name for t-test or Dunnett's tests", action=SM)
    parser.add_argument('-d', '--divide', type=float, help='Divide the cell densities by the specified value for plotting (default is None)', default=None, action=SM)
    parser.add_argument('-y', '--ylabel', help='Y-axis label (Default: cell_density)', default='cell_density', action=SM)
    parser.add_argument('-csv', '--csv_path', help='CSV name or path/name.csv. Default: regional_summary_CCFv3-2020.csv', default='regional_summary_CCFv3-2020.csv', action=SM)
    parser.add_argument('-b', '--bar_color', help="ABA (default), #hex_code, Seaborn palette, or #hex_code list matching # of groups", default='ABA', action=SM)
    parser.add_argument('-s', '--symbol_color', help="ABA, #hex_code, Seaborn palette (Default: light:white), or #hex_code list matching # of groups", default='light:white', action=SM)
    parser.add_argument('-o', '--output', help='Output directory for plots (Default: <args.test_type>_plots)', action=SM)
    parser.add_argument('-alt', "--alternate", help="Number of tails and direction for t-tests or Dunnett's tests ('two-sided' [default], 'less' [group1 < group2], or 'greater')", default='two-sided', action=SM)
    parser.add_argument('-e', "--extension", help="File extension for plots. Choices: pdf (default), svg, eps, tiff, png)", default='pdf', choices=['pdf', 'svg', 'eps', 'tiff', 'png'], action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: Dunnett's test. LH/RH averaging via summing counts and volumes before dividing counts by volumes (rather than averaging densities directly). Set up label density quantification.


def get_region_details(region_id, df):
    # Adjust to account for the unique region IDs.
    region_row = df[(df["Region_ID"] == region_id) | (df["Region_ID"] == region_id + 20000)].iloc[0]
    return region_row["Region"], region_row["Abbr"]

def parse_color_argument(color_arg, num_groups, region_id, csv_path):
    if isinstance(color_arg, str):
        if color_arg.startswith('[') and color_arg.endswith(']'):
            # It's a string representation of a list, so evaluate it safely
            color_list = ast.literal_eval(color_arg)    
            if len(color_list) != num_groups:
                raise ValueError(f"The number of colors provided ({len(color_list)}) does not match the number of groups ({num_groups}).")
            return color_list
        elif color_arg.startswith('#'):
            # It's a single hex color, use it for all groups
            return [color_arg] * num_groups
        elif color_arg == 'ABA':
            # Determine the RGB color for bars based on the region_id
            combined_region_id = region_id if region_id < 20000 else region_id - 20000
            if csv_path == 'regional_summary.csv' or csv_path == 'regional_summary_CCFv3-2020.csv': 
                results_df = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / csv_path) #(Region_ID,ID_Path,Region,Abbr,General_Region,R,G,B)
            else:
                results_df = pd.read_csv(csv_path)
            region_rgb = results_df[results_df['Region_ID'] == combined_region_id][['R', 'G', 'B']]
            rgb = tuple(region_rgb.iloc[0].values)
            rgb_normalized = tuple([x / 255.0 for x in rgb])
            ABA_color = sns.color_palette([rgb_normalized] * num_groups)
            return ABA_color
        else:
            # It's a named seaborn palette
            return sns.color_palette(color_arg, num_groups)
    else:
        # It's already a list (this would be the case for default values or if the input method changes)
        return color_arg    

def summarize_significance(test_df, id):
    """Summarize the results of the statistical tests.
    
    Args:
        - test_df (DataFrame): the DataFrame containing the test results (w/ columns: group1, group2, p-value, meandiff)
        - id (int): the region or cluster ID

    Returns:
        - summary_df (DataFrame): the DataFrame containing the summarized results
    """
    summary_rows = []
    for _, row in test_df.iterrows():
        group1, group2 = row['group1'], row['group2']
        # Determine significance level
        sig = ''
        if row['p-value'] < 0.0001:
            sig = '****'
        elif row['p-value'] < 0.001:
            sig = '***'
        elif row['p-value'] < 0.01:
            sig = '**'
        elif row['p-value'] < 0.05:
            sig = '*'
        # Determine which group has a higher mean
        meandiff = row['meandiff']
        higher_group = group2 if meandiff > 0 else group1
        summary_rows.append({
            'Region_ID': id,
            'Comparison': f'{group1} vs {group2}',
            'p-value': row['p-value'],
            'Higher_Mean_Group': higher_group,
            'Significance': sig
        })
    return pd.DataFrame(summary_rows)

def process_and_plot_data(df, region_id, region_name, region_abbr, side, out_dir, group_columns, args):

    # Reshaping the data for plotting
    reshaped_data = []
    for prefix in args.groups:
        for value in df[group_columns[prefix]].values.ravel():
            reshaped_data.append({'group': prefix, 'density': value})
    reshaped_df = pd.DataFrame(reshaped_data)

    # Plotting
    mpl.rcParams['font.family'] = 'Arial'
    plt.figure(figsize=(4, 4))

    groups = reshaped_df['group'].unique()
    num_groups = len(groups)

    # Parse the color arguments
    bar_color = parse_color_argument(args.bar_color, num_groups, region_id, args.csv_path)
    symbol_color = parse_color_argument(args.symbol_color, num_groups, region_id, args.csv_path)

    # Coloring the bars and symbols
    ax = sns.barplot(x='group', y='density', data=reshaped_df, errorbar=('se'), capsize=0.1, palette=bar_color, linewidth=2, edgecolor='black')
    sns.stripplot(x='group', y='density', hue='group', data=reshaped_df, palette=symbol_color, alpha=0.5, size=8, linewidth=0.75, edgecolor='black')

    # Calculate y_max and y_min based on the actual plot
    y_max = ax.get_ylim()[1]
    y_min = ax.get_ylim()[0]
    height_diff = (y_max - y_min) * 0.05  # Adjust the height difference as needed
    y_pos = y_max * 1.05  # Start just above the highest bar

    # Check which test to perform
    if args.test_type == 't-test':
        # Perform t-test for each group against the control group
        control_data = df[group_columns[args.ctrl_group]].values.ravel()
        test_results = []
        for prefix in args.groups:
            if prefix != args.ctrl_group:
                other_group_data = df[group_columns[prefix]].values.ravel()
                t_stat, p_value = ttest_ind(other_group_data, control_data, equal_var=True, alternative=args.alternate) # Switched to equal_var=True and alternative=args.alternate
                meandiff = np.mean(other_group_data) - np.mean(control_data)
                # if args.alternate == 'less' and meandiff < 0:
                #     p_value /= 2  # For one-tailed test, halve the p-value if the alternative is 'less'
                #     t_stat = -t_stat  # Flip the sign for 'less'
                # elif args.alternate == 'greater' and meandiff > 0:
                #     p_value /= 2  # For one-tailed test, halve the p-value if the alternative is 'greater'
                # elif args.alternate == 'two-sided':
                #     pass # No change in p value needed for two-sided test
                # else: # Effect direction not consistent with hypothesis 
                #     p_value = 1
                test_results.append({
                    'group1': args.ctrl_group,
                    'group2': prefix,
                    't-stat': t_stat,
                    'p-value': p_value,
                    'meandiff': np.mean(other_group_data) - np.mean(control_data)
                })

        test_results_df = pd.DataFrame(test_results)
        significant_comparisons = test_results_df[test_results_df['p-value'] < 0.05]

    # elif args.test_type == 'dunnett':

    #     # Extract the data for the control group and the other groups
    #     data = [df[group_columns[prefix]].values.ravel() for prefix in args.groups if prefix != args.ctrl_group]
    #     control_data = df[group_columns[args.ctrl_group]].values.ravel()

    #     # The * operator unpacks the list so that each array is a separate argument, as required by dunnett
    #     dunnett_results = dunnett(*data, control=control_data, alternative=args.alternate)

    #     group2_data = [df[group_columns[prefix]].values.ravel() for prefix in args.groups if prefix != args.ctrl_group]

    #     # Convert the result to a DataFrame
    #     test_results_df = pd.DataFrame({
    #         'group1': [args.ctrl_group] * len(dunnett_results.pvalue),
    #         'group2': [prefix for prefix in args.groups if prefix != args.ctrl_group],
    #         'p-value': dunnett_results.pvalue,
    #         'meandiff': np.mean(group2_data, axis=1) - np.mean(control_data) # Calculate the mean difference between each group and the control group
    #     })
    #     significant_comparisons = test_results_df[test_results_df['p-value'] < 0.05]

    elif args.test_type == 'tukey':

        # Conduct Tukey's HSD test
        densities = np.array([value for prefix in args.groups for value in df[group_columns[prefix]].values.ravel()]) # Flatten the data
        groups = np.array([prefix for prefix in args.groups for _ in range(len(df[group_columns[prefix]].values.ravel()))])
        tukey_results = pairwise_tukeyhsd(densities, groups, alpha=0.05)

        # Extract significant comparisons from Tukey's results
        test_results_df = pd.DataFrame(data=tukey_results.summary().data[1:], columns=tukey_results.summary().data[0])
        test_results_df.rename(columns={'p-adj': 'p-value'}, inplace=True)
        significant_comparisons = test_results_df[test_results_df['p-value'] < 0.05]

    # Loop for plotting comparison bars and asterisks
    for _, row in significant_comparisons.iterrows():
        group1, group2 = row['group1'], row['group2']
        x1 = np.where(groups == group1)[0][0]
        x2 = np.where(groups == group2)[0][0]

        # Plotting comparison lines
        plt.plot([x1, x1, x2, x2], [y_pos, y_pos + height_diff, y_pos + height_diff, y_pos], lw=1.5, c='black')
        
        # Plotting asterisks based on p-value
        if row['p-value'] < 0.0001:
            sig = '****'
        elif row['p-value'] < 0.001:
            sig = '***'
        elif row['p-value'] < 0.01:
            sig = '**'
        else:
            sig = '*'
        plt.text((x1 + x2) * .5, y_pos + 1 * height_diff, sig, horizontalalignment='center', size='xx-large', color='black', weight='bold')

        y_pos += 3 * height_diff  # Increment y_pos for the next comparison bar

    # Remove the legend only if it exists
    if ax.get_legend():
        ax.get_legend().remove()

    # Format the plot
    if args.ylabel == 'cell_density':
        ax.set_ylabel(r'Cells*10$^{4} $/mm$^{3}$', weight='bold')
    else:
        ax.set_ylabel(args.ylabel, weight='bold')
    ax.set_xticklabels(ax.get_xticklabels(), weight='bold')
    ax.tick_params(axis='both', which='major', width=2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_linewidth(2)
    ax.spines['left'].set_linewidth(2)
    plt.ylim(0, y_pos) # Adjust y-axis limit to accommodate comparison bars
    ax.set_xlabel('group') ### was None

    # Check if there are any significant comparisons (for prepending '_sig__' to the filename)
    has_significant_results = True if significant_comparisons.shape[0] > 0 else False

    # Extract the general region for the filename (output file name prefix for sorting by region)
    if args.csv_path == 'regional_summary.csv' or args.csv_path == 'regional_summary_CCFv3-2020.csv': 
        regional_summary = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / args.csv_path) #(Region_ID,ID_Path,Region,Abbr,General_Region,R,G,B)
    else:
        regional_summary = pd.read_csv(args.csv_path)
    region_id = region_id if region_id < 20000 else region_id - 20000 # Adjust if left hemi
    general_region = regional_summary.loc[regional_summary['Region_ID'] == region_id, 'General_Region'].values[0]

    # Format the filename with '_sig__' prefix if there are significant results
    prefix = '_sig__' if has_significant_results else ''
    filename = f"{prefix}{general_region}__{region_id}_{region_abbr}_{side}".replace("/", "-") # Replace problematic characters

    # Save the plot for each side or pooled data
    title = f"{region_name} ({region_abbr}, {side})"
    wrapped_title = textwrap.fill(title, 42)
    plt.title(wrapped_title, pad = 20).set_position([.5, 1.05])
    plt.tight_layout()
    plt.savefig(f"{out_dir}/{filename}.{args.extension}")
    plt.close()

    return test_results_df


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
    
    # Find all CSV files in the current directory matching *cell_densities.csv
    file_list = [file for file in os.listdir('.') if file.endswith('cell_densities.csv')]
    print(f"\nAggregating data from *cell_densities.csv: {file_list}\n")

    # Check if files are found
    if not file_list:
        print("    [red1]No files found matching the pattern '*cell_densities.csv'.")
        return

    # Aggregate the data for each sample
    aggregated_df = pd.read_csv(file_list[0]).iloc[:, 0:5]
    for file_name in file_list:
        df = pd.read_csv(file_name).iloc[:, -1:]
        # Rename the column prefix to match the --groups argument
        for prefix in args.groups:
            if prefix.lower() in df.columns[0].lower():
                old_prefix = df.columns[0].split("_")[0]
                new_column_name = df.columns[0].replace(old_prefix, prefix)
                df.rename(columns={df.columns[0]: new_column_name}, inplace=True)
                
                # Append the aggregated data to the dataframe
                aggregated_df = pd.concat([aggregated_df, df], axis=1)

    # Sort all columns that are not part of the first five by group prefix
    group_columns = sorted(aggregated_df.columns[5:], key=lambda x: args.groups.index(x.split('_')[0]))

    # Sort each group's columns numerically and combine them
    sorted_group_columns = []
    for prefix in args.groups:
        prefixed_group_columns = [col for col in group_columns if col.startswith(f"{prefix}_")]
        sorted_group_columns += sorted(prefixed_group_columns, key=lambda x: int(re.search(r'\d+', x).group()))

    # Combine the first five columns with the sorted group columns
    sorted_columns = aggregated_df.columns[:5].tolist() + sorted_group_columns

    # Now sorted_columns contains all columns, sorted by group and numerically within each group
    df = aggregated_df[sorted_columns]

    # Save the aggregated data as a CSV
    df.to_csv('regional_cell_densities_all.csv', index=False)

    # Normalization if needed
    if args.divide:
        df.iloc[:, 5:] = df.iloc[:, 5:].div(args.divide)

    # Prepare output directories
    if args.alternate == 'two-sided':
        suffix = ''
    else:
        suffix = f"_{args.alternate}" # Add suffix to indicate the alternative hypothesis

    # Make output directories
    if args.output:
        if args.hemi == 'both': 
            out_dirs = {side: f"{args.output}_{side}{suffix}" for side in ["L", "R", "pooled"]}
        elif args.hemi == 'r': 
            out_dirs = {side: f"{args.output}_{side}{suffix}" for side in ["R"]}
        elif args.hemi == 'l': 
            out_dirs = {side: f"{args.output}_{side}{suffix}" for side in ["L"]}
        else: 
            print("--hemi should be l, r, or both")
            import sys ; sys.exit()
    else:
        if args.hemi == 'both': 
            out_dirs = {side: f"{args.test_type}_plots_{side}{suffix}" for side in ["L", "R", "pooled"]}
        elif args.hemi == 'r': 
            out_dirs = {side: f"{args.test_type}_plots_{side}{suffix}" for side in ["R"]}
        elif args.hemi == 'l': 
            out_dirs = {side: f"{args.test_type}_plots_{side}{suffix}" for side in ["L"]}
        else: 
            print("--hemi should be l, r, or both")
            import sys ; sys.exit()

    for out_dir in out_dirs.values():
        os.makedirs(out_dir, exist_ok=True)
    
    group_columns = {}
    for prefix in args.groups:
        group_columns[prefix] = [col for col in df.columns if col.startswith(f"{prefix}_")] 

    if args.hemi == 'both': 
        # Averaging data across hemispheres and plotting pooled data (DR)
        print(f"\nPlotting and summarizing pooled data for each region...\n")
        rh_df = df[df['Region_ID'] < 20000]
        lh_df = df[df['Region_ID'] > 20000]

        # Initialize an empty dataframe to store all summaries
        all_summaries_pooled = pd.DataFrame() 

        # Drop first 4 columns
        rh_df = rh_df.iloc[:, 5:]
        lh_df = lh_df.iloc[:, 5:]

        # Reset indices to ensure alignment
        rh_df.reset_index(drop=True, inplace=True)
        lh_df.reset_index(drop=True, inplace=True)

        # Initialize pooled_df with common columns
        pooled_df = df[['Region_ID', 'Side', 'ID_Path', 'Region', 'Abbr']][df['Region_ID'] < 20000].reset_index(drop=True)
        pooled_df['Side'] = 'Pooled'  # Set the 'Side' to 'Pooled'

        # Average the cell densities for left and right hemispheres
        for col in lh_df.columns:
            pooled_df[col] = (lh_df[col] + rh_df[col]) / 2

        # Averaging data across hemispheres and plotting pooled data
        unique_region_ids = df[df["Side"] == "R"]["Region_ID"].unique()
        progress, task_id = initialize_progress_bar(len(unique_region_ids), "[red]Processing regions (pooled)...")
        with Live(progress):
            for region_id in unique_region_ids:
                region_name, region_abbr = get_region_details(region_id, df)
                out_dir = out_dirs["pooled"]
                comparisons_summary = process_and_plot_data(pooled_df[pooled_df["Region_ID"] == region_id], region_id, region_name, region_abbr, "Pooled", out_dir, group_columns, args)
                summary_df = summarize_significance(comparisons_summary, region_id)
                all_summaries_pooled = pd.concat([all_summaries_pooled, summary_df], ignore_index=True)
                progress.update(task_id, advance=1)

        # Merge with the original regional_summary.csv and write to a new CSV
        if args.csv_path == 'regional_summary.csv' or args.csv_path == 'regional_summary_CCFv3-2020.csv': 
            regional_summary = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / args.csv_path) #(Region_ID,ID_Path,Region,Abbr,General_Region,R,G,B)
        else:
            regional_summary = pd.read_csv(args.csv_path)
        final_summary_pooled = pd.merge(regional_summary, all_summaries_pooled, on='Region_ID', how='left') 
        final_summary_pooled.to_csv(Path(out_dir) / '__significance_summary_pooled.csv', index=False)

    # Perform analysis and plotting for each hemisphere
    if args.hemi == 'r':
        sides_to_process = ["R"]
    elif args.hemi == 'l': 
        sides_to_process = ["L"]
    else:
        sides_to_process = ["L", "R"]

    for side in sides_to_process:
        print(f"\nPlotting and summarizing data for {side} hemisphere...\n")

        # Initialize an empty dataframe to store all summaries
        all_summaries = pd.DataFrame()
        side_df = df[df['Side'] == side]
        unique_region_ids = side_df["Region_ID"].unique() # Get unique region IDs for the current side
        progress, task_id = initialize_progress_bar(len(unique_region_ids), f"[red]Processing regions ({side})...")
        with Live(progress):
            for region_id in unique_region_ids:
                region_name, region_abbr = get_region_details(region_id, side_df)
                out_dir = out_dirs[side]
                comparisons_summary = process_and_plot_data(side_df[side_df["Region_ID"] == region_id], region_id, region_name, region_abbr, side, out_dir, group_columns, args)
                summary_df = summarize_significance(comparisons_summary, region_id)
                all_summaries = pd.concat([all_summaries, summary_df], ignore_index=True)
                progress.update(task_id, advance=1)

        # Merge with the original regional_summary.csv and write to a new CSV
        if args.csv_path == 'regional_summary.csv' or args.csv_path == 'regional_summary_CCFv3-2020.csv': 
            regional_summary = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / args.csv_path) #(Region_ID,ID_Path,Region,Abbr,General_Region,R,G,B)
        else:
            regional_summary = pd.read_csv(args.csv_path)

        # Adjust Region_ID for left hemisphere
        if side == "L":
            all_summaries["Region_ID"] = all_summaries["Region_ID"] - 20000

        final_summary = pd.merge(regional_summary, all_summaries, on='Region_ID', how='left') 
        final_summary.to_csv(Path(out_dir) / f'__significance_summary_{side}.csv', index=False)

    verbose_end_msg()


if __name__ == '__main__':
    main()
