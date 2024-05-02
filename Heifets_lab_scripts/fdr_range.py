#!/usr/bin/env python3

import argparse
import subprocess
from rich import print
from rich.traceback import install

from argparse_utils import SM, SuppressMetavar
from unravel_utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Determine range of q values for FDR correction that yeilds clusters', formatter_class=SuppressMetavar)
    q_values_default = [0.00001, 0.00005, 0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 0.999, 0.9999]
    parser.add_argument('-i', '--input', help='path/p_value_map.nii.gz', required=True, action=SM)
    parser.add_argument('-mas', '--mask', help='path/mask.nii.gz', required=True, action=SM)
    parser.add_argument('-q', '--q_values', help='Space-separated list of q values. If omitted, a default list is used.', nargs='*', default=q_values_default, type=float, action=SM)
    parser.epilog = """
Usage: fdr_range.py -i path/vox_p_tstat1.nii.gz -mas path/mask.nii.gz -q 0.05 0.01 0.001

Inputs: 
    - p value map (e.g., *vox_p_*stat*.nii.gz from vstats.py)    

"""
    return parser.parse_args()

def smart_float_format(value, max_decimals=9):
    """Format float with up to `max_decimals` places, but strip unnecessary trailing zeros."""
    formatted = f"{value:.{max_decimals}f}"  # Format with maximum decimal places
    return formatted.rstrip('0').rstrip('.') if '.' in formatted else formatted

def fdr(input_path, mask_path, q_value):
    """Perform FDR correction on the input p value map using a mask.
    
    Args:
        - input_path (str): the path to the p value map
        - mask_path (str): the path to the mask
        - q_value (float): the q value for FDR correction

    """
    print('')

    fdr_command = [
        'fdr', 
        '-i', str(input_path), 
        '--oneminusp', 
        '-m', str(mask_path), 
        '-q', str(q_value),
    ]

    print(f'[bold]Running FDR correction with q value: {smart_float_format(q_value)}[/]')

    result = subprocess.run(fdr_command, capture_output=True, text=True)    
    if result.returncode != 0:
        raise Exception(f"Error in FDR correction: {result.stderr}")
    print(result.stdout)

    # Extract the probability threshold from the output
    probability_threshold = result.stdout.strip().split()[-1]
    try:
        probability_threshold_float = float(probability_threshold)
    except ValueError:
        raise ValueError(f"Failed to convert probability threshold to float: {probability_threshold}")

    return probability_threshold_float


def main():

    # FDR Correction
    q_values_resulting_in_clusters = []
    for q_value in args.q_values:
        probability_threshold = fdr(args.input, args.mask, q_value)
        if probability_threshold > 0 and probability_threshold < 0.05:
            q_values_resulting_in_clusters.append(q_value)
        if probability_threshold > 0.05:
            break

    # print the q values resulting in clusters as a space-separated list
    q_values_resulting_in_clusters_str = ' '.join([str(q) for q in q_values_resulting_in_clusters])
    print(f'\n[bold]Q values resulting in clusters:[/]\n{q_values_resulting_in_clusters_str}\n')


if __name__ == '__main__': 
    install()
    args = parse_args()
    print_cmd_and_times(main)()
