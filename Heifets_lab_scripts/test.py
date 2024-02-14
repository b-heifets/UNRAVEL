#!/usr/bin/env python3

import argparse
import concurrent.futures
import cc3d
import os
import numpy as np
from pathlib import Path
import pandas as pd
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from to_native5 import warp_to_native
from unravel_config import Configuration 
from unravel_img_io import load_3D_img, load_image_metadata_from_txt, load_nii_subset, resolve_path
from unravel_img_tools import cluster_IDs
from unravel_utils import print_cmd_and_times, initialize_progress_bar, get_samples, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(description='Warps cluster index from atlas space to tissue space, crops clusters and applies segmentation mask', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? folders', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern (sample??) for dirs to process. Else: use cwd', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)

    # Key args
    parser.add_argument('-m', '--moving_img', help='REQUIRED: path/*_rev_cluster_index.nii.gz to warp from atlas space', required=True, action=SM)
    parser.add_argument('-s', '--seg', help='REQUIRED: Dir name for segmentation image (e.g., cfos_seg_ilastik_1) or rel_path/seg_img.nii.gz', required=True, action=SM)
    parser.add_argument('-c', '--clusters', help='Clusters to process: all or list of clusters (e.g., 1 3 4). Default: all', nargs='*', default='all', action=SM)
    parser.add_argument('-de', '--density', help='Density to measure: cell_density (default) or label_density', default='cell_density', choices=['cell_density', 'label_density'], action=SM)
    parser.add_argument('-o', '--output', help='rel_path/clusters_info.csv (Default: clusters/<cluster_index_dir>/cluster_data.csv)', default=None, action=SM)

    # Optional warp_to_native() args
    parser.add_argument('-n', '--native_idx', help='Load/save native cluster index from/to rel_path/native_image.zarr (fast) or rel_path/native_image.nii.gz if provided', default=None, action=SM)
    parser.add_argument('-f', '--fixed_img', help='path/fixed_image.nii.gz. Default: reg_final/clar_downsample_res25um.nii.gz', default="reg_final/clar_downsample_res25um.nii.gz", action=SM)
    parser.add_argument('-i', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor [default], genericLabel [slow])', default="nearestNeighbor", action=SM)
    parser.add_argument('-t', '--transforms', help="Name of dir w/ transforms. Default: clar_allen_reg", default="clar_allen_reg", action=SM)
    parser.add_argument('-rp', '--reg_o_prefix', help='Registration output prefix. Default: allen_clar_ants', default='allen_clar_ants', action=SM)
    parser.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    parser.add_argument('-fr', '--fixed_res', help='Resolution of the fixed image. Default: 25', default='25',type=int, action=SM)
    parser.add_argument('-md', '--metadata', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order for scaling to full res. Default: 0 (nearest-neighbor)', default='0',type=int, action=SM)
    parser.add_argument('-l', '--legacy', help='Mode for backward compatibility (accounts for raw to nii reorienting)', action='store_true', default=False)

    # Optional arg for count_cells()
    parser.add_argument('-cc', '--connect', help='Connected component connectivity (6, 18, or 26). Default: 6', type=int, default=6, metavar='')

    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Run from a sample?? folder.

Example usage:     validate_clusters.py -m <path/rev_cluster_index_to_warp_from_atlas_space.nii.gz> -s cfos_seg_ilastik_1 -v

cluster_index_dir = Path(args.moving_img).name w/o "_rev_cluster_index" and ".nii.gz"

Outputs: ./sample??/clusters/<cluster_index_dir>/outer_bounds.txt, ./sample??/clusters/<cluster_index_dir>/<args.density>_data.csv

For -s, if a dir name is provided, the script will load ./sample??/seg_dir/sample??_seg_dir.nii.gz. 
If a relative path is provided, the script will load the image at the specified path.

Next script: cluster_cell_counts.py"""
    return parser.parse_args()


# TODO: QC. Aggregate .csv results for all samples if args.exp_dirs, script to load image subset.
# TODO: Make config file for defaults like: reg_final/clar_downsample_res25um.nii.gz.




def main():

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample_path in samples:
            
            metadata_path = resolve_path(sample_path, args.metadata)
            print(f'\n{metadata_path=}\n')
     
            # Load image metadata from .txt
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(metadata_path)
            if xy_res is None or z_res is None: 
                print("    [red bold]./sample??/parameters/metadata.txt missing. cd to sample?? dir and run: metadata.py")


            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()