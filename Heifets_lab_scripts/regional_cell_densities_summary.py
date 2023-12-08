#!/usr/bin/env python3

import argparse
import ast
import os
from pathlib import Path
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import textwrap
from argparse import RawTextHelpFormatter
from rich import print
from scipy.stats import dunnett
from statsmodels.stats.multicomp import pairwise_tukeyhsd

def parse_args():
    parser = argparse.ArgumentParser(description='Plot cell densensities for a given region intensity ID for 3+ groups.\n CSV columns: Region_ID,Side,Name,Abbr,Saline_sample06,Saline_sample07,...,MDMA_sample01,...,Meth_sample23,...', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-i', '--input', help='CSV file with cell densities for each group', metavar='')
    parser.add_argument('--groups', nargs='*', help='Group prefixes (e.g., saline meth cbsMeth)', metavar='')
    parser.add_argument('-t', '--test_type', help="Type of statistical test to use: 'tukey' or 'dunnett' (default: 'dunnett')", choices=['tukey', 'dunnett'], default='dunnett', metavar='')
    parser.add_argument('-c', '--ctrl_group', help="Control group name for Dunnett's tests", metavar='')
    parser.add_argument('-d', '--divide', type=float, help='Divide the cell densities by the specified value for plotting (default is None)', default=None, metavar='')
    parser.add_argument('-y', '--ylabel', help='Y-axis label (Default: cell_density)', default='cell_density', metavar='')
    parser.add_argument('-b', '--bar_color', help="ABA (default), #hex_code, Seaborn palette, or #hex_code list matching # of groups", default='ABA', metavar='')
    parser.add_argument('-s', '--symbol_color', help="ABA, #hex_code, Seaborn palette (Default: light:white), or #hex_code list matching # of groups", default='light:white', metavar='')
    parser.add_argument('-o', '--output', help='Output directory for plots (Default: <args.test_type>_plots)', metavar='')
    parser.add_argument('-a', "--alt", help="Number of tails and direction for Dunnett's test {'two-sided', 'less' (means < ctrl)}", default='two-sided', metavar='')
    parser.epilog = """regional_cell_densities_summary.py -i cell_densities.csv --groups Saline MDMA Meth -c Saline -d 10000 -s symbols --test_type tukey
    
    Example hex code list (pass arg w/ quotes): ['#2D67C8', '#27AF2E', '#D32525', '#7F25D3']"""
    return parser.parse_args()

# TODO: Organize PDF names based on general region and note if has sig diff (e.g., <>__Subregion__Abbr__ID.pdf). Summarize results in new output csv file. Add t-test test_type. Dunnett greater. One-tailed option for other test_type options. 


def get_region_details(region_id, df):
    # Adjust to account for the unique region IDs.
    region_row = df[(df["Region_ID"] == region_id) | (df["Region_ID"] == region_id + 20000)].iloc[0]
    return region_row["Name"], region_row["Abbr"]

def parse_color_argument(color_arg, num_groups, region_id):
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
            results_df = pd.read_csv(Path(__file__).parent / 'regional_summary.csv') #(Region_ID,ID_Path,Region,Abbr,General_Region,R,G,B)
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
    
def summarize_significance(test_df, region_id, df, group_columns):
    summary_rows = []
    for _, row in test_df.iterrows():
        group1, group2 = row['group1'], row['group2']
        # Determine significance level
        sig = ''
        if row['p-adj'] < 0.0001:
            sig = '****'
        elif row['p-adj'] < 0.001:
            sig = '***'
        elif row['p-adj'] < 0.01:
            sig = '**'
        elif row['p-adj'] < 0.05:
            sig = '*'
        # Determine which group has a higher mean
        meandiff = row['meandiff']
        higher_group = group2 if meandiff > 0 else group1
        summary_rows.append({
            'Region_ID': region_id,
            'Comparison': f'{group1} vs {group2}',
            'p-value': row['p-adj'],
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
    bar_color = parse_color_argument(args.bar_color, num_groups, region_id)
    symbol_color = parse_color_argument(args.symbol_color, num_groups, region_id)

    # Coloring the bars and symbols
    ax = sns.barplot(x='group', y='density', data=reshaped_df, errorbar=('se'), capsize=0.1, palette=bar_color, linewidth=2, edgecolor='black')
    sns.stripplot(x='group', y='density', hue='group', data=reshaped_df, palette=symbol_color, alpha=0.5, size=8, linewidth=0.75, edgecolor='black')

    # Calculate y_max and y_min based on the actual plot
    y_max = ax.get_ylim()[1]
    y_min = ax.get_ylim()[0]
    height_diff = (y_max - y_min) * 0.05  # Adjust the height difference as needed
    y_pos = y_max * 1.05  # Start just above the highest bar

    # Check which test to perform
    if args.test_type == 'dunnett':

        # Extract the data for the control group and the other groups
        data = [df[group_columns[prefix]].values.ravel() for prefix in args.groups if prefix != args.ctrl_group]
        control_data = df[group_columns[args.ctrl_group]].values.ravel()

        # The * operator unpacks the list so that each array is a separate argument, as required by dunnett
        dunnett_results = dunnett(*data, control=control_data, alternative=args.alt)

        # Convert the result to a DataFrame
        test_results_df = pd.DataFrame({
            'group1': [args.ctrl_group] * len(dunnett_results.pvalue),
            'group2': [prefix for prefix in args.groups if prefix != args.ctrl_group],
            'p-adj': dunnett_results.pvalue,
        })
        significant_comparisons = test_results_df[test_results_df['p-adj'] < 0.05]

    elif args.test_type == 'tukey':

        # Conduct Tukey's HSD test
        cell_densities = np.array([value for prefix in args.groups for value in df[group_columns[prefix]].values.ravel()]) # Flatten the data
        labels = np.array([prefix for prefix in args.groups for _ in range(len(df[group_columns[prefix]].values.ravel()))])
        tukey_results = pairwise_tukeyhsd(cell_densities, labels, alpha=0.05)

        # Extract significant comparisons from Tukey's results
        test_results_df = pd.DataFrame(data=tukey_results.summary().data[1:], columns=tukey_results.summary().data[0])
        significant_comparisons = test_results_df[test_results_df['p-adj'] < 0.05]

    # Loop for plotting comparison bars and asterisks
    for _, row in significant_comparisons.iterrows():
        group1, group2 = row['group1'], row['group2']
        x1 = np.where(groups == group1)[0][0]
        x2 = np.where(groups == group2)[0][0]

        # Plotting comparison lines
        plt.plot([x1, x1, x2, x2], [y_pos, y_pos + height_diff, y_pos + height_diff, y_pos], lw=1.5, c='black')
        
        # Plotting asterisks based on p-value
        if row['p-adj'] < 0.0001:
            sig = '****'
        elif row['p-adj'] < 0.001:
            sig = '***'
        elif row['p-adj'] < 0.01:
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
    ax.set_xlabel(None)

    # Check if the 'Significance' column exists in significant_comparisons (for prepending '_sig__' to the filename)
    has_significant_results = False
    if 'reject' in significant_comparisons.columns:
        has_significant_results = significant_comparisons['reject'].any()

    # Extract the general region for the filename (output file name prefix for sorting by region)
    regional_summary = pd.read_csv(Path(__file__).parent / 'regional_summary.csv') #(Region_ID,ID_Path,Region,Abbr,General_Region,R,G,B)
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
    plt.savefig(f"{out_dir}/{filename}.pdf")
    plt.close()

    return test_results_df


def main():
    args = parse_args()

    df = pd.read_csv(args.input)

    # Normalization if needed
    if args.divide:
        df.iloc[:, 4:] = df.iloc[:, 4:].div(args.divide)

    # Prepare output directories
    if args.output:
        out_dirs = {side: f"{args.output}_{side}" for side in ["L", "R", "pooled"]}
    else:
        out_dirs = {side: f"{args.test_type}_plots_{side}" for side in ["L", "R", "pooled"]}
    for out_dir in out_dirs.values():
        os.makedirs(out_dir, exist_ok=True)

    group_columns = {}
    for prefix in args.groups:
        group_columns[prefix] = [col for col in df.columns if col.startswith(f"{prefix}_")] 

    all_summaries = pd.DataFrame()

    # Averaging data across hemispheres and plotting pooled data (DR)
    rh_df = df[df['Region_ID'] < 20000]
    lh_df = df[df['Region_ID'] > 20000]

    # Drop first 4 columns
    rh_df = rh_df.iloc[:, 4:]
    lh_df = lh_df.iloc[:, 4:]

    # Reset indices to ensure alignment
    rh_df.reset_index(drop=True, inplace=True)
    lh_df.reset_index(drop=True, inplace=True)

    # Initialize pooled_df with common columns
    pooled_df = df[['Region_ID', 'Side', 'Name', 'Abbr']][df['Region_ID'] < 20000].reset_index(drop=True)
    pooled_df['Side'] = 'Pooled'  # Set the 'Side' to 'Pooled'

    # Average the cell densities for left and right hemispheres
    for col in lh_df.columns:
        pooled_df[col] = (lh_df[col] + rh_df[col]) / 2

    # Averaging data across hemispheres and plotting pooled data
    unique_region_ids = df[df["Side"] == "R"]["Region_ID"].unique()
    for region_id in unique_region_ids:
        region_name, region_abbr = get_region_details(region_id, df)
        out_dir = out_dirs["pooled"]
        significant_comparisons = process_and_plot_data(pooled_df[pooled_df["Region_ID"] == region_id], region_id, region_name, region_abbr, "Pooled", out_dir, group_columns, args)
        summary_df = summarize_significance(significant_comparisons, region_id, pooled_df, group_columns)
        all_summaries = pd.concat([all_summaries, summary_df], ignore_index=True)

    # Merge with the original regional_summary.csv and write to a new CSV
    regional_summary = pd.read_csv(Path(__file__).parent / 'regional_summary.csv')
    final_summary = pd.merge(regional_summary, all_summaries, on='Region_ID', how='left')
    final_summary.to_csv(Path(out_dir) / '__significance_summary.csv', index=False)

    # Perform analysis and plotting for each hemisphere
    for side in ["L", "R"]:
        side_df = df[df['Side'] == side]
        unique_region_ids = side_df["Region_ID"].unique()
        for region_id in unique_region_ids:        
            region_name, region_abbr = get_region_details(region_id, side_df)
            out_dir = out_dirs[side]
            significant_comparisons = process_and_plot_data(side_df[side_df["Region_ID"] == region_id], region_id, region_name, region_abbr, side, out_dir, group_columns, args)
            summary_df = summarize_significance(significant_comparisons, region_id, side_df, group_columns)
            all_summaries = pd.concat([all_summaries, summary_df], ignore_index=True)

        # Merge with the original regional_summary.csv and write to a new CSV
        regional_summary = pd.read_csv(Path(__file__).parent / 'regional_summary.csv')
        final_summary = pd.merge(regional_summary, all_summaries, on='Region_ID', how='left')
        final_summary.to_csv(Path(out_dir) / '__significance_summary.csv', index=False)


if __name__ == "__main__":
    main()