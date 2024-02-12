#!/usr/bin/env python3

import argparse
import concurrent.futures #youtube.com/watch?v=fKl2JW_qrso
import numpy as np
from pathlib import Path
import pandas as pd
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from to_native5 import warp_to_native
from unravel_config import Configuration 
from unravel_img_io import load_3D_img, load_image_metadata_from_txt, resolve_relative_path
from unravel_img_tools import cluster_IDs
from unravel_utils import print_cmd_and_times, initialize_progress_bar, get_samples, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(description='Warps cluster index from atlas space to tissue space, crops clusters and applies segmentation mask', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? folders', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern (sample??) for dirs to process. Else: use cwd', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dirs to process. Overrides --pattern', nargs='*', default=None, action=SM)

    # Key args
    parser.add_argument('-m', '--moving_img', help='REQUIRED: path/*_rev_cluster_index.nii.gz to warp from atlas space', required=True, action=SM)
    parser.add_argument('-s', '--seg', help='REQUIRED: Dir name for segmentation image (e.g., cfos_seg_ilastik_1) or rel_path/seg_img', required=True, action=SM)
    parser.add_argument('-c', '--clusters', help='Clusters to process: all or list of clusters (e.g., 1 3 4). Default: all', nargs='*', default='all', action=SM)
    parser.add_argument('-o', '--output', help='rel_path/clusters_info.csv (Default: clusters/<cluster_index_dir>/cluster_data.csv)', default=None, action=SM)

    # Optional warp_to_native() args
    parser.add_argument('-n', '--native_idx', help='Load/save native cluster index from/to rel_path/native_image.zarr (fast) or rel_path/native_image.nii.gz if provided', default=None, action=SM)
    parser.add_argument('-f', '--fixed_img', help='path/fixed_image.nii.gz. Default: reg_final/clar_downsample_res25um.nii.gz', default="reg_final/clar_downsample_res25um.nii.gz", action=SM)
    parser.add_argument('-i', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor [default], genericLabel, linear)', default="nearestNeighbor", action=SM)
    parser.add_argument('-t', '--transforms', help="Name of dir w/ transforms. Default: clar_allen_reg", default="clar_allen_reg", action=SM)
    parser.add_argument('-rp', '--reg_o_prefix', help='Registration output prefix. Default: allen_clar_ants', default='allen_clar_ants', action=SM)
    parser.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    parser.add_argument('-fr', '--fixed_res', help='Resolution of the fixed image. Default: 25', default='25',type=int, action=SM)
    parser.add_argument('-md', '--metadata', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order for scaling to full res. Default: 0 (nearest-neighbor)', default='0',type=int, action=SM)
    parser.add_argument('-l', '--legacy', help='Mode for backward compatibility (accounts for raw to nii reorienting)', action='store_true', default=False)

    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Run from a sample?? folder.

Example usage:     native_clusters2.py -m <path/rev_cluster_index_to_warp_from_atlas_space.nii.gz> -s cfos_seg_ilastik_1 -v

Outputs: ./sample??/clusters/<cluster_index_dir>/outer_bounds.txt, ./sample??/clusters/<cluster_index_dir>/cluster_data.csv

For -s, if a dir name is provided, the script will load ./sample??/seg_dir/sample??_seg_dir.nii.gz. 
If a relative path is provided, the script will load the image at the specified path.

Next script: cluster_cell_counts.py"""
    return parser.parse_args()


# TODO: Make config file for defaults like: reg_final/clar_downsample_res25um.nii.gz. If still slow, consider loading image subsets corresponding to clusters. could use resolve_relative_path to allow for relative paths with glob patterns


@print_func_name_args_times()
def native_clusters(c, native_cluster_index, xy_res, z_res, seg_img):
    """For each cluster, crop native_cluster_index, mask it, measure volume, crop seg_cropped, and zero out voxels outside of clusters."""

    # Get bounding box for each cluster
    index = np.where(native_cluster_index == c) # 1D arrays of indices of elements == i for each axis
    xmin = int(min(index[0]))
    xmax = int(max(index[0])+1)
    ymin = int(min(index[1]))
    ymax = int(max(index[1])+1)
    zmin = int(min(index[2])) 
    zmax = int(max(index[2])+1)

    # Crop native_cluster_index for each cluster using the bounding box
    cropped_cluster = native_cluster_index[xmin:xmax, ymin:ymax, zmin:zmax]

    # Mask clusters
    cropped_cluster[cropped_cluster != c] = 0

    # Measure cluster volume
    volume_in_cubic_mm = ((xy_res**2) * z_res) * int(np.count_nonzero(cropped_cluster)) / 1000000000

    # Crop the segmentation image for each cluster using the bounding box
    cropped_seg = seg_img[xmin:xmax, ymin:ymax, zmin:zmax]

    # Zero out segmented voxels outside of clusters
    cropped_seg[cropped_cluster == 0] = 0

    return c, volume_in_cubic_mm, xmin, xmax, ymin, ymax, zmin, zmax, cropped_seg


def main():

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample_path in samples:
            
            # Define final output and check if it exists
            cluster_index_dir = Path(args.moving_img).parent.name
            if args.output:
                output_path = resolve_relative_path(sample_path, args.output)
            else: 
                output_path = resolve_relative_path(sample_path, Path("clusters", cluster_index_dir, "cluster_data.csv"), make_parents=True)
            if output_path.exists():
                print(f"\n\n    {output_path} already exists. Skipping.\n")
                return
            
            # Use lower bit-depth possible for cluster index
            rev_cluster_index = load_3D_img(args.moving_img)
            if rev_cluster_index.max() < 256:
                d_type = "uint8"
            elif rev_cluster_index.max() < 65536:
                d_type = "uint16"
            
            # Load cluster index and convert to ndarray 
            if Path(args.native_idx).exists():
                native_cluster_index = load_3D_img(resolve_relative_path(sample_path, args.native_idx))
            else:
                native_cluster_index = warp_to_native(args.moving_img, args.fixed_img, args.transforms, args.reg_o_prefix, args.reg_res, args.fixed_res, args.interpol, args.metadata, args.legacy, args.zoom_order, d_type, output=args.native_idx)
            
            # Get clusters to process
            if args.clusters == "all":
                clusters = cluster_IDs(rev_cluster_index)
            else:
                clusters = [args.clusters]
            clusters = [int(cluster) for cluster in clusters]

            # Load image metadata from .txt
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(args.metadata)
            if xy_res is None or z_res is None: 
                print("    [red bold]./sample??/parameters/metadata.txt missing. cd to sample?? dir and run: metadata.py")

            # Load cell segmentation .nii.gz
            if Path(sample_path, args.seg).is_dir():
                seg_img = load_3D_img(Path(sample_path, args.seg, f"{sample_path.name}_{args.seg}.nii.gz"))
            else:
                seg_img = load_3D_img(resolve_relative_path(sample_path, args.seg))

            # For each cluster, crop native_cluster_index, mask it, measure volume, crop seg_cropped, and zero out voxels outside of clusters.
            for c in clusters:
                c, volume_in_cubic_mm, xmin, xmax, ymin, ymax, zmin, zmax = native_clusters(c, native_cluster_index, xy_res, z_res, seg_img)

            # For each cluster, crop native_cluster_index, mask it, measure volume, crop seg_cropped, and zero out voxels outside of clusters.
                
            # Count cells (objects) in each cluster ##############


            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()