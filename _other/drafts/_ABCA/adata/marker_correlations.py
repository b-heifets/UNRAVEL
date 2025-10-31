#!/usr/bin/env python3
"""
Use ``marker_correlations`` from UNRAVEL to calculate correlations between marker genes across cell types for humans vs. mice.

Note:
    - The order of data must match between the two input files (e.g., same cell types in same order).
    - Pearson correlations are calculated per feature (e.g., gene) across all cell types.
    - Empirical p-values are computed via permutation testing (shuffling one dataset).
    - FDR correction is applied to the p-values using the Benjamini-Hochberg method.

Usage:
------
    ./marker_correlations.py -1 path/input_1.csv -2 path/input_2.csv [-o path/output.csv] [-v]
"""

import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install
from scipy.stats import pearsonr
from statsmodels.stats.multitest import multipletests

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-1', '--input_1', help='Path to the input CSV file.', required=True, action=SM)
    reqs.add_argument('-2', '--input_2', help='Path to the second input CSV file.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Path to output CSV file.', default=None, action=SM)

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
    input_path = Path(args.input_1)
    df_1 = pd.read_csv(input_path, index_col=0)

    print(f"\nInput DataFrame 1: {df_1}\n")

    input_path = Path(args.input_2)
    df_2 = pd.read_csv(input_path, index_col=0)
    print(f"\nInput DataFrame 2: {df_2}\n")

    # Calculate correlations
    mouse_matrix = df_1.values
    human_matrix = df_2.values

    n_perm = 10000
    rng = np.random.default_rng(42)
    results = []
    for i in range(mouse_matrix.shape[1]):
        x = mouse_matrix[:, i]
        y = human_matrix[:, i]

        # Observed correlation
        r, _ = pearsonr(x, y)

        # Null distribution (randomly shuffle y)
        perm_rs = [pearsonr(x, rng.permutation(y))[0] for _ in range(n_perm)]

        # One-tailed empirical p-value (positive correlations only)
        p = (np.sum(perm_rs >= r) + 1) / (n_perm + 1)

        results.append((i, r, p))

    # Convert to DataFrame and FDR-correct
    output_df = pd.DataFrame(results, columns=["feature_idx", "pearson", "p_empirical"])
    output_df["fdr_corrected_p"] = multipletests(output_df["p_empirical"], method="fdr_bh")[1]
    output_df.set_index("feature_idx", inplace=True)

    # Print the output DataFrame
    print(f'\n{output_df}\n')

    # Save
    default_output = input_path.parent / f"{input_path.stem}_correlations.csv"
    output_path = Path(args.output) if args.output else default_output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.round(6).to_csv(output_path, index=True)
    print(f"\n[green]Saved correlation values for {len(output_df)} cell types to:[/green] {output_path}")

    verbose_end_msg()

if __name__ == '__main__':
    main()
