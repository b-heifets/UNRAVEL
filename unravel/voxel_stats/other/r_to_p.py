#!/usr/bin/env python3

"""
Converts correlation map to z-score, p value, and FDR p value maps.

Usage:
------
    path/r_to_p.py -i sample01_cfos_correlation_map.nii.gz -x 25 -z 25 -v

Outputs: 
    - <image>_z_score_map.nii.gz
    - <image>_p_value_map.nii.gz
    - <image>_p_value_map_fdr_corrected.nii.gz
"""

import argparse
from pathlib import Path
import numpy as np
from rich import print
from rich.traceback import install
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_nii
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='[path/]image.nii.gz', required=True, action=SM)
    parser.add_argument('-x', '--xy_res', help='x/y voxel size in microns. Default: get via metadata', default=None, type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='z voxel size in microns. Default: get via metadata', default=None, type=float, action=SM)
    parser.add_argument('-a', '--alpha', help='FDR alpha. Default: 0.05', default=0.05, type=float, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()


@print_func_name_args_times()
def r_to_z(correlation_map):
    """Convert a Pearson correlation map (ndarray) to a Z-score map (ndarray) using Fisher's Z-transformation via np.arctanh"""
    # Adjust values slightly (e.g., in the seed region) if they are exactly 1 or -1 to avoid divide by zero error
    max_value = 1 - 1e-10  # Adjust 1e-10 to a suitable tolerance value
    adjusted_correlation_map = np.clip(correlation_map, -max_value, max_value)
    return np.arctanh(adjusted_correlation_map) # Fast equivalent to Fisher's Z-transformation: 0.5 * np.log((1 + adjusted_correlation_map) / (1 - adjusted_correlation_map))

@print_func_name_args_times()
def z_to_p(z_map):
    """Convert a Z-score map (ndarray) to a two-tailed p-value map (ndarray)"""
    return norm.sf(abs(z_map)) * 2 #https://www.geeksforgeeks.org/how-to-find-a-p-value-from-a-z-score-in-python/


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load Pearson correlation map
    if args.xy_res is None or args.z_res is None:
        img, xy_res, z_res = load_3D_img(args.input, return_res=True)
    else:
        img = load_3D_img(args.input)
        xy_res, z_res = args.xy_res, args.z_res

    correlation_map = load_3D_img(args.input)

    # Apply Fisher Z-transformation to convert to z-score map
    z_map = r_to_z(correlation_map)

    # Convert z-score map to p-value map
    p_map = z_to_p(z_map)

    # Invert P value map for visualization
    inv_p_map = 1 - p_map

    # Apply multiple comparisons correction (False Discovery Rate, FDR)
    alpha_level = 0.05  # Set your desired alpha level
    _, p_map_fdr_corrected, _, _ = multipletests(p_map.flatten(), alpha=alpha_level, method='fdr_bh')
    p_map_fdr_corrected = p_map_fdr_corrected.reshape(p_map.shape)

    # Invert FDR corrected P value map for visualization
    inv_p_map_fdr_corrected = 1 - p_map_fdr_corrected

    # Save the Z-score map and P-value maps
    output_prefix = str(Path(args.input).resolve()).replace(".nii.gz", "")

    save_as_nii(z_map, f"{output_prefix}_z_score_map.nii.gz", xy_res, z_res, data_type='float32')
    save_as_nii(inv_p_map, f"{output_prefix}_1-p_value_map.nii.gz", xy_res, z_res, data_type='float32')
    save_as_nii(inv_p_map_fdr_corrected, f"{output_prefix}_1-p_value_map_fdr_corrected.nii.gz", xy_res, z_res, data_type='float32')
    print("\n    Z-score map, P-value map, and FDR-corrected P-value map saved.\n")
    
    verbose_end_msg()


if __name__ == '__main__':
    main()