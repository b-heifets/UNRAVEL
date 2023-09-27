#!/usr/bin/env python3

import argparse
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import seaborn as sns
import textwrap
from scipy.stats import dunnett
from statsmodels.stats.multicomp import pairwise_tukeyhsd

region_ID_name_abbr_csv = "/Users/Danielthy/Documents/_Heifets_lab_data/_Lightsheet_microscopy_data/#Gubra/gubra_region_ID_name_abbr.csv"

def parse_args():
    parser = argparse.ArgumentParser(description='Plot mean IF intensity for a given region intensity ID for 3+ groups (only works for positive data)')

    parser.add_argument('--region_ids', nargs='*', type=int, help='List of region intensity IDs (Default: process all regions from the lut CSV)', metavar='')
    parser.add_argument('--order', nargs='*', help='Group Order for plotting (must match 1st word of CSVs)', metavar='')
    parser.add_argument('--labels', nargs='*', help='Group Labels in same order', metavar='')
    parser.add_argument('-l', '--lut', help="path to CSV with 'region_ID', 'region_name', 'region_abbr", default=region_ID_name_abbr_csv, metavar='')
    parser.add_argument('-t', '--test', help='Choose between "tukey" and "dunnett" post-hoc tests. (Default: tukey)', default='tukey', choices=['tukey', 'dunnett'], metavar='')
    parser.add_argument('-s', '--show_plot', help='Show plot', action='store_true')

    parser.epilog = "regional_IF_mean_intensities_summary.py -r 1 --order group3 group2 group1 --labels Group_3 Group_2 Group_1"
    return parser.parse_args()

# Set Arial as the font
mpl.rcParams['font.family'] = 'Arial'

def load_data(region_id):
    data = []
    
    # Load all CSVs in the directory
    for filename in os.listdir():
        if filename.endswith('.csv'):
            group_name = filename.split("_")[0]
            df = pd.read_csv(filename)
            
            # Filter by the region ID
            mean_intensity = df[df["Region_Intensity"] == region_id]["Mean_IF_Intensity"].values
            if len(mean_intensity) > 0:
                data.append({
                    'group': group_name,
                    'mean_intensity': mean_intensity[0]
                })
    
    return pd.DataFrame(data)

def get_region_details(region_id, csv_path):
    region_df = pd.read_csv(csv_path)
    region_row = region_df[region_df["region_ID"] == region_id].iloc[0]
    return region_row["region_name"], region_row["region_abbr"]

def get_all_region_ids(csv_path):
    """Retrieve all region IDs from the provided CSV."""
    region_df = pd.read_csv(csv_path)
    return region_df["region_ID"].tolist()

def plot_data(region_id, order=None, labels=None, csv_path=region_ID_name_abbr_csv, test_type='tukey', show_plot=False):
    df = load_data(region_id)
    region_name, region_abbr = get_region_details(region_id, csv_path)
    
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
    ax.set_xticklabels(ax.get_xticklabels(), weight='bold')
    ax.tick_params(axis='both', which='major', width=2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_linewidth(2)
    ax.spines['left'].set_linewidth(2)

    # Swarm plot
    sns.swarmplot(x='group_label', y='mean_intensity', hue='group', data=df, palette=group_colors, size=8, linewidth=1, edgecolor='black')
    
    # Remove the legend created by hue
    ax.legend_.remove()

    # Perform the chosen post-hoc test
    if test_type == 'tukey':
        test_results = pairwise_tukeyhsd(df['mean_intensity'], df['group']).summary()
        test_df = pd.DataFrame(test_results.data[1:], columns=test_results.data[0])
    elif test_type == 'dunnett':
        # Assuming control is the first group in the order (change as needed)
        control_data = df[df['group'] == order[0]]['mean_intensity'].values
        experimental_data = [df[df['group'] == group]['mean_intensity'].values for group in order[1:]]
        test_stats = dunnett(*experimental_data, control=control_data)
        # Convert the result to a DataFrame similar to the Tukey output for easier handling
        test_df = pd.DataFrame({
            'group1': [order[0]] * len(test_stats.pvalue),
            'group2': order[1:],
            'p-adj': test_stats.pvalue
        })
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

    plt.ylim(0, y_pos + 2*height_diff)
    ax.set_xlabel(None)

    # Save the plot
    title = f"{region_name} ({region_abbr})"
    wrapped_title = textwrap.fill(title, 42)  # wraps at x characters. Adjust as needed.
    plt.title(wrapped_title)
    plt.tight_layout()
    region_abbr = region_abbr.replace("/", "-") # Replace problematic characters for file paths
    plt.savefig(f'region_{region_id}_{region_abbr}.pdf')
    plt.close()

    if args.show_plot:
        plt.show()

if __name__ == "__main__":
    args = parse_args()

    if (args.order and not args.labels) or (not args.order and args.labels):
        raise ValueError("Both --order and --labels must be provided together.")

    if args.order and args.labels and len(args.order) != len(args.labels):
        raise ValueError("The number of entries in --order and --labels must match.")

    # If region IDs are provided using -r, use them; otherwise, get all region IDs from the CSV
    region_ids_to_process = args.region_ids if args.region_ids else get_all_region_ids(args.lut)

    # Process each region ID
    for region_id in region_ids_to_process:
        plot_data(region_id, args.order, args.labels, csv_path=args.lut, test_type=args.test, show_plot=args.show_plot)
