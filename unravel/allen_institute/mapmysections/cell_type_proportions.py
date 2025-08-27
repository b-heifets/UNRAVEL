#!/usr/bin/env python3

"""
Use ``mms_cell_type_proportions`` or ``mms_ctp`` from UNRAVEL to calculate cell type proportions for an ontological level.

Prereqs: 
    - ``abca_merfish_filter`` or ``abca_merfish_filter_by_mask`` to generate the input cell metadata.

Output:
    - CSV file with cell type proportions for the specified column (e.g., neurotransmitter, class, subclass, supertype, cluster).
    - To organize data like in the MapMySections data challenge, use --transpose to get cell types as columns (one row of proportions per input file).

Note:
    - Only cell types present in the filtered MERFISH data are included.
    - Cell type names are standardized by replacing spaces, dashes, and slashes with dots (``.``), and removing any numerical prefixes (e.g., ``1.``).

Next steps:
    - To summarize cell type proportions across multiple files (like in MapMySections), usemms_concat`` to concatenate multiple CSVs into one file

Usage:
------
    mms_ctp -i <input_path(s)> [-col subclass] [-rc parcellation_structure -r VISp] [-n] [-c] [-t] [-o output_path]

Usage for MapMySections (VISp example):
---------------------------------------
    mms_ctp -i <input_path(s)> -col subclass -rc parcellation_structure -r VISp -t -o VISp_subclass

Usage for MapMySections (all regions):
--------------------------------------
    mms_ctp -i <input_path(s)> -col subclass -t -o all_regions_subclass
"""

