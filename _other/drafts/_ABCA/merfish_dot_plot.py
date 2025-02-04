#!/usr/bin/env python3

"""
Use merfish_dot_plot.py from UNRAVEL to analyze scRNA-seq expression.

Prereqs:
    - merfish_filter.py
    - merfish_join_expression_data.py

Usage:
------
    ./merfish_dot_plot.py -i path/cells_w_gene_exp.csv -g gene [-c cell_level] [-r region_level] [-b base] [-fh fig_height] [-fw fig_width] [-v]
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
    opts.add_argument('-fh', '--fig_height', help='Fig height', default=4, type=float, action=SM)
    opts.add_argument('-fw', '--fig_width', help='Fig width', default=4, type=float, action=SM)
    opts.add_argument('-min', '--min_color', help='Min color value', default=2, type=float, action=SM)
    opts.add_argument('-max', '--max_color', help='Max color value', default=6, type=float, action=SM)

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
        expressing_cells = df_subset[df_subset[args.gene] > 0].shape[0]
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
    
    # # Ensure dots are large when all values are the same
    # min_percent = dot_plot_df["Percent expressing"].min()
    # if min_percent == 100:
    #     sizes_range = (200, 200)
    # else:
    #     sizes_range = (1, 200)

    # Define absolute size range

    # Scale the dot sizes based on the percent expressing
    min_expression = dot_plot_df["Percent expressing"].min()
    max_expression = dot_plot_df["Percent expressing"].max()
    min_dot_size = 0   # Smallest dot when 0% of cells express
    max_dot_size = int(max_expression * 2)  # Largest dot when 100% of cells express
    if min_expression == 100:
        min_dot_size = 200

    # Create the dot plot with genes on the x-axis
    scatter = sns.scatterplot(
        data=dot_plot_df,
        x="Gene",  # Put genes on the x-axis
        y="Cell type",  # Cell types remain on the y-axis
        size="Percent expressing",
        hue="Mean expression",
        hue_norm=(args.min_color, args.max_color),
        sizes=(min_dot_size, max_dot_size),  # Adjust size range for a smoother gradient
        palette=sns.color_palette("viridis", as_cmap=True),
        edgecolor="w",
        ax=ax
    )

    # Customize plot labels and title
    ax.set_xlabel("Gene", fontsize=12, fontweight="bold")
    ax.set_ylabel(f"Cell Type ({args.cell_level})", fontsize=12, fontweight="bold")
    ax.set_title(region, fontsize=14, fontweight="bold")

    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45, ha="right")  # Correct

    plt.show()

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

    import sys ; sys.exit()



    
    

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
    plt.xlim(-0.5, len(data['region'].unique()) - 0.5)
    plt.ylim(-0.5, len(data['cell_type'].unique()) - 0.5)
    plt.subplots_adjust(left=0.15, right=0.85, top=0.9, bottom=0.3)

    plt.tight_layout()
    plt.show()

    verbose_end_msg()

if __name__ == '__main__':
    main()

@print_func_name_args_times()
def merfish_dot_plot_metrics(gdata, cell_df, genes):
    # Prepare DataFrame to store results
    results = []

    # Include 'Whole Brain' as a region
    cell_df['region'] = cell_df['region_of_interest_acronym']
    cell_df['region'].fillna('Whole Brain', inplace=True)
    regions = cell_df['region'].unique()

    # Get unique combinations of cell_type and region
    group_combinations = cell_df[['cell_type', 'region']].drop_duplicates()

    for gene in genes:
        for _, row in group_combinations.iterrows():
            cell_type = row['cell_type']
            region = row['region']
            # Filter cells by cell type and region
            cells_of_interest = cell_df[(cell_df['cell_type'] == cell_type) & (cell_df['region'] == region)]
            cell_indices = cells_of_interest.index.intersection(gdata.index)
            gene_expression = gdata.loc[cell_indices, gene]

            # Calculate metrics
            expressing_cells = gene_expression[gene_expression > 0].count()
            total_cells = gene_expression.count()
            mean_expression = gene_expression.mean()
            median_expression = gene_expression.median()
            percent_expressing = (expressing_cells / total_cells * 100) if total_cells > 0 else 0

            # Store the results
            results.append({
                'gene': gene,
                'cell_type': cell_type,
                'region': region,
                'mean_expression': mean_expression,
                'median_expression': median_expression,
                'percent_expressing': percent_expressing,
                'expressing_cells': expressing_cells,
                'total_cells': total_cells
            })

        # Calculate whole-brain metrics for each gene and cell type
        for cell_type in cell_df['cell_type'].unique():
            whole_brain_cells = cell_df[cell_df['cell_type'] == cell_type]
            cell_indices = whole_brain_cells.index.intersection(gdata.index)
            gene_expression = gdata.loc[cell_indices, gene]

            # Calculate whole-brain metrics
            expressing_cells = gene_expression[gene_expression > 0].count()
            total_cells = gene_expression.count()
            mean_expression = gene_expression.mean()
            median_expression = gene_expression.median()
            percent_expressing = (expressing_cells / total_cells * 100) if total_cells > 0 else 0

            # Append whole-brain results
            results.append({
                'gene': gene,
                'cell_type': cell_type,
                'region': 'Whole Brain',
                'mean_expression': mean_expression,
                'median_expression': median_expression,
                'percent_expressing': percent_expressing,
                'expressing_cells': expressing_cells,
                'total_cells': total_cells
            })

    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    return results_df