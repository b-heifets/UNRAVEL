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
    parser = argparse.ArgumentParser(description='Plot cell densensities for a given region intensity ID for 3+ groups.\n CSV columns: region_ID,region_name,region_abbr,saline_sample06,saline_sample07,saline_sample08,meth_sample01,meth_sample03,meth_sample12,cbsMeth_sample23,cbsMeth_sample24,cbsMeth_sample25')
    parser.add_argument('-i', '--input', help='CSV file with cell densities for each group', metavar='')
    parser.add_argument('--groups', nargs='*', help='Group prefixes (e.g., saline meth cbsMeth)', metavar='')
    parser.add_argument('-c', '--ctrl_group', help="Control group name for Dunnett's tests", metavar='')
    parser.add_argument('-d', '--divide', type=float, help='Divide the cell densities by the specified value for plotting (default is None)', default=None, metavar='')
    parser.add_argument('-a', "--alt", help="Number of tails and direction for Dunnett's test {'two-sided', 'less' (means < ctrl)}", default='two-sided', metavar='')
    parser.add_argument('-y', '--ylabel', help='Y-axis label (Default: cell_density)', default='cell_density', metavar='')
    parser.add_argument('-o', '--output', help='Output directory for plots (Default: dunnetts_plots)', default='dunnetts_plots', metavar='')
    parser.epilog = "regional_densities_summary.py -i cell_densities.csv --groups saline meth cbsMeth -c saline"
    return parser.parse_args()

# Set Arial as the font
mpl.rcParams['font.family'] = 'Arial'

def get_region_details(region_id, df):
    region_row = df[df["region_ID"] == region_id].iloc[0]
    return region_row["region_name"], region_row["region_abbr"]

def dunnetts_test(csv, group_prefixes, control_group, denominator, alt, out_dir, ylabel):

    df = pd.read_csv(csv)

    # Divide the cell densities by the normalization factor
    if denominator != None:
        for col in df.columns:
            if "sample" in col:
                df[col] = df[col] / denominator

    group_columns = {prefix: [col for col in df.columns if prefix in col] for prefix in group_prefixes}

    region_ids = df["region_ID"].unique()

    # Make output directory for plots
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    # Map group names to colors
    group_colors = {
        group_prefixes[0]: '#2D67C8',  # blue
        group_prefixes[1]: '#D32525',  # red
        group_prefixes[2]: '#27AF2E',  # green
    }

    for region_id in region_ids:
        region_name, region_abbr = get_region_details(region_id, df)
        print(f"Processing Region ID: {region_id}, {region_name} ({region_abbr})")

        # Perform Dunnett's test (https://docs.scipy.org/doc/scipy-1.11.3/reference/generated/scipy.stats.dunnett.html#scipy.stats.dunnett)
        control_data = df[df["region_ID"] == region_id][group_columns[control_group]].values.ravel()
        data = [df[df["region_ID"] == region_id][group_columns[prefix]].values.ravel() for prefix in group_prefixes if prefix != control_group]
        dunnett_results = dunnett(*data, control=control_data, alternative=alt) 
        
        # Convert the result to a DataFrame similar to the Tukey output for easier handling
        test_df = pd.DataFrame({
            'group1': [control_group] * len(dunnett_results.pvalue),
            'group2': group_prefixes[1:],
            'p-adj': dunnett_results.pvalue
        })
        test_df['reject'] = test_df['p-adj'] < 0.05
        significant_comparisons = test_df[test_df['reject'] == True]

        # Reshaping the data for plotting
        reshaped_data = []
        for group, values in group_columns.items():
            for value in df[df["region_ID"] == region_id][values].values.ravel():
                reshaped_data.append({'group': group, 'density': value})

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

        # Save the plot
        title = f"{region_name} ({region_abbr})"
        wrapped_title = textwrap.fill(title, 42)  # wraps at x characters. Adjust as needed.
        plt.title(wrapped_title)
        plt.tight_layout()
        region_abbr = region_abbr.replace("/", "-") # Replace problematic characters for file paths
        plt.savefig(f"{out_dir}/{region_id}_{region_abbr}.pdf")
        plt.close()

def main():
    args = parse_args()

    df = dunnetts_test(args.input, args.groups, args.ctrl_group, args.divide, args.alt, args.output, args.ylabel)

if __name__ == "__main__":
    main()