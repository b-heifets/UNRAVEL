#!/usr/bin/env python3

"""
Use ``parquet_unique_intensities.py`` from UNRAVEL to load a column from a parquet file and print the unique intensities.

Usage:
------
    parquet_unique_intensities -i path/to/parquet -c column_name [-s] [-min min_size] [-v]
"""

import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.img_tools import label_IDs
from unravel.core.img_io import load_nii
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Output parquet file path.', required=True, action=SM)
    reqs.add_argument('-c', '--col', help='Column name for the intensities.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-s', '--print_sizes', help='Print label IDs and sizes. Default: False', default=False, action='store_true')
    opts.add_argument('-min', '--min_size', help='Min label size in voxels (Default: 1)', default=1, action=SM, type=int)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    df = pd.read_parquet(args.input, engine="pyarrow", columns=[args.col])

    # Convert to ndarray
    ndarray = df[args.col].to_numpy()

    # Get unique intensities and their counts
    if args.gt_zero:
        unique_intensities, counts = np.unique(ndarray[ndarray > 0], return_counts=True)
    else:
        unique_intensities, counts = np.unique(ndarray, return_counts=True)

    # Filter clusters based on size
    clusters_above_minextent = [intensity for intensity, count in zip(unique_intensities, counts) if count >= args.min_size]
    
    # Print cluster IDs
    if args.print_sizes:
        print(f"\nID,Size")
    for idx, cluster_id in enumerate(clusters_above_minextent):
        if args.print_sizes:
            print(f"{int(cluster_id)},{counts[idx]}")
        else:
            print(int(cluster_id), end=' ')
    print()

    verbose_end_msg()


if __name__ == '__main__':
    main()