#!/usr/bin/env python3
"""
Use ``marker_summary`` from UNRAVEL to calculate mean or enrichment scRNA-seq values for multiple cell types.

Prereqs:
    - marker_summary.py to generate enrichment values for specified genes.
    - ``edit_cols`` to keep only desired marker gene columns for a given cell type.

Inputs:
    - CSV output from marker_summary.py with columns representing marker genes for a given cell type.

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

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Path to output CSV file.', default=None, action=SM)
    opts.add_argument('-ct', '--cell_type', help="Cell type(s) to include. Default: all", nargs='*', default=['all'], action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the scRNA-seq data
    input_path = Path(args.input)
    df = pd.read_csv(input_path, index_col=0)

    print(f"\nInput DataFrame: {df}\n")

    # Optional normalization step per gene (to ~ evenly weight genes)
    norm_df = df / df.max() # Normalize to [0,1]

    print(f"\nNormalized DataFrame: {norm_df}\n")

    genes = df.columns.tolist()

    # Combine enrichments using the harmonic mean if multiple genes are given
    if len(genes) > 1:
        eps = 1e-6  # avoid division by zero

        # Harmonic mean penalizes imbalance across genes
        norm_df["harmonic_mean_enrichment"] = len(genes) / (
            (1.0 / (norm_df + eps)).sum(axis=1)
        )

    else:
        norm_df["harmonic_mean_enrichment"] = norm_df[genes[0]]

    output_df = norm_df[["harmonic_mean_enrichment"]]
    print(f"\nHarmonic Mean Enrichment DataFrame: {output_df}\n")

    # Save
    default_output = input_path.parent / f"{input_path.stem}_harmonic_enrichment.csv"
    output_path = Path(args.output) if args.output else default_output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.round(6).to_csv(output_path, index=True)
    print(f"\n[green]Saved harmonic enrichment values for {len(output_df)} cell types to:[/green] {output_path}")

    verbose_end_msg()

if __name__ == '__main__':
    main()
