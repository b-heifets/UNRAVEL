#!/usr/bin/env python3

"""
Use ``cstats_fdr_range`` (``fr``) from UNRAVEL to output a list of FDR q values that yeild clusters.

Inputs: 
    - p value map (e.g., *vox_p_*stat*.nii.gz from vstats)

Next command:
    - ``cstats_fdr`` to correct for multiple comparisons (use the q values from ``cstats_fdr_range``).

Usage:
------
    cstats_fdr_range -i path/vox_p_tstat1.nii.gz -mas path/mask.nii.gz [-q 0.00001 0.00005 0.0001 0.0005 0.001 0.005 0.01 0.05 0.1 0.15 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 0.95 0.99 0.999 0.9999] [-th 22] [-v]
"""

import concurrent.futures
import subprocess
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    q_values_default = [0.00001, 0.00005, 0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 0.999, 0.9999]

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/p_value_map.nii.gz', required=True, action=SM)
    reqs.add_argument('-mas', '--mask', help='path/mask.nii.gz', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-q', '--q_values', help='Space-separated list of q values. Default: a list from 0.00001 to 0.9999 is used.', nargs='*', default=q_values_default, type=float, action=SM)
    opts.add_argument('-th', '--threads', help='Number of threads. Default: 22', default=22, type=int, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Sometimes different q values yield the same p value threshold. Don't repeat q values with the same p value threshold in the output.

def smart_float_format(value, max_decimals=9):

    """Format float with up to `max_decimals` places, but strip unnecessary trailing zeros."""
    formatted = f"{value:.{max_decimals}f}"  # Format with maximum decimal places
    return formatted.rstrip('0').rstrip('.') if '.' in formatted else formatted

def fdr_range(input_path, mask_path, q_value):
    """Perform FDR correction on the input p value map using a mask.
    
    Args:
        - input_path (str): the path to the p value map
        - mask_path (str): the path to the mask
        - q_value (float): the q value for FDR correction

    """

    fdr_command = [
        'fdr', 
        '-i', str(input_path), 
        '--oneminusp', 
        '-m', str(mask_path), 
        '-q', str(q_value),
    ]

    result = subprocess.run(fdr_command, capture_output=True, text=True)    
    if result.returncode != 0:
        raise Exception(f"Error in FDR correction: {result.stderr}")

    # Extract the probability threshold from the output
    probability_threshold = result.stdout.strip().split()[-1]
    probability_threshold_float = float(probability_threshold)

    return q_value, probability_threshold_float

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
    
    # Initialize ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
        # Submit tasks to the executor for each q_value
        futures = [executor.submit(fdr_range, args.input, args.mask, q_value) for q_value in args.q_values]
        
        q_values_resulting_in_clusters = []
        # Process results as they complete
        for future in concurrent.futures.as_completed(futures):
            q_value, probability_threshold = future.result()
            if 0 < probability_threshold < 0.05:
                q_values_resulting_in_clusters.append(q_value)

    # Sort q_values numerically
    q_values_resulting_in_clusters.sort()

    # Convert the sorted list to a string and print
    q_values_resulting_in_clusters_str = ' '.join([smart_float_format(q) for q in q_values_resulting_in_clusters])
    print(f'\n{q_values_resulting_in_clusters_str}\n')

    verbose_end_msg()


if __name__ == '__main__':
    main()