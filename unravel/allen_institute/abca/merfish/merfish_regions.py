#!/usr/bin/env python3

"""
Use ``abca_merfish_regions`` or ``mfr`` from UNRAVEL to list unique region names from the Allen Brain Cell Atlas MERFISH parcellation annotations.

Note:
    - This is useful for finding region acronyms that are relevant to MERFISH data analysis.
    - For other MERFISH scripts, parcellation_ is prepended to the region-related columns (e.g., parcellation_substructure). 

Usage:
------
    abca_merfish_regions -b path/base_dir [-c column] [-o path/output.csv] [-v]

Usage with piping to grep:
--------------------------
    abca_merfish_regions -b path/base_dir | grep BLA
"""

import anndata
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import SimpleITK as sitk
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-c', '--column', help='Column: organ, category, division, structure, substructure. Default: substructure', default='substructure', action=SM)
    opts.add_argument('-o', '--output', help='Path to save .csv file. Default: None', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Make base cwd by default. Consider intergrating with the cache tool from Allen. 
# TODO: Offload the lists of genes to CSVs
# TODO: Offload common functions to allen_utils.py
# TODO: Add option to download the data if not present
# TODO: Rename functions from cluster details to cell details etc



@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    parcellation_annotation_path = download_base / 'metadata/Allen-CCF-2020/20230630/views/parcellation_to_parcellation_term_membership_acronym.csv'

    parcellation_annotation = pd.read_csv(parcellation_annotation_path, index_col=0)
    
    # Print unique values in the specified column
    unique_values = parcellation_annotation[args.column].unique()
    print(f"Unique values in column '{args.column}':\n{unique_values}\n")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        parcellation_annotation[args.column].to_csv(output_path, header=True)
        print(f"Saved unique values to {output_path}")

    verbose_end_msg()

if __name__ == '__main__':
    main()
