#!/usr/bin/env python3

"""
Use RNAseq_dot_plot.py from UNRAVEL to analyze scRNA-seq expression.

Prereqs:
    - RNAseq_expression scripts

Input: 
    - path/gene_expression.csv
    - Columns: gene, cell_type, region, mean_expression, median_expression, percent_expressing, expressing_cells, total_cells
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
    reqs.add_argument('-i', '--input', help='path/gene_expression.csv', required=True, action=SM)
    reqs.add_argument('-g', '--gene', help='Gene to analyze', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', action=SM)
    opts.add_argument('-fh', '--fig_height', help='Fig height', default=4, type=float, action=SM)
    opts.add_argument('-fw', '--fig_width', help='Fig width', default=14, type=float, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity', action='store_true', default=False)

    return parser.parse_args()

# TODO: Color region names based on metadata. Sort regions based on order in metadata. Define custom order for humans to match mice? 

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the CSV file
    data = pd.read_csv(args.input)

    # Filter for the gene of interest
    data = data[data['gene'] == args.gene]

    # Color regions based on metadata
    if args.base:
        download_base = Path(args.base)
        is_human = "Human" in data['region'].unique()

        if is_human:
            region_colors_path = download_base / "metadata" / "WHB-10Xv3" / "20240330" / "region_of_interest_structure_map.csv"
        else:
            region_colors_path = download_base / "metadata" / "WMB-10X" / "20231215" / "region_of_interest_metadata.csv"

        # Human columns: region_of_interest_label, structure_identifier, structure_symbol, structure_name, color_hex_triplet
        # Mouse columns: label, acronym, name, order, color_hex_triplet  # Use this order 
        if region_colors_path.exists():
            region_colors = pd.read_csv(region_colors_path)
            region_colors = region_colors.set_index('region_of_interest_label' if is_human else 'acronym')
            region_colors = region_colors['color_hex_triplet']
            data['region_color'] = data['region'].map(region_colors)

    # Trim "Human" from region names
    data['region'] = data['region'].str.replace("Human ", "", regex=False)

    # Drop rows with with missing values for cell type
    data = data.dropna(subset=['cell_type'])

    # Set custom order for cell types and regions
    cell_types_order = sorted(data['cell_type'].unique())
    if "Other" in cell_types_order:
        cell_types_order.remove("Other")
        cell_types_order.append("Other")  # Move "Other" to the end

    regions_order = sorted(data['region'].unique())
    if "Whole Brain" in regions_order:
        regions_order.remove("Whole Brain")
        regions_order.insert(0, "Whole Brain")  # Move "Whole Brain" to the start

    # Apply the custom order to cell_type and region columns
    data['cell_type'] = pd.Categorical(data['cell_type'], categories=cell_types_order, ordered=True)
    data['region'] = pd.Categorical(data['region'], categories=regions_order, ordered=True)
    data = data.sort_values(['cell_type', 'region'])

    # Set up the plot dimensions and aesthetics
    plt.figure(figsize=(args.fig_width, args.fig_height))
    sns.set(style="white")  # Remove grid lines for a cleaner look

    # Create the dot plot with a smoother gradient
    plot = sns.scatterplot(
        data=data,
        x="region",
        y="cell_type",
        size="percent_expressing",
        hue="mean_expression",
        sizes=(1, 200),  # Adjust size range for a smoother gradient
        palette=sns.color_palette("viridis", as_cmap=True),  # Use continuous colormap
        edgecolor="w",
        legend="brief"
    )

    # Customize plot labels and title
    plt.xlabel("Brain Region", fontsize=12, fontweight='bold')
    plt.ylabel("Cell Type", fontsize=12, fontweight='bold')
    plt.title(f"Gene Expression Dot Plot for {args.gene}", fontsize=14, fontweight='bold')
    plt.xticks(rotation=90)  # Rotate x-axis labels for readability

    # Update the legend
    handles, labels = plot.get_legend_handles_labels()

    # labels[0] = "Mean Expression"
    ### labels[7] = "Percent Expressing"
    # labels[len(labels) // 2] = "Percent Expressing"

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
    plt.xlim(-0.5, len(data['region'].unique()) - 0.5)
    plt.ylim(-0.5, len(data['cell_type'].unique()) - 0.5)
    plt.subplots_adjust(left=0.15, right=0.85, top=0.9, bottom=0.3)

    plt.tight_layout()
    plt.show()

    verbose_end_msg()

if __name__ == '__main__':
    main()
