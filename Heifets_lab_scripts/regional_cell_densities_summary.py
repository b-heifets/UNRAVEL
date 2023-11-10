#!/usr/bin/env python3

import argparse
import os
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import textwrap
from scipy.stats import dunnett

def parse_args():
    parser = argparse.ArgumentParser(description='Plot cell densensities for a given region intensity ID for 3+ groups.\n CSV columns: Region_ID,Side,Name,Abbr,saline_sample06,saline_sample07,...,mdma_sample01,...,meth_sample23,..')
    parser.add_argument('-i', '--input', help='CSV file with cell densities for each group', metavar='')
    parser.add_argument('--groups', nargs='*', help='Group prefixes (e.g., saline meth cbsMeth)', metavar='')
    parser.add_argument('-c', '--ctrl_group', help="Control group name for Dunnett's tests", metavar='')
    parser.add_argument('-d', '--divide', type=float, help='Divide the cell densities by the specified value for plotting (default is None)', default=None, metavar='')
    parser.add_argument('-a', "--alt", help="Number of tails and direction for Dunnett's test {'two-sided', 'less' (means < ctrl)}", default='two-sided', metavar='')
    parser.add_argument('-y', '--ylabel', help='Y-axis label (Default: cell_density)', default='cell_density', metavar='')
    parser.add_argument('-o', '--output', help='Output directory for plots (Default: dunnetts_plots)', default='dunnetts_plots', metavar='')
    parser.epilog = "regional_cell_densities_summary.py -i cell_densities.csv --groups saline mdma meth -c saline ; update colors in script if needed"
    return parser.parse_args()

# Set Arial as the font
mpl.rcParams['font.family'] = 'Arial'

def get_region_details(region_id, df):
    # Adjust to account for the unique region IDs.
    region_row = df[(df["Region_ID"] == region_id) | (df["Region_ID"] == region_id + 20000)].iloc[0]
    return region_row["Name"], region_row["Abbr"]


