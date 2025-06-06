#!/usr/bin/env python3

"""
Use ``./RNAseq_join_expression_data.py`` from UNRAVEL to join cell metadata with scRNA-seq expression data from the Allen Brain Cell Atlas.

Prereqs:
    - RNAseq_expression.py script to generate the input expression data.
    - Cell metadata from the Allen Brain Cell Atlas.

Usage:
------
    ./RNAseq_join_expression_data.py -i path/filtered_cells.csv -b path/base_dir -s species [-v]

"""

import anndata
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import SimpleITK as sitk
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

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    cell_df = load_RNAseq_cell_metadata(download_base, species=args.species)

    print(cell_df)

    # Load the input expression data (from RNAseq_expression.py)
    exp_df = pd.read_csv(args.input, dtype={'cell_label': str})

    print(exp_df)

    # Join the cell metadata with the expression data using the 'cell_label' column
    exp_df = cell_df.join(exp_df.set_index('cell_label'), how='left').reset_index()

    print(exp_df)

    # Save the joined data
    exp_df.to_csv(f"{Path(args.input).stem}_w_cells.csv", index=False)

    verbose_end_msg()

if __name__ == '__main__':
    main()