import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help="path/cell_metadata_filtered.csv file(s) or glob pattern(s). E.g., '*.csv'", required=True, nargs='*', action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-col', '--column', help='Column to calculate proportions for (neurotransmitter \[default], class, subclass, supertype, cluster)', default='neurotransmitter', action=SM)
    opts.add_argument('-rc', '--region_col', help='Region column (e.g., parcellation_structure or parcellation_substructure)', default=None, action=SM)
    opts.add_argument('-r', '--region', help='Region to filter by (e.g., "VISp" with parcellation_structure). If not provided, all regions are included.', default=None, action=SM)
    opts.add_argument('-n', '--neurons', help='Filter out non-neuronal cells. Default: False', action='store_true', default=False)
    opts.add_argument('-c', '--counts', help='Include counts in the output. Default: False', action='store_true', default=False)
    opts.add_argument('-t', '--transpose', help='Transpose the output DataFrame. Default: False', action='store_true', default=False)
    opts.add_argument('-o', '--output', help='Output directory path. Default: [region_]<column>_proportions[_transposed]/<input_file>.csv', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

def cell_type_proportions(cells_df, column='neurotransmitter'):
    """
    Calculate cell type proportions across all ontological levels.

    Parameters:
    -----------
    cells_df : pd.DataFrame
        DataFrame containing cell metadata with columns: 'neurotransmitter', 'class', 'subclass', 'supertype', 'cluster'.

    Returns:
    --------
    pd.DataFrame
        DataFrame with cell type proportions.
    """
    if column not in cells_df.columns:
        raise ValueError(f"Level '{column}' not found in the DataFrame columns. Available columns: {cells_df.columns.tolist()}")

    # Group by the level and count the number of cells for cell type at that level
    grouped_df = cells_df.groupby(column).size().reset_index(name='counts')

    # Sort by the number of cells
    grouped_df = grouped_df.sort_values('counts', ascending=False)

    # Calculate proportions
    grouped_df['proportions'] = grouped_df['counts'] / grouped_df['counts'].sum()
    
    return grouped_df.reset_index(drop=True)

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_paths = match_files(args.input)

    # Construct default output directory name
    if args.output:
        out_dir = Path(args.output)
    else:
        region_prefix = f"{args.region}_" if args.region else ""
        suffix = "_proportions_transposed" if args.transpose else "_proportions"
        out_dir = Path(f"{region_prefix}{args.column}{suffix}")
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.verbose:
        print(f'Output directory: {out_dir}')

    for input_path in input_paths:
        if args.verbose:
            print(f'\nProcessing file: {input_path}\n')

        # Load the CSV file
        if args.region_col:
            cells_df = pd.read_csv(input_path, usecols=['neurotransmitter', 'class', 'subclass', 'supertype', 'cluster', args.region_col])
        else:
            cells_df = pd.read_csv(input_path, usecols=['neurotransmitter', 'class', 'subclass', 'supertype', 'cluster'])

        print(f'\nLoaded cells DataFrame:\n{cells_df}\n')

        if args.region_col and args.region:
            # Filter cells by the specified region
            if args.region_col not in cells_df.columns:
                raise ValueError(f"Region column '{args.region_col}' not found in the DataFrame columns. Available columns: {cells_df.columns.tolist()}")
            cells_df = cells_df[cells_df[args.region_col] == args.region]
            print(f'\nFiltered cells by region ({args.region}):\n{cells_df}\n')
        elif args.region_col:
            # If region_col is provided but no region, raise an error
            raise ValueError(f"Region column '{args.region_col}' provided but no region specified. Please specify a region to filter by.")
        elif args.region:
            # If region is provided but no region_col, raise an error
            raise ValueError("Region specified but no region column provided. Please provide a region column to filter by.")

        print(f'\nCells DataFrame after filtering by region:\n{cells_df}\n')

        # Replace blank values in 'neurotransmitter' column with 'NA'
        cells_df['neurotransmitter'] = cells_df['neurotransmitter'].fillna('NA')

        if args.neurons:
            # Filter out non-neuronal cells
            cells_df = cells_df[cells_df['class'].str.split().str[0].astype(int) <= 29]

        print(f'\n{cells_df}\n')

        grouped_df = cell_type_proportions(cells_df, column=args.column)

        print(f'\n{grouped_df}\n')

        # Drop the 'counts' column
        if not args.counts:
            grouped_df = grouped_df.drop(columns='counts')

        ontology_path = Path(__file__).parent.parent.parent.parent / 'unravel' / 'core' / 'csvs' / 'ABCA' / 'WMB_unique_cell_types.csv'
        if ontology_path.exists():
            ontology_df = pd.read_csv(ontology_path, usecols=[args.column])
            ontology_df = ontology_df.dropna().reset_index(drop=True)  # This removes any rows with NaN in the specified column
            print(f'\nLoaded ontology DataFrame:\n{ontology_df}\n')

            # Merge with the ontology DataFrame on the specified column
            grouped_df = pd.merge(ontology_df, grouped_df, left_on=args.column, right_on=args.column, how='left')
            grouped_df['proportions'] = grouped_df['proportions'].fillna(0)
            print(f'\nMerged cell proportions DataFrame with ontology DataFrame:\n{grouped_df}\n')

            # Filter to keep only entries present in the filtered cells_df
            if args.region_col and args.region:
                grouped_df = grouped_df[grouped_df[args.column].isin(cells_df[args.column])]
                print(f'\nFiltered merged DataFrame by region ({args.region}):\n{grouped_df[[args.column, "proportions"]].head()}\n')

            # Rename values in the specified column (spaces, dashes, slashes to dots, and remove numerical prefixes)
            grouped_df[args.column] = (
                grouped_df[args.column]
                .str.replace(' ', '.', regex=False)
                .str.replace('-', '.', regex=False)
                .str.replace('/', '.', regex=False)
                .str.replace(r'^\d+\.', '', regex=True)
            )

            # Sort by the specified column
            grouped_df = grouped_df.sort_values(by=args.column).reset_index(drop=True)

            print(f'\nRenamed cell types and sorted merged DataFrame:\n{grouped_df}\n')

        else:
            print(f'Ontology file not found at {ontology_path}. Proceeding without merging.')

        # Transpose the DataFrame if requested
        if args.transpose:
            grouped_df = grouped_df.T
            grouped_df.columns = grouped_df.iloc[0]  # Set first row as new header
            grouped_df = grouped_df[1:].reset_index(drop=True)
            print(f'\nTransposed DataFrame:\n{grouped_df}\n')

        # Save the output to a CSV file
        output_file = input_path.name
        output_path = out_dir / output_file if out_dir else None
        print(f'Saving output to: {output_path}')
        grouped_df.to_csv(output_path, index=False)

    verbose_end_msg()


if __name__ == '__main__':
    main()