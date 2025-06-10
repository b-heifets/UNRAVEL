#!/usr/bin/env python3

"""
Use ``abca_scRNA-seq_filter`` or ``s_filter`` from UNRAVEL to filter ABCA scRNA-seq cells based on columns and values in the cell metadata.

Notes:
    - region_of_interest_acronym: ACA, AI, AUD, AUD-TEa-PERI-ECT, CB, CTXsp, ENT, HIP, HY, LSX, MB, MO-FRP, MOp, MY, OLF, P, PAL, PL-ILA-ORB, RHP, RSP, sAMY, SS-GU-VISC, SSp, STRd, STRv, TEa-PERI-ECT, TH, VIS, VIS-PTLp
    - mouse columns: cell_label, feature_matrix_label, region_of_interest_acronym, x, y, cluster_alias, neurotransmitter, class, subclass, supertype, cluster, ..., <genes>
    - human columns: cell_label, feature_matrix_label, region_of_interest_acronym, x, y, cluster_alias, neurotransmitter, supercluster, cluster, subcluster, ..., <genes>
    
Next steps:
    - ``abca_sunburst_expression``

Usage:
------
    abca_scRNA-seq_filter -b path/base_dir [--columns] [--values] [-o path/output.csv] [-v]
"""

import anndata
import numpy as np
import pandas as pd
import nibabel as nib
from pathlib import Path
from rich import print
from rich.traceback import install

import unravel.abca.merfish.merfish as mf
from unravel.abca.merfish.merfish_filter import filter_dataframe
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)
    reqs.add_argument('-i', '--input', help='Path to the scRNAseq CSV file', required=True, action=SM)
    reqs.add_argument('-c', '--columns', help='Columns to filter scRNSseq cell metadata by (e.g., region_of_interest_acronym)', nargs='*', action=SM)
    reqs.add_argument('-val', '--values', help='Values to filter scRNSseq cell metadata by (e.g., STRv).', nargs='*', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Output path for the filtered cell metadata', default=None, action=SM)
    opts.add_argument('-d', '--details', help='Add classification levels and colors to the filtered DataFrame.', default=False)

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

    # Load the cell metadata
    cell_df = pd.read_csv(args.input, dtype={'cell_label': str})

    print(f"\n    Initial cell metadata shape:\n    {cell_df.shape}")
    print(f'\n{cell_df}\n')

    # Filter the DataFrame
    filtered_df = filter_dataframe(cell_df, args.columns, args.values)
    print("\nFiltered cell metadata shape:", filtered_df.shape)
    print("\n                                             First row:")
    print(filtered_df.iloc[0])
    print("Filtered cell metadata:")
    print(f'\n{filtered_df}\n')

    if args.details:
        print("\nAdding classification levels and colors to the filtered DataFrame...")
        # Add the classification levels and the corresponding color.
        filtered_df_joined = mf.join_cluster_details(filtered_df, download_base)

        # Add the cluster colors
        filtered_df_joined = mf.join_cluster_colors(filtered_df_joined, download_base)
    else:
        print("\nSkipping classification levels and colors addition.")
        filtered_df_joined = filtered_df
        
    for column in args.columns:
        print(f"\nUnique values for {column}:")
        print(filtered_df_joined[column].unique())

    # Save the filtered DataFrame
    if args.output is not None:
        output_path = Path(args.output)
    else:
        output_path = str(Path(args.input).name).replace('.csv', '_filtered.csv')
    filtered_df_joined.to_csv(output_path)
    print(f"\nFiltered data saved to: {output_path}")

    verbose_end_msg()


if __name__ == '__main__':
    main()
