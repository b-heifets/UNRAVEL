#!/usr/bin/env python3
"""
Use ``marker_summary`` from UNRAVEL to calculate mean or enrichment scRNA-seq values for multiple cell types.

Note:
    - Enrichment for a gene in a cell type = mean expression in cell type / mean expression in all cells
    - Markers for each mouse cell type are available in Supplementary Table 7 from Yao et al., (2023): 
    - https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-023-06812-z/MediaObjects/41586_2023_6812_MOESM8_ESM.xlsx

Usage:
------
    ./marker_summary.py -i path/input.csv -g Gene1 Gene2 -c column_name -ct cell_type1 cell_type2 [-o path/output.csv] [-s species] [-m mean|enrichment] [-v]
"""

from pathlib import Path
from typing import List
import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.allen_institute.abca.merfish.gene_catalog import genes
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path to the input CSV file.', required=True, action=SM)
    reqs.add_argument('-g', '--genes', help='Gene(s) to analyze (e.g., Drd1 or Drd1 Drd2).', required=True, nargs='*', action=SM)
    reqs.add_argument('-c', '--column', help='Cell type column to calculate enrichment for (neurotransmitter, class, subclass, supertype, cluster, supercluster, subcluster).', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-ct', '--cell_type', help="Cell type(s) to include. Default: all", nargs='*', default=['all'], action=SM)
    opts.add_argument('-o', '--output', help='Path to output CSV file.', default=None, action=SM)
    opts.add_argument('-s', '--species', help='Species (human or mouse). Default: mouse', default='mouse', action=SM)
    opts.add_argument('-m', '--metric', help="Metric to save: 'mean' or 'enrichment'. Default: mean", choices=['mean', 'enrichment'], default='mean', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

def normalize_gene_names(gene_list: List[str], species: str) -> List[str]: # This could be imported once integrated elsewhere
    """Normalize gene names based on species conventions."""
    if species == 'mouse':
        # Mouse gene symbols: capitalize only the first letter (Htr2a)
        return [g.lower().capitalize() for g in gene_list]
    elif species == 'human':
        # Human gene symbols: all uppercase (HTR2A)
        return [g.upper() for g in gene_list]
    return gene_list

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the scRNA-seq data
    input_path = Path(args.input)
    cols = pd.read_csv(args.input, nrows=0).columns
    if args.column not in cols:
        raise ValueError(f"Selected column '{args.column}' not found in input columns.")

    genes = normalize_gene_names(args.genes, species=args.species)
    for gene in genes:
        if gene not in cols:
            raise ValueError(f"Gene '{gene}' not found in input columns.")

    usecols = [args.column] + genes
    df = pd.read_csv(input_path, usecols=usecols)

    if args.metric == 'enrichment':
        mean_df_unique = df.groupby(args.column).mean(numeric_only=True)  # Mean with unique genes only to avoid duplication issues
        overall_means_unique = df.mean(numeric_only=True)

        # Enrichment = mean(cell type) / mean(all cells)
        enrichment_unique_df = mean_df_unique / overall_means_unique

        # Reorder columns to match input gene order (including duplicates)
        result_df = enrichment_unique_df[genes]

    else:
        # Reorder columns to match input gene order (including duplicates)
        df_gene_order = df[[args.column] + genes]

        # Mean expression per cell type
        result_df = df_gene_order.groupby(args.column).mean(numeric_only=True)

    # Filter by cell type(s)
    if args.cell_type == ['all']:
        output_df = result_df
    else:
        output_df = result_df.loc[result_df.index.isin(args.cell_type)]

        # Reorder rows to match args.cell_type order
        output_df = output_df.reindex(args.cell_type)

    # Print the output DataFrame
    print(f'\n{output_df}\n')

    # Save
    metric_suffix = "enrichment" if args.metric == "enrichment" else "mean"
    cell_type_suffix = "all_cells" if args.cell_type == ['all'] else "selected_cells"
    default_output = input_path.parent / f"{input_path.stem}_{args.column}_{metric_suffix}_{cell_type_suffix}.csv"
    output_path = Path(args.output) if args.output else default_output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.round(6).to_csv(output_path, index=True)
    print(f"\n[green]Saved {args.metric} values for {len(output_df)} cell types to:[/green] {output_path}")

    verbose_end_msg()

if __name__ == '__main__':
    main()
