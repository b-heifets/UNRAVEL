#!/usr/bin/env python3

"""
Organize filtered MERFISH data for plotting cell type proportion across slices. This is done for each ontology level.

Prereqs:
    - merfish_cell_types_across_slices.py -b <abc_download_root> -c parcellation_substructure -val BLAa -o BLAa_cells.csv

Notes:
    - Lower numbers for brain sections and z_reconstructed indicate more posterior sections.

Usage:
------
    ./merfish_cell_types_across_slices.py -i path/input.csv
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/input.csv', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-n', '--neuronal', help='Only keep neuronal cells (neurotransmitter == NaN).', action='store_true', default=False)
    opts.add_argument('-o', '--output_dir', help="Directory to save output plots.", default='.', action=SM)
    opts.add_argument('-l', '--levels', help="Ontological levels to calculate and plot proportions for", default=['class', 'subclass', 'supertype', 'cluster'], nargs='*', action=SM)
    opts.add_argument('-t', '--threshold', help="Minimum proportion threshold for plotting", default=1.0, type=float, action=SM)

    return parser.parse_args()


def calculate_proportions(df, level):
    """
    Calculate the proportion of each cell type at a specific ontological level across slices.
    
    Args:
        df (pd.DataFrame): Filtered cell metadata DataFrame.
        level (str): Ontological level to calculate proportions ('class', 'subclass', etc.).
    
    Returns:
        pd.DataFrame: DataFrame with slice, cell type, and proportion data.
    """
    # Group by brain section and cell type at the given level
    grouped_df = df.groupby(['z_reconstructed', level]).size().reset_index(name='count')

    # Sort by z_reconstructed
    grouped_df = grouped_df.sort_values('z_reconstructed', ascending=False)

    # Calculate total counts per slice
    total_counts = grouped_df.groupby('z_reconstructed')['count'].transform('sum')

    # Calculate proportions
    grouped_df['proportion'] = (grouped_df['count'] / total_counts) * 100

    return grouped_df

def plot_proportions(proportions_df, level, output_dir, color_dict, threshold):
    """
    Create a plot of cell type proportions for a given ontological level across slices, applying a minimum threshold.
    
    Args:
        proportions_df (pd.DataFrame): DataFrame with slice, cell type, and proportion data.
        level (str): Ontological level used for grouping ('class', 'subclass', etc.).
        output_dir (str): Directory to save the plots.
        color_dict (dict): Dictionary mapping cell types to their colors.
        threshold (float): Minimum proportion threshold for including a cell type in the plot.
    """
    # Pivot the data for easier plotting
    pivot_df = proportions_df.pivot(index='z_reconstructed', columns=level, values='proportion').fillna(0)

    # Filter out cell types that are below the threshold across all slices
    filtered_columns = pivot_df.columns[pivot_df.max(axis=0) >= threshold]
    pivot_df = pivot_df[filtered_columns]

    # Sort by z_reconstructed in descending order
    pivot_df = pivot_df.sort_index(ascending=False)

    print(f'\nFiltered Pivoted DataFrame for plotting:\n{pivot_df}\n')

    # Plot each cell type
    plt.figure(figsize=(12, 6))
    for cell_type in pivot_df.columns:
        color = color_dict.get(cell_type, "#000000")  # Default to black if color is missing
        plt.plot(pivot_df.index, pivot_df[cell_type], label=cell_type, color=color)

    # Ensure the x-axis shows the desired descending order
    plt.gca().invert_xaxis()

    # Plot details
    plt.title(f'Cell Type Proportions Across Slices ({level.capitalize()})')
    plt.xlabel('Position (z in MERFISH-CCF space)')
    plt.ylabel('Proportion (%)')
    plt.legend(title=level.capitalize(), bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    plt.savefig(f"{output_dir}/{level}_proportions.png")

    # plt.show()
    plt.close()

@log_command
def main():
    install()
    args = parse_args()

    # Load the filtered cell metadata
    df = pd.read_csv(args.input, usecols=['brain_section_label', 'z_reconstructed', 'neurotransmitter',
                                          'class', 'class_color', 'subclass', 'subclass_color',
                                          'supertype', 'supertype_color', 'cluster', 'cluster_color'])

    # Sort the data by z_reconstructed
    df = df.sort_values('z_reconstructed', ascending=False)
    print("\nLoaded and sorted data:", df, sep="\n")

    # Drop non-neuronal cells based on the class prefix
    if args.neuronal:
        df['class_numeric'] = df['class'].str.split().str[0].astype(int)
        df = df[df['class_numeric'] <= 29]
        print("\nFiltered neuronal cells (class <= 29):", df.head(), sep="\n")

    # Calculate proportions and plot for each ontological level
    for level in args.levels:
        color_column = f"{level}_color"  # Dynamically select the color column
        if color_column not in df.columns:
            print(f"Color column '{color_column}' not found in the input data. Skipping level '{level}'.")
            continue

        # Calculate proportions at the given level
        proportions_df = calculate_proportions(df, level)
        print(f"\nProportions at {level.capitalize()} level:")
        print(proportions_df)

        # Create a dictionary mapping cell types to their colors
        level_color = f"{level}_color"
        class_color_dict = df[[level, level_color]].drop_duplicates().set_index(level)[level_color].to_dict()

        # Plot the proportions with the threshold
        plot_proportions(proportions_df, level, args.output_dir, class_color_dict, args.threshold)



if __name__ == '__main__':
    main()
