#!/usr/bin/env python3

"""
Use ``cstats_find_incongruent`` from UNRAVEL if ``cstats_fdr`` was used to convert non-directional p value maps into directional cluster indices. This helps to find clusters where the direction of the mean intensity difference between groups does not match direction of the difference in cell/label density between groups.

Usage
-----
    cstats_find_incongruent -c tukey_results.csv -l groupA -g groupB
    
This is useful to find clusters where z-scoring introduces incongruencies between the mean intensity difference and the density difference.
    
For example, if group A has increased IF in region A and not B, z-scoring may decrease the relative intensity of region B. 
This decrease for region B for one group, may introduce a difference in the mean intensity between groups that is not reflected in the density difference.

Input csv: 
    ./_cluster_validation_info/tukey_results.csv  or ttest_results.csv from ``cstats``

Columns: 
    'cluster_ID', 'comparison', 'higher_mean_group', 'p-value', 'significance'

Output:
    Cluster IDs where the mean intensity difference does not match the density difference between groups A and B.
"""

from pathlib import Path
import pandas as pd
from glob import glob
from rich import print
from rich.traceback import install

from unravel.core.argparse_rich_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-c', '--csv_name', help='Name of the CSV file.', required=True, action=SM)
    reqs.add_argument('-l', '--lesser_group', help='Group with a lower mean for the comparison of interest.', required=True, action=SM)
    reqs.add_argument('-g', '--greater_group', help='Group with a higher mean for the comparison of interest.', required=True, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def find_incongruent_clusters(df, expected_lower_mean_group, expected_higher_mean_group):

    # Determine the comparison string (e.g. 'groupA vs groupB' in the 'comparison' column)
    comparison_str1 = f'{expected_lower_mean_group} vs {expected_higher_mean_group}'
    comparison_str2 = f'{expected_higher_mean_group} vs {expected_lower_mean_group}'

    # Filter data based on the comparison string
    filtered_df = df[
        (df['comparison'] == comparison_str1) |
        (df['comparison'] == comparison_str2)
    ]

    # Find clusters that are significant and incongruent with the prediction
    incongruent_clusters = filtered_df[
        (filtered_df['significance'] != 'n.s.') &
        (filtered_df['higher_mean_group'] != expected_higher_mean_group)
    ]['cluster_ID'].tolist()
    
    return incongruent_clusters

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    current_dir = Path.cwd()

    # Consctruct substring to find matching subdirs
    substring_str1 = f'{args.greater_group}_gt_{args.lesser_group}'
    substring_str2 = f'{args.lesser_group}_lt_{args.greater_group}'

    # Iterate over all subdirectories in the current working directory
    for subdir in [d for d in current_dir.iterdir() if d.is_dir() and (substring_str1 in d.name or substring_str2 in d.name)]:
        print(f"\nProcessing directory: [default bold]{subdir.name}[/]")

        df = pd.read_csv(subdir / "_valid_clusters_stats" / args.csv_name)
        incongruent_clusters = find_incongruent_clusters(df, args.lesser_group, args.greater_group)
        
        if incongruent_clusters:
            print(f'\n    CSV: {args.csv_name}')
            print(f"    Incongruent clusters: {incongruent_clusters}\n")
        else:
            print(f'    CSV: {args.csv_name}')
            print("    No incongruent clusters found.\n")

    verbose_end_msg()


if __name__ == '__main__':
    main()