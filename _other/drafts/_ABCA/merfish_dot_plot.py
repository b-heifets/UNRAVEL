#!/usr/bin/env python3

"""
Use merfish_dot_plot.py from UNRAVEL to analyze scRNA-seq expression.

Prereqs:
    - merfish_filter.py
    - merfish_join_expression_data.py

Usage:
------
    ./merfish_dot_plot.py -i path/cells_w_gene_exp.csv -g gene [-c cell_level] [-r region_level] [-fh fig_height] [-fw fig_width] [-min min_color] [-max max_color] [-t threshold] [-v]
"""

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, print_func_name_args_times, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/filtered_cells_w_expression_data.csv', required=True, action=SM)
    reqs.add_argument('-g', '--gene', help='Gene to analyze', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-c', '--cell_level', help='Cell type level (class \[default], subclass, supertype, cluster)', default='class', action=SM)
    opts.add_argument('-r', '--region_level', help='Region level (category, division, structure, [default]substructure). It will be prepended with parcellation_', default='substructure', action=SM)
    opts.add_argument('-n', '--neurons', help='Filter out non-neuronal cells. Default: False', action='store_true', default=False)
    opts.add_argument('-fh', '--fig_height', help='Fig height', default=4, type=float, action=SM)
    opts.add_argument('-fw', '--fig_width', help='Fig width', default=4, type=float, action=SM)
    opts.add_argument('-min_c', '--min_color', help='Min color value', default=0, type=float, action=SM)
    opts.add_argument('-max_c', '--max_color', help='Max color value', default=8, type=float, action=SM)
    opts.add_argument('-min_s', '--min_size', help='Min dot size', default=1, type=float, action=SM)
    opts.add_argument('-max_s', '--max_size', help='Max dot size', default=100, type=float, action=SM)
    opts.add_argument('-t', '--threshold', help='Threshold for gene expression (3 \[default] is stringent)', default=3, type=float, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity', action='store_true', default=False)

    return parser.parse_args()

# TODO: Color region names based on metadata. Sort regions based on order in metadata. Define custom order for humans to match mice? 

# TODO: loop over genes and make a dot plot for each gene

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the CSV file
    cell_exp_df = pd.read_csv(args.input, dtype={'cell_label': str})
    
    if args.neurons:
        cell_exp_df = cell_exp_df[cell_exp_df['class'].str.split().str[0].astype(int) <= 29]

    # Determine unique cell types
    cell_types = cell_exp_df[args.cell_level].unique()

    # Determine unique regions
    parecellation = 'parcellation_' + args.region_level
    uniq_regions = cell_exp_df[parecellation].unique()
    if uniq_regions.size == 1:
        region = uniq_regions[0]
    else:
        print(f'More than one region present: {uniq_regions=}\n')
        import sys ; sys.exit()

    # Plan: make a region x cell_type matrix with mean_expression values (color) and percent_expressing values (diameter of dot) for the gene of interest   
    results = []
    for cell_type in cell_types:
        # Filter cells by cell type
        df_subset = cell_exp_df[cell_exp_df[args.cell_level] == cell_type]

        # Calculate metrics using the number of rows (cells)
        expressing_cells = df_subset[df_subset[args.gene] > args.threshold].shape[0]
        total_cells = df_subset.shape[0]
        mean_expression = df_subset[args.gene].mean(numeric_only=True)
        percent_expressing = (expressing_cells / total_cells * 100) if total_cells > 0 else 0

        # Store the results
        results.append({
            'Gene': args.gene,
            'Cell type': cell_type,
            'Region': region,
            'Mean expression': mean_expression,
            'Percent expressing': percent_expressing,
            'Expressing cells': expressing_cells,
            'Total cells': total_cells
        })

    # Convert to DataFrame
    dot_plot_df = pd.DataFrame(results)
    dot_plot_df = dot_plot_df.sort_values('Cell type')
    print(f'\n{dot_plot_df=}\n')

    # Dynamically adjust figure width based on the number of genes
    n_genes = dot_plot_df["Gene"].nunique()
    computed_width = max(args.fig_width, n_genes * 1.5)  # Adjust width per gene, with a minimum

    fig, ax = plt.subplots(figsize=(computed_width, args.fig_height), constrained_layout=True)
    
    # Scale the dot sizes based on the percent expressing
    min_expression = dot_plot_df["Percent expressing"].min()
    min_dot_size = args.min_size   # Smallest dot when 0% of cells express
    if min_expression == 100:
        min_dot_size = 200

    # Create the dot plot with genes on the x-axis (use magma_r colormap)
    scatter = sns.scatterplot(
        data=dot_plot_df,
        x="Gene",  # Put genes on the x-axis
        y="Cell type",  # Cell types remain on the y-axis
        size="Percent expressing",
        hue="Mean expression",
        hue_norm=(args.min_color, args.max_color),
        sizes=(min_dot_size, args.max_size),  # Adjust size range for a smoother gradient
        palette=sns.color_palette("magma_r", as_cmap=True),  # Use continuous colormap
        edgecolor="w",
        ax=ax, 
        legend=False
    )



    # Customize plot labels and title
    ax.set_xlabel("Gene", fontsize=12, fontweight="bold")
    ax.set_ylabel(f"Cell Type ({args.cell_level})", fontsize=12, fontweight="bold")
    ax.set_title(region, fontsize=14, fontweight="bold")

    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45, ha="right")  # Correct

    plt.show()
    import sys ; sys.exit()



    # Extract legend elements
    handles, labels = scatter.get_legend_handles_labels()

    # Create a separate figure for the legend
    fig_legend, ax_legend = plt.subplots(figsize=(3, 2))  # Adjust size as needed
    ax_legend.axis("off")  # Remove axes
    legend = ax_legend.legend(
        handles=handles, 
        labels=labels, 
        loc="center",
        title="Legend",
        fontsize=10,
        title_fontsize=12,
        frameon=False  # Remove legend border
    )

    # Show both figures separately
    plt.show()  # Show the main dot plot
    plt.show(fig_legend)  # Show the legend separately


    import sys ; sys.exit()



    # Update the legend
    handles, labels = plot.get_legend_handles_labels()
    labels[0] = "Mean Expression"
    # labels[7] = "Percent Expressing"
    labels[len(labels) // 2] = "Percent Expressing"

    # Regenerate the legend with finer control over labels and layout
    legend = plot.legend(
        handles=handles,
        labels=labels,
        loc="upper left",
        bbox_to_anchor=(1, 1.2),
        title_fontsize='13',
        fontsize='10'
    )

    # Adjust x and y axis limits and spacing to make the plot more compact
    # plt.xlim(-0.5, len(dot_plot_df['region'].unique()) - 0.5)
    # plt.ylim(-0.5, len(dot_plot_df['cell_type'].unique()) - 0.5)
    # plt.subplots_adjust(left=0.15, right=0.85, top=0.9, bottom=0.3)

    plt.tight_layout()
    plt.show()


    verbose_end_msg()


if __name__ == '__main__':
    main()