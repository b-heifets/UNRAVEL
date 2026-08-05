#!/usr/bin/env python3

"""
Use ``abca_scRNAseq_join_gene`` from UNRAVEL to join cell metadata with expression data from the ABCA.

Prereqs:
    - ``abca_scRNAseq_expression`` to generate the input expression data for the specified genes.
    - Cell metadata from the Allen Brain Cell Atlas (use ``abca_cache`` to download).

Output:
    - A CSV file with the joined data (<input>_joined_expression.csv)

Usage:
------
    abca_scRNAseq_join_gene -i path/filtered_cells.csv -b path/base_dir -s species [-v]

"""

import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

import pandas as pd
from pathlib import Path
from unravel.allen_institute.abca.scRNA_seq.expression import join_cell_metadata
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


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)
    exp_df = pd.read_csv(args.input, dtype={'cell_label': str})
    joined_df = join_cell_metadata(exp_df, download_base, args.species)

    # Save the joined data with the cell_label column (index)
    if args.output is not None:
        output_path = Path(args.output)
    else:
        output_path = Path(str(args.input).replace('.csv', '_w_cells.csv'))
    joined_df.to_csv(output_path, index=True)
    print(f"\n    Saved the joined data to {output_path}\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()