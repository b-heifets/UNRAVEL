#!/usr/bin/env python3

"""
Use ``marker_enrichment`` from UNRAVEL to load a scRNA-seq expression CSV file and calculate marker gene enrichment.

Note:
    - The enrichment is calculated for each gene and cell type (mean expression in cell type / mean expression overall).
    - Markers for each mouse cell type are available in Supplementary Table 7 from Yao et al., (2023): 
    - https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-023-06812-z/MediaObjects/41586_2023_6812_MOESM8_ESM.xlsx
"""

from pathlib import Path
from typing import List
import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path to the input CSV file.', required=True, action=SM)
    reqs.add_argument('-g', '--genes', help='Gene(s) to analyze (e.g., Drd1 or Drd1 Drd2).', required=True, nargs='*', action=SM)
    reqs.add_argument('-c', '--column', help='Cell type column to calculate enrichment for (neurotransmitter, class, subclass, supertype, cluster, supercluster, subcluster).', required=True, action=SM)
    reqs.add_argument('-ct', '--cell_type', help="Cell type to analyze (e.g., '014 LA-BLA-BMA-PA Glut'). Default: None", default=None, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Path to output CSV file.', default=None, action=SM)
    opts.add_argument('-s', '--species', help='Species to use (human or mouse). Default: mouse', default='mouse', action=SM)
    opts.add_argument('-m', '--metric', help="Metric to save: 'mean' for mean expression, 'enrichment' for enrichment ratio. Default: mean", choices=['mean', 'enrichment'], default='mean', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

def normalize_gene_names(gene_list: List[str], species: str) -> List[str]: # This could be imported once integrated elsewhere
    """Normalize gene names based on species conventions."""
    if species == 'mouse':
        # Mouse gene symbols: capitalize only the first letter (Htr2a)
        gene_list = [g.lower().capitalize() for g in gene_list]
    elif species == 'human':
        # Human gene symbols: all uppercase (HTR2A)
        gene_list = [g.upper() for g in gene_list]
    return gene_list

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the CSV file")
    input_path = Path(args.input)
    cols = pd.read_csv(args.input, nrows=0).columns
    if args.column not in cols:
        raise ValueError(f"Selected column '{args.column}' not found in input data columns.")
    genes = normalize_gene_names(args.genes, species=args.species)
    for gene in genes:
        if gene not in cols:
            raise ValueError(f"Gene '{gene}' not found in input data columns.")
    use = [args.column] + genes    
    df = pd.read_csv(input_path, usecols=use)

    # Make the args.column the first column
    cols = df.columns.tolist()
    cols.insert(0, cols.pop(cols.index(args.column))) # Move the cell type column to the front of the list
    df = df[cols] # Reorder the dataframe columns

    # Calculate mean expression per cell type
    summary_df = df.groupby(args.column).mean(numeric_only=True)
    overall_means = df.mean(numeric_only=True)

    # Calculate marker gene enrichment (mean for a cell type / mean across all cells)
    # Compute enrichment for all genes at once (vectorized)
    enrichment_df = summary_df[genes] / overall_means[genes]

    # Rename columns for clarity
    enrichment_df.columns = [f"{g}_enrichment" for g in genes]

    print(f'\n{summary_df=}\n')
    print(f'\n{enrichment_df=}\n')
    
    # Join group means with enrichment_df to get the cell type column in the same order
    summary_df = summary_df.join(enrichment_df, how="inner")

    print(f'\n{summary_df=}\n')

    # Ensure consistent column order
    if args.metric == 'mean':
        ordered_cols = genes
    elif args.metric == 'enrichment':
        ordered_cols = [f"{g}_enrichment" for g in genes]
    else:
        raise ValueError(f"Invalid metric: {args.metric}. Must be 'mean' or 'enrichment'.")
    summary_df = summary_df[ordered_cols]

    print(f'\n{ordered_cols=}\n')
    print(f'\n{summary_df=}\n')

    # Sort by appropriate enrichment column
    print(f"\n[bold cyan]Mean expression and enrichment for the specified cell type {args.cell_type}:[/bold cyan]\n")
    cell_type_summary_df = summary_df.loc[[args.cell_type]]
    print(cell_type_summary_df)

    # Save the results for the specified cell type
    if args.output:
        default_output_path = input_path.parent / f"{input_path.stem}_{args.column}_{args.cell_type}_marker_enrichment.csv"
        output_path = Path(args.output) if args.output else default_output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cell_type_summary_df = cell_type_summary_df.round(6) # Only use 6 decimal places for saving
        cell_type_summary_df.to_csv(output_path)
        print(f"\n[green]Saved enrichment results to:[/green] {output_path}\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()
