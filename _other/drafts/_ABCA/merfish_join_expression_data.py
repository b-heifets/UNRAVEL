#!/usr/bin/env python3

"""
Use ``./merfish_join_expression_data.py`` from UNRAVEL to join [filtered] cell metadata with MERFISH expression data from the Allen Brain Cell Atlas.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/merfish_tutorial_part_2b.html

Output:
    - A CSV file with the joined data (input_<gene>_expression.csv)

Usage:
------
    ./merfish_join_expression_data.py -i path/filtered_cells.csv -b path/base_dir -g gene -gb groupby [-v]

"""

import anndata
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import SimpleITK as sitk
from pathlib import Path
from rich import print
from rich.traceback import install

import unravel.abca.merfish as mf
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)
    reqs.add_argument('-i', '--input', help='path/filtered_cells.csv', required=True, action=SM)
    reqs.add_argument('-g', '--gene', help='Gene to analyze', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-im', '--imputed', help='Use imputed expression data. Default: False', action='store_true', default=False)

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

    # Load the filtered cell metadata
    cell_df = pd.read_csv(args.input, dtype={'cell_label': str})

    # Load the expression data for all genes (if the gene is in the dataset) 
    adata = mf.load_expression_data(download_base, args.gene, imputed=args.imputed)

    # Filter expression data for the specified gene
    asubset, gf = mf.filter_expression_data(adata, args.gene)

    # Create a dataframe with the expression data for the specified gene
    gdata = asubset[:, gf.index].to_df()  # Extract expression data for the gene
    
    gdata.columns = gf.gene_symbol  # Set the column names to the gene symbols
    
    # exp_df = cell_df.join(gdata)  # Join the cell metadata with the expression data
    exp_df = cell_df.set_index('cell_label').join(gdata, how='left').reset_index()

    # Save the joined data
    if args.imputed:
        exp_df.to_csv(f"{Path(args.input).stem}_{args.gene}_imputed_expression.csv", index=False)
        print(f"\n    Saved the joined data to {Path(args.input).stem}_{args.gene}_imputed_expression.csv\n")
    else:
        exp_df.to_csv(f"{Path(args.input).stem}_{args.gene}_expression.csv", index=False)
        print(f"\n    Saved the joined data to {Path(args.input).stem}_{args.gene}_expression.csv\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()