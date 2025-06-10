#!/usr/bin/env python3

"""
Use ``./RNAseq_join_expression_data.py`` from UNRAVEL to join cell metadata with scRNA-seq expression data from the Allen Brain Cell Atlas.

Prereqs:
    - RNAseq_expression.py script to generate the input expression data.
    - Cell metadata from the Allen Brain Cell Atlas (use ``abca_cache`` to download).

Output:
    - A CSV file with the joined data (<input>_joined_expression.csv)

Usage:
------
    ./RNAseq_join_expression_data.py -i path/filtered_cells.csv -b path/base_dir -s species [-v]

"""

import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from _other.drafts._ABCA.RNAseq_expression import load_RNAseq_cell_metadata
import unravel.abca.merfish.merfish as mf
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)
    reqs.add_argument('-i', '--input', help='path/RNAseq_expression.csv', required=True, action=SM)
    reqs.add_argument('-s', '--species', help='Species to analyze (e.g., "mouse" or "human")', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Output path for the joined cell metadata and expression data.', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Move cell metadata loading, classification, and color joining to RNAseq_expression.py or consolidate in a common module.

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    cell_df = load_RNAseq_cell_metadata(download_base, species=args.species)

    # Classify cells based on their metadata
    cell_df = mf.join_cluster_details(cell_df, download_base, args.species)  # This could be moved to the RNAseq_expression.py script

    # Add color info
    cell_df = mf.join_cluster_colors(cell_df, download_base, args.species)

    # Load the input expression data (from RNAseq_expression.py)
    exp_df = pd.read_csv(args.input, dtype={'cell_label': str})
    exp_df = exp_df.set_index('cell_label')
    exp_cols = exp_df.columns.tolist()

    # Join the expression data with the cell metadata
    exp_df = exp_df.join(cell_df, on='cell_label', how='left')

    # Move the exp_cols to the end of the DataFrame
    exp_df = exp_df[[col for col in exp_df.columns if col not in exp_cols] + exp_cols]

    # Save the joined data
    if args.output is not None:
        output_path = Path(args.output)
    else:
        output_path = Path(str(args.input).replace('.csv', '_w_cells.csv'))
    exp_df.to_csv(output_path, index=False)
    print(f"\n    Saved the joined data to {output_path}\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()