#!/usr/bin/env python3

import argparse
import matplotlib as mpl    
import matplotlib.pyplot as plt
import os
import pandas as pd
import seaborn as sns
import warnings
from matplotlib.ticker import MaxNLocator
from scipy.stats import ttest_ind

from unravel.core.argparse_utils import SuppressMetavar, SM


warnings.simplefilter(action='ignore', category=FutureWarning)

# Set Arial as the font
mpl.rcParams['font.family'] = 'Arial'

def parse_args():
    parser = argparse.ArgumentParser(description='Load CSV w/ cluster densities and conduct t-tests', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input_csv', help='Path to CSV with cluster densities', required=True, action=SM)
    parser.add_argument('-ord', '--order', help='Group Order for plotting (must match condition in CSV)', required=True, nargs=2, action=SM)
    parser.add_argument('-l', '--labels', help='Group Labels in same order', nargs=2, default=None, action=SM)
    parser.add_argument('-c', '--colors', help="Colors (<color> or <hexcode>) for the bars in the same order as groups (Default: #dadada #ddeeff)", nargs=2, default=['#dadada', '#ddeeff'], action=SM)
    parser.add_argument('--symbol_color', help='Color (<color> or <hexcode>) for the symbols in swarmplot (Default: #bababa #abface)', nargs=2, default=['#bababa', '#abcdef'], action=SM)
    parser.add_argument('-ort', '--orient', help='Orientation of bar graphs (h: horizontal, v: vertical; Default: h)', choices=['h', 'v'], default='h',  action=SM)
    parser.add_argument('--output_type', choices=['pdf', 'png', 'svg'], default='pdf', help='Output file type (pdf, png, or svg)', action=SM)
    return parser.parse_args()

def get_significance(p_val):
    if p_val > 0.05:
        return "n.s."
    elif p_val < 0.05:
        return "*"
    elif p_val < 0.01:
        return "**"
    elif p_val < 0.001:
        return "***"
    else:
        return "****"
    
def graph_formatting(ax, orientation='h'):

    # Explicitly set the tick locations
    ax.set_xticks(ax.get_xticks())
    ax.set_xticklabels(ax.get_xticklabels(), weight='bold')
    ax.tick_params(axis='both', which='major', width=2)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_linewidth(2)
    ax.spines['left'].set_linewidth(2)

    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

def save_legend_to_file(labels, colors, filename="legend.png"):
    # Create dummy patches to use for creating the legend
    patches = [plt.Line2D([0], [0], color=color, lw=4, label=label) for label, color in zip(labels, colors)]
    
    # Create the legend and save it
    fig, ax = plt.subplots(figsize=(3, 2))  # Adjust as needed
    ax.legend(handles=patches, loc='center')
    ax.axis('off')
    plt.tight_layout()
    fig.savefig(filename, bbox_inches='tight')
    plt.close()

def get_position_for_significance_bar(data, cluster, order, offset=0.1, orientation='v'):
    group1_max = data[data['Conditions'] == order[0]][cluster].max()
    group2_max = data[data['Conditions'] == order[1]][cluster].max()
    if orientation == 'v':
        return max(group1_max, group2_max) + offset
    else:
        return max(group1_max, group2_max) + offset

def add_significance_marker(ax, start, stop, position, significance, orientation='v', vertical_offset=0.0):
    if orientation == 'v':
        ax.plot([start, start, stop, stop], [position, position + 0.05, position + 0.05, position], color='black')
        ax.text((start + stop) * 0.5, position + vertical_offset, significance, ha='center', va='bottom', color='black', weight='bold', size='xx-large')
    else:
        ax.plot([position, position + 0.15, position + 0.15, position], [start, start, stop, stop], color='black') 
        ax.text(position + 0.23, (start + stop) * 0.5 + vertical_offset, significance, ha='left', va='center', color='black', weight='bold', size='xx-large')

def cluster_density_t_tests(df, order, labels=None, colors=['#dadada', '#ddeeff'], orientation='h', symbol_color=['#bababa', '#abcdef'], output_type='pdf', global_max=None):
    clusters = df.columns[2:]
    results = {"Cluster": [], "P-value": [], "Significance": []}
    
    for cluster in clusters:
        df[cluster] = df[cluster] / 10000 # Convert to per 10,000 cells
        group1 = df[df['Conditions'] == order[0]][cluster]
        group2 = df[df['Conditions'] == order[1]][cluster]
        _, p_val = ttest_ind(group1, group2, equal_var=False)
        results["Cluster"].append(cluster)
        results["P-value"].append(p_val)
        results["Significance"].append(get_significance(p_val))
    
    results_df = pd.DataFrame(results)
    results_df.to_csv(f"{prefix}_t_test_results.csv", index=False)
    print(f"\n  Results saved to {prefix}_t_test_results.csv\n")
    
    significant_clusters = results_df[results_df["P-value"] < 0.05]["Cluster"].tolist()

    plot_clusters(df, clusters, order, labels, colors, orientation, symbol_color, output_type, global_max)
    plot_all_clusters(df, clusters, order, labels, colors, orientation, symbol_color, output_type, global_max, results_df)
    plot_significant_clusters(df, significant_clusters, order, labels, colors, orientation, symbol_color, output_type, global_max, results_df)

def plot_clusters(df, clusters, order, labels=None, colors=['#dadada', '#ddeeff'], orientation='h', symbol_color=['#bababa', '#abcdef'], output_type='pdf', global_max=None):
    for cluster in clusters:
        if global_max is None:
            global_max = df[cluster].max()

        if orientation == 'v':
            y, x, orient = cluster, 'Conditions', 'v'
            plt.figure(figsize=(2, 4))
            plt.ylim(0, global_max)
        else:
            y, x, orient = 'Conditions', cluster, 'h'
            plt.figure(figsize=(4, 2))
            plt.xlim(0, global_max)
            
        ax = sns.barplot(data=df, y=y, x=x, order=order, palette=colors, errorbar='se', edgecolor='black', linewidth=2, orient=orient, capsize=0.2)
        graph_formatting(ax)
        sns.swarmplot(data=df, y=y, x=x, hue='Conditions', order=order, hue_order=order, palette=symbol_color, size=7, linewidth=1, edgecolor='black', orient=orient, legend=False)
     
        # Add abbreviated region name to the plot
        # plt.title(cluster)

        if orientation == 'v':
            plt.ylabel(r'Cells*10$^{4} $/mm$^{3}$', weight='bold')
            plt.xlabel('')
            asterisk_offset = -0.05 # Offset in y 
            bar_offset = 0.15 # Offset from largest data point
        else: 
            plt.xlabel(r'Cells*10$^{4} $/mm$^{3}$', weight='bold')
            plt.ylabel('')
            asterisk_offset = -0.1 # Offset in y 
            bar_offset = 0.2 
            ax.set_ylim(-0.5, len(order) - 0.5) 

        # plt.ylabel('Conditions' if labels is None else '')
        
        if labels and orientation == 'h':
            plt.yticks(ticks=range(len(order)), labels=labels)

        for label in ax.get_yticklabels():
            label.set_weight('bold')

        group1 = df[df['Conditions'] == order[0]][cluster]
        group2 = df[df['Conditions'] == order[1]][cluster]
        _, p_val = ttest_ind(group1, group2, equal_var=False)

        # Get position for the comparison bar ad significance marker for each cluster
        position = get_position_for_significance_bar(df, cluster, order, offset=bar_offset, orientation=orientation)
        significance = get_significance(p_val) 
        if significance != "n.s.":
            add_significance_marker(ax, 0, 1, position, significance, orientation, vertical_offset=asterisk_offset)
        
        plt.tight_layout()
        filename = f"{prefix}_{cluster}.{output_type}"
        plt.savefig(filename)
        plt.close()

def plot_all_clusters(df, clusters, order, labels=None, colors=['#dadada', '#ddeeff'], orientation='h', symbol_color=['#bababa', '#abcdef'], output_type='pdf', global_max=None, results_df=None):
    melted_df = df.melt(id_vars='Conditions', value_vars=clusters)

    if global_max is None:
        global_max = melted_df['value'].max()

    if orientation == 'v':
        y, x, orient = 'value', 'variable', 'v'
        plt.figure(figsize=(len(clusters) * 2, 4))
        plt.ylim(0, global_max)
    else:
        y, x, orient = 'variable', 'value', 'h'
        plt.figure(figsize=(4, len(clusters) * 2))
        plt.xlim(0, global_max)

    ax = sns.barplot(data=melted_df, y=y, x=x, hue='Conditions', palette=colors, errorbar='se', edgecolor='black', linewidth=2, orient=orient, order=clusters, hue_order=order, capsize=0.2)
    graph_formatting(ax)
    sns.swarmplot(data=melted_df, y=y, x=x, hue='Conditions', dodge=True, palette=symbol_color, size=7, linewidth=1, edgecolor='black', orient=orient, order=clusters, hue_order=order, legend=False)
    ax.legend().set_visible(False)

    if orientation == 'v':
        plt.ylabel(r'Cells*10$^{4} $/mm$^{3}$', weight='bold')
        plt.xlabel('')
        asterisk_offset = -0.05
        bar_offset = 0.15
    else: 
        plt.xlabel(r'Cells*10$^{4} $/mm$^{3}$', weight='bold')
        plt.ylabel('')
        asterisk_offset = 0.035
        bar_offset = 0.2

    for idx, cluster in enumerate(clusters):
        # Get y position for significance marker for each cluster
        position = get_position_for_significance_bar(df, cluster, order, offset=bar_offset, orientation=orientation)
        significance = results_df.loc[results_df['Cluster'] == cluster, 'Significance'].iloc[0]
        
        if significance != "n.s.":
            # Add significance marker between the bars for each cluster
            add_significance_marker(ax, idx-0.2, idx+0.2, position, significance, orientation, vertical_offset=asterisk_offset)

    # plt.legend(loc='lower right') # uncomment to add legend
    # if labels:
    #     plt.legend(title='', labels=labels)

    plt.tight_layout()
    filename = f"{prefix}_all_clusters.{output_type}"
    plt.savefig(filename)
    plt.close()

def plot_significant_clusters(df, significant_clusters, order, labels=None, colors=['#dadada', '#ddeeff'], orientation='h', symbol_color=['#bababa', '#abcdef'], output_type='pdf', global_max=None, results_df=None):
    if not significant_clusters:
        return
    
    if global_max is None:
        global_max = df[significant_clusters].max().max()

    if orientation == 'v':
        plt.figure(figsize=(len(significant_clusters) * 2, 4))
        y, x, orient = 'value', 'variable', 'v'
        plt.ylim(0, global_max)
    else:
        plt.figure(figsize=(4, len(significant_clusters) * 2))
        y, x, orient = 'variable', 'value', 'h'
        plt.xlim(0, global_max)
        
    ax = sns.barplot(data=df.melt(id_vars='Conditions', value_vars=significant_clusters), y=y, x=x, hue='Conditions', palette=colors, errorbar='se', orient=orient, order=significant_clusters, hue_order=order, edgecolor='black', linewidth=2, capsize=0.2)
    graph_formatting(ax)
    sns.swarmplot(data=df.melt(id_vars='Conditions', value_vars=significant_clusters), y=y, x=x, hue='Conditions', dodge=True, palette=symbol_color, size=7, linewidth=1, edgecolor='black', orient=orient, order=significant_clusters, hue_order=order, legend=False)
    ax.legend().set_visible(False)

    if orientation == 'v':
        plt.ylabel(r'Cells*10$^{4} $/mm$^{3}$', weight='bold')
        plt.xlabel('')
        asterisk_offset = -0.05 
        bar_offset = 0.15 
    else: 
        plt.xlabel(r'Cells*10$^{4} $/mm$^{3}$', weight='bold')
        plt.ylabel('')
        asterisk_offset = 0.035 
        bar_offset = 0.2 

    # plt.legend(loc='lower right')
    plt.gca().tick_params(width=2)
    plt.gca().spines['bottom'].set_linewidth(2)
    plt.gca().spines['left'].set_linewidth(2)
    # if labels:
    #    plt.legend(title='', labels=labels)

    for idx, cluster in enumerate(significant_clusters):
        # Get y position for significance marker for each cluster
        position = get_position_for_significance_bar(df, cluster, order, offset=bar_offset, orientation=orientation)
        significance = results_df.loc[results_df['Cluster'] == cluster, 'Significance'].iloc[0]
        
        if significance != "n.s.":
            # Add significance marker between the bars for each cluster
            add_significance_marker(ax, idx-0.2, idx+0.2, position, significance, orientation, vertical_offset=asterisk_offset) 
    
    plt.tight_layout()
    filename = f"{prefix}_significant_clusters.{output_type}"
    plt.savefig(filename)
    plt.close()

if __name__ == "__main__":
    args = parse_args()
    prefix = os.path.splitext(os.path.basename(args.input_csv))[0]
    
    df = pd.read_csv(args.input_csv)

    global_max = df.iloc[:, 2:].max().max()  # Get the maximum value across the entire dataset
    
    # Adjust the global max to be cells per 10,000
    global_max = global_max / 10000
    global_max += 0.1 * global_max # Add 10% to the max value for the axis limit

    for column in df.columns[2:]:
        if df[column].max() == 0:
            print(f"Column {column} only has zero values!")

    cluster_density_t_tests(df, args.order, args.labels, args.colors, args.orient, args.symbol_color, args.output_type, global_max)

    results_df = pd.read_csv(f"{prefix}_t_test_results.csv")

    significant_clusters = results_df[results_df["P-value"] < 0.05]["Cluster"].tolist()
    
    # Convert significant clusters to integers
    significant_clusters = [int(cluster.split('_')[1]) for cluster in significant_clusters]

    total_clusters = len(df.columns[2:])
    validation_rate = len(significant_clusters) / total_clusters * 100

    if args.labels:
        save_legend_to_file(args.labels, args.colors, filename=f"{prefix}__legend.{args.output_type}")

    with open(f"{prefix}_validation_rate.txt", 'w') as file:
        file.write(f"\n  Number of significant clusters: {len(significant_clusters)}\n")
        file.write(f"  Total number of clusters: {total_clusters}\n")
        file.write(f"  Validation rate: {validation_rate:.2f}%\n")
        file.write(f"\n  Significant clusters: " + ' '.join(str(cluster) for cluster in significant_clusters) + "\n")

    print(f"\n  Number of significant clusters: {len(significant_clusters)}")
    print(f"  Total number of clusters: {total_clusters}")
    print(f"  Validation rate: {validation_rate:.2f}%")
    print(f"\n  Significant clusters: {' '.join(str(cluster) for cluster in significant_clusters)}")


# TO DO: 
# use color pallets by default? 
# Add option for resizing the plots
# Separate out significant clusters into a separate plot based on effect direction (for fstats)
# simplify the code
# optionally label clusters like: VTA (1), CP (2), etc.
# optionally sort clusters based on anatomical relationships
