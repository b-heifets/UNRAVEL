#!/usr/bin/env python3

"""
Use ``abca_sunburst`` or ``sb`` from UNRAVEL to generate a sunburst plot of cell type proportions across all ontological levels.

Prereqs: 
    - merfish_filter.py or RNAseq_expression.py + RNAseq_join_expression_data.py to generate the input cell metadata.
    
Outputs:
    - path/input_sunburst.csv and [WMB_sunburst_colors.csv or HMB_sunburst_colors.csv if --output_lut is provided]

Note:
    - LUT location: unravel/core/csvs/ABCA/

Next steps:
    - Use input_sunburst.csv to make a sunburst plot or regional volumes in Flourish Studio (https://app.flourish.studio/)
    - It can be pasted into the Data tab (categories columns = cell type columns, Size by = percent column)
    - Preview tab: Hierarchy -> Depth to 5, Colors -> paste hex codes from ..._sunburst_colors.csv into Custom overrides

Usage:
------ 
    abca_sunburst -i path/cell_metadata_filtered.csv [-n] [-l] [-v]
"""

import numpy as np
import pandas as pd
import shutil
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/cell_metadata_filtered.csv', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-s', '--species', help='Species to analyze ("mouse" or "human"). Default: mouse', default='mouse', action=SM)
    opts.add_argument('-n', '--neurons', help='Filter out non-neuronal cells. Default: False', action='store_true', default=False)
    opts.add_argument('-l', '--output_lut', help='Output WMB_sunburst_colors.csv if flag provided (for ABCA coloring)', action='store_true')

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

def filter_non_neuronal_cells(cells_df, species):
    """Filter out non-neuronal cells based on the species."""
    species = species.lower()
    if species == 'mouse':
        return cells_df[cells_df['class'].str.split().str[0].astype(int) <= 29]
    elif species == 'human':
        nonneurons = ['Oligodendrocyte', 'Committed oligodendrocyte precursor', 'Oligodendrocyte precursor',
                      'Astrocyte', 'Ependymal', 'Microglia', 'Vascular', 'Bergmann glia', 'Fibroblast', 'Choroid plexus']
        return cells_df[~cells_df['supercluster'].str.split().str[0].isin(nonneurons)]
    else:
        raise ValueError(f"Unsupported species: {species}. Supported species are 'mouse' and 'human'.")

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    species = args.species.lower()

    # Load the CSV file
    if species == 'mouse':
        cells_df = pd.read_csv(args.input, usecols=['neurotransmitter', 'class', 'subclass', 'supertype', 'cluster'])
    elif species == 'human':
        cells_df = pd.read_csv(args.input, usecols=['neurotransmitter', 'supercluster', 'cluster', 'subcluster'])
    else:
        raise ValueError(f"Unsupported species: {args.species}. Supported species are 'mouse' and 'human'.")

    # Replace blank values in 'neurotransmitter' column with 'NA'
    cells_df['neurotransmitter'] = cells_df['neurotransmitter'].fillna('NA')

    if args.neurons:
        cells_df = filter_non_neuronal_cells(cells_df, species)
        
    # Groupby the finest level of granularity (cluster or subcluster) to calculate the percentage of cells in each cell type
    fine_level_col = 'subcluster' if 'subcluster' in cells_df.columns else 'cluster'
    fine_df = cells_df.groupby(fine_level_col).size().reset_index(name='counts')  # Count the number of cells in each cluster
    fine_df = fine_df.sort_values('counts', ascending=False)  # Sort the clusters by the number of cells

    # Add a column for the percentage of cells in each fine level cell type
    fine_df['percent'] = fine_df['counts'] / fine_df['counts'].sum() * 100

    # Drop the 'counts' column
    fine_df = fine_df.drop(columns='counts')

    # Join the cells_df with the fine_df
    cells_df = cells_df.merge(fine_df, on=fine_level_col)

    # Drop duplicate rows
    cells_df = cells_df.drop_duplicates()

    # Sort by percentage
    cells_df = cells_df.sort_values('percent', ascending=False).reset_index(drop=True)

    # If human, insert an empty column after subcluster and before percent
    if species == 'human':
        cells_df.insert(cells_df.columns.get_loc('subcluster') + 1, '.', '.')

    print(f'\n{cells_df}\n')

    # Save the output to a CSV file
    output_path = str(Path(args.input)).replace('.csv', '_sunburst.csv')
    cells_df.to_csv(output_path, index=False)

    if args.output_lut:
        if species == 'mouse':
            lut_path = Path(__file__).parent.parent.parent.parent / 'unravel' / 'core' / 'csvs' / 'ABCA' / 'WMB_sunburst_colors.csv'
        elif species == 'human':
            lut_path = Path(__file__).parent.parent.parent.parent / 'unravel' / 'core' / 'csvs' / 'ABCA' / 'WHB_sunburst_colors.csv'
        shutil.copy(lut_path, Path(args.input).parent / lut_path.name)

    verbose_end_msg()


if __name__ == '__main__':
    main()