def process_and_plot_data(df, region_id, region_name, region_abbr, side, out_dir, group_prefixes, control_group, group_columns, group_colors, alt, ylabel):
    # Prepare data for Dunnett's test
    control_data = df[group_columns[control_group]].values.ravel()
    data = [df[group_columns[prefix]].values.ravel() for prefix in group_prefixes if prefix != control_group]

    # The * operator unpacks the list so that each array is a separate argument, as required by dunnett
    dunnett_results = dunnett(*data, control=control_data, alternative=alt)

    # Convert the result to a DataFrame
    test_df = pd.DataFrame({
        'group1': [control_group] * len(dunnett_results.pvalue),
        'group2': [prefix for prefix in group_prefixes if prefix != control_group],
        'p-adj': dunnett_results.pvalue
    })
    test_df['reject'] = test_df['p-adj'] < 0.05
    significant_comparisons = test_df[test_df['reject'] == True]

    # Reshaping the data for plotting
    reshaped_data = []
    for prefix in group_prefixes:
        for value in df[group_columns[prefix]].values.ravel():
            reshaped_data.append({'group': prefix, 'density': value})

    reshaped_df = pd.DataFrame(reshaped_data)

    # Plot the data
    plt.figure(figsize=(4, 4))
    
    # Bar plot
    ax = sns.barplot(x='group', y='density', data=reshaped_df, color='white', errorbar=('se'), capsize=0.1, linewidth=2, edgecolor='black')
    
    # Swarm plot
    sns.swarmplot(x='group', y='density', hue='group', data=reshaped_df, palette=group_colors, size=8, linewidth=1, edgecolor='black', legend=False)

    ax = sns.swarmplot(x='group', y='density', hue='group', data=reshaped_df, palette=group_colors, size=8, linewidth=1, edgecolor='black')
    ax.get_legend().remove()

    # Formatting as in the plot_data() function
    if ylabel == 'cell_density':
        ax.set_ylabel(r'Cells*10$^{4} $/mm$^{3}$', weight='bold')
    else:
        ax.set_ylabel(ylabel, weight='bold')
    ax.set_xticklabels(ax.get_xticklabels(), weight='bold')
    ax.tick_params(axis='both', which='major', width=2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_linewidth(2)
    ax.spines['left'].set_linewidth(2)

    # Add comparison bars and asterisks similar to plot_data()
    y_max = reshaped_df['density'].max()
    y_min = reshaped_df['density'].min()
    height_diff = (y_max - y_min) * 0.1
    y_pos = y_max + 1 * height_diff

    groups = reshaped_df['group'].unique()

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
            
        plt.text((x1 + x2) * .5, y_pos + 1 * height_diff, sig, horizontalalignment='center', size='xx-large', color='black', weight='bold')
        y_pos += 3 * height_diff

    plt.ylim(0, y_pos + 2 * height_diff)
    ax.set_xlabel(None)

    # Save the plot for each side or pooled data
    title = f"{region_name} ({region_abbr}, {side})"
    wrapped_title = textwrap.fill(title, 42)
    plt.title(wrapped_title)
    plt.tight_layout()
    filename = f"{region_id}_{region_abbr}_{side}".replace("/", "-")  # Replace problematic characters
    plt.savefig(f"{out_dir}/{filename}.pdf")
    plt.close()


def main():
    args = parse_args()

    df = pd.read_csv(args.input)

    # Normalization if needed
    if args.divide:
        df.iloc[:, 4:] = df.iloc[:, 4:].div(args.divide)

    # Prepare output directories
    out_dirs = {side: f"{args.output}_{side}H" for side in ["L", "R", "pooled"]}
    for out_dir in out_dirs.values():
        os.makedirs(out_dir, exist_ok=True)

    group_columns = {}
    for prefix in args.groups:
        group_columns[prefix] = [col for col in df.columns if col.startswith(f"{prefix}_")] 

    group_colors = {
        args.groups[0]: '#2D67C8',  # blue
        args.groups[1]: '#27AF2E',  # green
        args.groups[2]: '#D32525',  # red
        args.groups[3]: '#7F25D3',  # purple
    }

    # Perform analysis and plotting for each hemisphere
    for side in ["L", "R"]:
        side_df = df[df['Side'] == side]
        unique_region_ids = side_df["Region_ID"].unique()
        for region_id in unique_region_ids:
            region_name, region_abbr = get_region_details(region_id, side_df)
            out_dir = out_dirs[side]
            process_and_plot_data(side_df[side_df["Region_ID"] == region_id], region_id, region_name, region_abbr, side, out_dir, args.groups, args.ctrl_group, group_columns, group_colors, args.alt, args.ylabel)
    
    # Averaging data across hemispheres and plotting pooled data
    unique_region_ids = df[df["Side"] == "R"]["Region_ID"].unique()
    for region_id in unique_region_ids:
        lh_region_id = region_id + 20000
        rh_region_id = region_id

        # Filter dataframes for the specific region ID
        lh_df = df[df["Region_ID"] == lh_region_id]
        rh_df = df[df["Region_ID"] == rh_region_id]

        # Ensure there is a corresponding region in the other hemisphere before averaging
        if not lh_df.empty and not rh_df.empty:
            # Initialize the pooled dataframe with non-sample columns
            pooled_df = lh_df[['Region_ID', 'Side', 'Name', 'Abbr']].copy()
            pooled_df['Side'] = 'Pooled'  # Set the 'Side' to 'Pooled'

            # Compute the average for each sample column
            for group in args.groups:
                for col in group_columns[group]:
                    pooled_df[col] = (lh_df[col].values + rh_df[col].values) / 2

            region_name, region_abbr = get_region_details(rh_region_id, df)
            out_dir = out_dirs["pooled"]
            # Call the function with the pooled dataframe
            process_and_plot_data(pooled_df, rh_region_id, region_name, region_abbr, "Pooled", out_dir, args.groups, args.ctrl_group, group_columns, group_colors, args.alt, args.ylabel)


if __name__ == "__main__":
    main()