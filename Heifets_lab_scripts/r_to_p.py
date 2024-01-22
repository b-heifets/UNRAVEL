#!/usr/bin/env python3

import argparse
from argparse import RawTextHelpFormatter
from pathlib import Path
import numpy as np
from unravel_config import Configuration
from rich import print
from rich.traceback import install
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests
from unravel_img_tools import load_3D_img, save_as_nii
from unravel_utils import print_cmd_and_times, print_func_name_args_times

def parse_args():
    parser = argparse.ArgumentParser(description='Converts correlation map to z-score, p value, and FDR p value maps', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-i', '--input', help='path/image.nii.gz', required=True, metavar='')
    parser.add_argument('-a', '--alpha', help='FDR alpha. Default: 0.05', default=0.05, type=float, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Outputs: path/z_score_map.nii.gz, path/p_value_map.nii.gz, path/p_value_map_fdr_corrected.nii.gz"""
    return parser.parse_args()


@print_func_name_args_times()
def r_to_z(correlation_map):
    """Convert a Pearson correlation map (ndarray) to a Z-score map (ndarray) using Fisher's Z-transformation via np.arctanh"""
    return np.arctanh(correlation_map) #https://stats.stackexchange.com/questions/109028/fishers-z-transform-in-python

@print_func_name_args_times()
def z_to_p(z_map):
    """Convert a Z-score map (ndarray) to a two-tailed p-value map (ndarray)"""
    return norm.sf(abs(z_map)) * 2 #https://www.geeksforgeeks.org/how-to-find-a-p-value-from-a-z-score-in-python/


def main():

    # Load Pearson correlation map
    correlation_map = load_3D_img(args.input)

    # Apply Fisher Z-transformation to convert to z-score map
    z_map = r_to_z(correlation_map)

    # Convert z-score map to p-value map
    p_map = z_to_p(z_map)

    # Apply multiple comparisons correction (False Discovery Rate, FDR)
    alpha_level = 0.05  # Set your desired alpha level
    _, p_map_fdr_corrected, _, _ = multipletests(p_map.flatten(), alpha=alpha_level, method='fdr_bh')
    p_map_fdr_corrected = p_map_fdr_corrected.reshape(p_map.shape)

    # Save the Z-score map and P-value maps
    output_prefix = str(Path(args.input).resolve()).replace(".nii.gz", "")

    save_as_nii(z_map, f"{output_prefix}_z_score_map.nii.gz")
    save_as_nii(p_map, f"{output_prefix}_p_value_map.nii.gz")
    save_as_nii(p_map_fdr_corrected, f"{output_prefix}_p_value_map_fdr_corrected.nii.gz")
    print("\n    Z-score map, P-value map, and FDR-corrected P-value map saved.\n")
    
    
if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()