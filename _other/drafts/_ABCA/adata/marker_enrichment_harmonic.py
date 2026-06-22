#!/usr/bin/env python3

"""
Use ``marker_enrichment_harmonic`` from UNRAVEL to load a scRNA-seq expression CSV file and calculate marker gene enrichment.

Overview:
    - Calculates mean expression per gene and cell type.
    - Computes enrichment = (mean expression in cell type) / (mean expression overall).
    - Uses the *harmonic mean* to combine enrichments across multiple genes,
      ensuring that high enrichment in one gene cannot dominate the result unless
      all genes are consistently high.

Interpretation:
    - A high harmonic mean enrichment indicates co-expression across all markers.
    - A low value indicates that one or more markers are not enriched in that cell type.

Reference:
    - Markers for each mouse cell type are available in Supplementary Table 7 from
      Yao et al. (2023), Nature. https://doi.org/10.1038/s41586-023-06812-z

Usage:
------
    ./marker_enrichment_harmonic.py -i path/input.csv -g Gene1 Gene2 -c column_name [-o path/output.csv] [-s species] [-v]
"""

from pathlib import Path
from typing import List
import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.allen_institute.abca.merfish.merfish_check_genes import normalize_gene_names
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path to the input CSV file.', required=True, action=SM)
    reqs.add_argument('-g', '--genes', help='Gene(s) to analyze (e.g., Drd1 or Drd1 Drd2).', required=True, nargs='*', action=SM)
    reqs.add_argument('-c', '--column', help='Cell type column to calculate enrichment for (i.e., neurotransmitter, class, subclass, supertype, cluster, supercluster, subcluster).', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Path to output CSV file.', default=None, action=SM)
    opts.add_argument('-s', '--species', help='Species to use (human or mouse). Default: mouse', default='mouse', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the input CSV
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

    # Calculate mean expression per cell type and enrichment
    summary_df = df.groupby(args.column).mean(numeric_only=True)
    overall_means = df.mean(numeric_only=True)
    enrichment_df = summary_df[genes] / overall_means[genes]
    enrichment_df.columns = [f"{g}_enrichment" for g in genes]
    enrichment_df = enrichment_df.reset_index()

    enrichment_cols = [f"{g}_enrichment" for g in genes]

    # Combine enrichments using the harmonic mean if multiple genes are given
    if len(genes) > 1:
        eps = 1e-6  # avoid division by zero
        # Optional normalization step per gene (so dynamic ranges don’t dominate)
        enrichment_norm = enrichment_df[enrichment_cols] / enrichment_df[enrichment_cols].max() # Normalize to [0,1]

        # Harmonic mean penalizes imbalance across genes
        enrichment_df["harmonic_mean_enrichment"] = len(genes) / (
            (1.0 / (enrichment_norm + eps)).sum(axis=1)
        )
        sort_col = "harmonic_mean_enrichment"
    else:
        sort_col = enrichment_cols[0]

    # Merge and reorder columns
    enrichment_df.set_index(args.column, inplace=True)
    summary_df = summary_df.join(enrichment_df, on=args.column, how='inner')
    ordered_cols = genes + enrichment_cols
    if "harmonic_mean_enrichment" in enrichment_df.columns:
        ordered_cols.append("harmonic_mean_enrichment")
    summary_df = summary_df[ordered_cols]

    # Sort and print results
    print(f"\n[bold cyan]Mean expression and enrichment for each cell type sorted by {sort_col}:[/bold cyan]\n")
    summary_df = summary_df.sort_values(by=sort_col, ascending=False)
    print(summary_df)

    # Save results
    if args.output:
        default_output_path = input_path.parent / f"{input_path.stem}_{args.column}_harmonic_enrichment.csv"
        output_path = Path(args.output) if args.output else default_output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        summary_df.round(6).to_csv(output_path, index=True)
        print(f"\n[green]Saved enrichment results to:[/green] {output_path}\n")

    # Display average values for context
    averages_df = summary_df.select_dtypes(include=[np.number]).mean().to_frame().T
    print(f"\n[bold green]Average values for all numeric columns:[/bold green]\n")
    print(averages_df)

    verbose_end_msg()


if __name__ == '__main__':
    main()
