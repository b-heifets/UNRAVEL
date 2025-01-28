#!/usr/bin/env python3

"""
Use ``_other/drafts/correlation_comparison.py`` from UNRAVEL to calculate the difference between two Pearson correlations.
    
Usage:
------
    _other/drafts/correlation_comparison.py -r1 0.5 -r2 0.6 -n 1000 [-v]
"""

import numpy as np
from rich import print
from rich.traceback import install
from scipy.stats import norm

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-r1', '--r_group1', help='Pearson correlation value for group 1', required=True, type=float, action=SM)
    reqs.add_argument('-r2', '--r_group2', help='Pearson correlation value for group 2', required=True, type=float, action=SM)
    reqs.add_argument('-n', '--n_of_voxels', help='Number of voxels', required=True, type=int, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def fisher_r_to_z(r):
    """Convert Pearson correlation to Fisher z-score."""
    return 0.5 * np.log((1 + r) / (1 - r))

def compare_correlations(r1, r2, n_of_voxels):
    """Compare two Pearson correlations using Fisher's r-to-z transformation."""
    # Convert correlations to Fisher z-scores
    z1 = fisher_r_to_z(r1)
    z2 = fisher_r_to_z(r2)
    
    # Calculate standard error
    se = 1 / np.sqrt(n_of_voxels - 3) 
    
    # Calculate z for the difference between z1 and z2
    z_diff = (z1 - z2) / (se * np.sqrt(2))
    
    # Calculate two-tailed p-value
    p_value = 2 * (1 - norm.cdf(abs(z_diff)))  # Two-tailed test
    
    return z_diff, p_value


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    z_diff, p_value = compare_correlations(args.r_group1, args.r_group2, args.n_of_voxels)
    print(f"z-value: {z_diff}, p-value: {p_value}")

    verbose_end_msg()

if __name__ == '__main__':
    main()