#!/usr/bin/env python3

"""
Use ``cluster_validation`` from UNRAVEL to warp a cluster index from atlas space to tissue space, crop clusters, apply a segmentation mask, and quantify cell/label densities.

Usage:
------
    cluster_validation -e <experiment paths> -m <path/rev_cluster_index_to_warp_from_atlas_space.nii.gz> -s cfos_seg_ilastik_1 -v

cluster_index_dir = Path(args.moving_img).name w/o "_rev_cluster_index" and ".nii.gz"

Outputs:
    - ./sample??/clusters/<cluster_index_dir>/outer_bounds.txt
    - ./sample??/clusters/<cluster_index_dir>/<args.density>_data.csv

For -s, if a dir name is provided, the command will load ./sample??/seg_dir/sample??_seg_dir.nii.gz. 
If a relative path is provided, the command will load the image at the specified path.

Next command:
    ``cluster_summary``
"""


import argparse
import concurrent.futures
import cc3d
import numpy as np
import os
import pandas as pd
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.img_io import load_3D_img, load_image_metadata_from_txt, load_nii_subset, resolve_path
from unravel.core.img_tools import cluster_IDs
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples, print_func_name_args_times
from unravel.warp.to_native import to_native


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)

    # Key args
    parser.add_argument('-m', '--moving_img', help='path/*_rev_cluster_index.nii.gz to warp from atlas space', required=True, action=SM)
    parser.add_argument('-s', '--seg', help='rel_path/seg_img.nii.gz. 1st glob match processed', required=True, action=SM)
    parser.add_argument('-c', '--clusters', help='Clusters to process: all or list of clusters (e.g., 1 3 4). Default: all', nargs='*', default='all', action=SM)
    parser.add_argument('-de', '--density', help='Density to measure: cell_density (default) or label_density', default='cell_density', choices=['cell_density', 'label_density'], action=SM)
    parser.add_argument('-o', '--output', help='rel_path/clusters_info.csv (Default: clusters/<cluster_index_dir>/cluster_data.csv)', default=None, action=SM)

    # Optional to_native() args
    parser.add_argument('-n', '--native_idx', help='Load/save native cluster index from/to rel_path/native_image.zarr (fast) or rel_path/native_image.nii.gz if provided', default=None, action=SM)
    parser.add_argument('-fri', '--fixed_reg_in', help='Fixed input for registration (unravel.register.reg). Default: autofl_50um_masked_fixed_reg_input.nii.gz', default="autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)    
    parser.add_argument('-inp', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor [default], multiLabel [slow])', default="nearestNeighbor", action=SM)
    parser.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from unravel.register.reg (e.g., transforms). Default: reg_outputs", default="reg_outputs", action=SM)
    parser.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    parser.add_argument('-md', '--metadata', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order for scaling to full res. Default: 0 (nearest-neighbor)', default='0',type=int, action=SM)
    parser.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)

    # Optional arg for count_cells()
    parser.add_argument('-cc', '--connect', help='Connected component connectivity (6, 18, or 26). Default: 6', type=int, default=6, action=SM)

    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: QC. Aggregate .csv results for all samples if args.exp_dirs, script to load image subset.
# TODO: Make config file for defaults or a command_generator.py script
# TODO: Consider adding an option to quantify mean IF intensity in each cluster in segmented voxels. Also make a script for mean IF intensity in clusters in atlas space. 

@print_func_name_args_times()
def crop_outer_space(native_cluster_index, output_path):
    """Crop outer space around all clusters and save bounding box to .txt file (outer_bounds.txt) 
    Return cropped native_cluster_index, outer_xmin, outer_xmax, outer_ymin, outer_ymax, outer_zmin, outer_zmax"""
    
    # Create boolean arrays indicating presence of clusters along each axis
    presence_x = np.any(native_cluster_index, axis=(1, 2))
    presence_y = np.any(native_cluster_index, axis=(0, 2))
    presence_z = np.any(native_cluster_index, axis=(0, 1))
    
    # Use np.argmax on presence arrays to find first occurrence of clusters
    # For max, reverse the array, use np.argmax, and subtract from the length
    outer_xmin, outer_xmax = np.argmax(presence_x), len(presence_x) - np.argmax(presence_x[::-1])
    outer_ymin, outer_ymax = np.argmax(presence_y), len(presence_y) - np.argmax(presence_y[::-1])
    outer_zmin, outer_zmax = np.argmax(presence_z), len(presence_z) - np.argmax(presence_z[::-1])
    
    # Adjust the max bounds to include the last slice where the cluster is present
    outer_xmax += 1
    outer_ymax += 1
    outer_zmax += 1
    
    # Crop the native_cluster_index to the bounding box
    native_cluster_index_cropped = native_cluster_index[outer_xmin:outer_xmax, outer_ymin:outer_ymax, outer_zmin:outer_zmax]
    
    # Save the bounding box to a file
    with open(f"{output_path.parent}/outer_bounds.txt", "w") as file:
        file.write(f"{outer_xmin}:{outer_xmax}, {outer_ymin}:{outer_ymax}, {outer_zmin}:{outer_zmax}") 
    
    return native_cluster_index_cropped, outer_xmin, outer_xmax, outer_ymin, outer_ymax, outer_zmin, outer_zmax

def cluster_bbox(cluster_ID, native_cluster_index_cropped):
    """Get bounding box for the current cluster. Return cluster_ID, xmin, xmax, ymin, ymax, zmin, zmax."""
    cluster_mask = native_cluster_index_cropped == cluster_ID
    presence_x = np.any(cluster_mask, axis=(1, 2))
    presence_y = np.any(cluster_mask, axis=(0, 2))
    presence_z = np.any(cluster_mask, axis=(0, 1))

    xmin, xmax = np.argmax(presence_x), len(presence_x) - np.argmax(presence_x[::-1])
    ymin, ymax = np.argmax(presence_y), len(presence_y) - np.argmax(presence_y[::-1])
    zmin, zmax = np.argmax(presence_z), len(presence_z) - np.argmax(presence_z[::-1])

    return cluster_ID, xmin, xmax, ymin, ymax, zmin, zmax

@print_func_name_args_times()
def cluster_bbox_parallel(native_cluster_index_cropped, clusters):
    """Get bounding boxes for each cluster in parallel. Return list of results."""
    results = []
    num_cores = os.cpu_count() # This is good for CPU-bound tasks. Could try 2 * num_cores + 1 for io-bound tasks
    workers = min(num_cores, len(clusters))  
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_cluster = {executor.submit(cluster_bbox, cluster_ID, native_cluster_index_cropped): cluster_ID for cluster_ID in clusters}
        for future in concurrent.futures.as_completed(future_to_cluster):
            cluster_ID = future_to_cluster[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                print(f'Cluster {cluster_ID} generated an exception: {exc}')
    return results

def count_cells(seg_in_cluster, connectivity=6):
    """Count cells (objects) in each cluster using connected-components-3d
    Return the number of cells in the cluster."""

    # If the data is big-endian, convert it to little-endian
    if seg_in_cluster.dtype.byteorder == '>':
        seg_in_cluster = seg_in_cluster.byteswap().newbyteorder()
    seg_in_cluster = seg_in_cluster.astype(np.uint8)

    # Count the number of cells in the cluster
    labels_out, n = cc3d.connected_components(seg_in_cluster, connectivity=connectivity, out_dtype=np.uint32, return_N=True)

    return n

def density_in_cluster(cluster_data, native_cluster_index_cropped, seg_cropped, xy_res, z_res, connectivity=6, density='cell_count'):
    """Measure cell count or volume of segmented voxels in the current cluster.
    For cell densities, return: cluster_ID, cell_count, cluster_volume_in_cubic_mm, cell_density, xmin, xmax, ymin, ymax, zmin, zmax
    For label densities, return: cluster_ID, seg_volume_in_cubic_mm, cluster_volume_in_cubic_mm, label_density, xmin, xmax, ymin, ymax, zmin, zmax.
    """
    cluster_ID, xmin, xmax, ymin, ymax, zmin, zmax = cluster_data

    # Crop the cluster from the native cluster index
    cropped_cluster = native_cluster_index_cropped[xmin:xmax, ymin:ymax, zmin:zmax]

    # Crop the segmentation image for the current cluster
    seg_in_cluster = seg_cropped[xmin:xmax, ymin:ymax, zmin:zmax]

    # Zero out segmented voxels outside of the current cluster
    seg_in_cluster[cropped_cluster == 0] = 0

    # Measure cluster volume
    cluster_volume_in_cubic_mm = ((xy_res**2) * z_res) * np.count_nonzero(cropped_cluster) / 1e9

    # Count cells or measure the volume of segmented voxels
    if density == "cell_density":
        cell_count = count_cells(seg_in_cluster, connectivity=connectivity)
        cell_density = cell_count / cluster_volume_in_cubic_mm
        return cluster_ID, cell_count, cluster_volume_in_cubic_mm, cell_density, xmin, xmax, ymin, ymax, zmin, zmax
    else: 
        seg_volume_in_cubic_mm = ((xy_res**2) * z_res) * np.count_nonzero(seg_in_cluster) / 1e9
        label_density = seg_volume_in_cubic_mm / cluster_volume_in_cubic_mm * 100
        return cluster_ID, seg_volume_in_cubic_mm, cluster_volume_in_cubic_mm, label_density, xmin, xmax, ymin, ymax, zmin, zmax
    
@print_func_name_args_times()
def density_in_cluster_parallel(cluster_bbox_results, native_cluster_index_cropped, seg_cropped, xy_res, z_res, connectivity=6, density='cell_count'):
    """Measure cell count or volume of segmented voxels in each cluster in parallel. Return list of results."""
    results = []
    num_cores = os.cpu_count()
    workers = min(num_cores, len(cluster_bbox_results)) 
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_cluster = {executor.submit(density_in_cluster, cluster_data, native_cluster_index_cropped, seg_cropped, xy_res, z_res, connectivity, density): cluster_data[0] for cluster_data in cluster_bbox_results} # cluster_data[0] is the cluster_ID
        for future in concurrent.futures.as_completed(future_to_cluster):
            cluster_ID = future_to_cluster[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                print(f'Cluster {cluster_ID} generated an exception: {exc}')
    return results


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()
            
            # Define final output and check if it exists
            cluster_index_dir = str(Path(args.moving_img).name).replace(".nii.gz", "").replace("_rev_cluster_index_", "_")
            if args.output:
                output_path = resolve_path(sample_path, args.output)
            else: 
                output_path = resolve_path(sample_path, Path("clusters", cluster_index_dir, f"{args.density}_data.csv"), make_parents=True)
            if output_path and output_path.exists():
                print(f"\n\n    {output_path} already exists. Skipping.\n")
                continue
            
            # Use lower bit-depth possible for cluster index
            rev_cluster_index = load_3D_img(args.moving_img)

            # Define paths relative to sample?? folder 
            native_idx_path = resolve_path(sample_path, args.native_idx) if args.native_idx else None
            
            # Load cluster index and convert to ndarray 
            if args.native_idx and Path(args.native_idx).exists():
                native_cluster_index = load_3D_img(Path(args.native_idx).exists())
            else:
                fixed_reg_input = Path(sample_path, args.reg_outputs, args.fixed_reg_in) 
                if not fixed_reg_input.exists():
                    fixed_reg_input = sample_path / args.reg_outputs / "autofl_50um_fixed_reg_input.nii.gz"
                native_cluster_index = to_native(sample_path, args.reg_outputs, fixed_reg_input, args.moving_img, args.metadata, args.reg_res, args.miracl, args.zoom_order, args.interpol, output=native_idx_path)

            # Get clusters to process
            if args.clusters == "all":
                clusters = cluster_IDs(rev_cluster_index)
            else:
                clusters = args.clusters
            clusters = [int(cluster) for cluster in clusters]

            # Crop outer space around all clusters 
            native_cluster_index_cropped, outer_xmin, outer_xmax, outer_ymin, outer_ymax, outer_zmin, outer_zmax = crop_outer_space(native_cluster_index, output_path)

            # Load image metadata from .txt
            metadata_path = resolve_path(sample_path, args.metadata)
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(metadata_path)
            if xy_res is None or z_res is None: 
                print("    [red bold]./sample??/parameters/metadata.txt missing. cd to sample?? dir and run: io_metadata")

            # Get bounding boxes for each cluster in parallel
            cluster_bbox_data = cluster_bbox_parallel(native_cluster_index_cropped, clusters)

            # Load the segmentation image and crop it to the outer bounds of all clusters
            seg_path = next(sample_path.glob(str(args.seg)), None)
            if seg_path is None:
                print(f"\n    [red bold]No files match the pattern {args.seg} in {sample_path}\n")
                continue
            seg_cropped = load_nii_subset(seg_path, outer_xmin, outer_xmax, outer_ymin, outer_ymax, outer_zmin, outer_zmax)

            # Process each cluster to count cells or measure volume, in parallel
            cluster_data_results = density_in_cluster_parallel(cluster_bbox_data, native_cluster_index_cropped, seg_cropped, xy_res, z_res, args.connect, args.density)

            # Process cluster_data_results to save to CSV or perform further analysis
            data_list = []
            for result in cluster_data_results:
                cluster_ID, cell_count_or_seg_vol, cluster_volume_in_cubic_mm, density_measure, xmin, xmax, ymin, ymax, zmin, zmax = result

                # Determine the appropriate headers based on the density measure type
                if args.density == "cell_density":
                    count_or_vol_header, density_header = "cell_count", "cell_density"
                else: 
                    count_or_vol_header, density_header = "label_volume", "label_density"

                # Prepare the data dictionary
                data = {
                    "sample": sample_path.name, 
                    "cluster_ID": cluster_ID, 
                    count_or_vol_header: cell_count_or_seg_vol,  
                    "cluster_volume": cluster_volume_in_cubic_mm, 
                    density_header: density_measure, 
                    "xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax, "zmin": zmin, "zmax": zmax
                }

                data_list.append(data)
            
            # Create a DataFrame from the list of data dictionaries
            df = pd.DataFrame(data_list)

            # Sort the DataFrame by 'cluster_ID' in ascending order
            df_sorted = df.sort_values(by='cluster_ID', ascending=True)

            # Save the sorted DataFrame to the CSV file
            df_sorted.to_csv(output_path, index=False)
            print(f"\n    Output: [default bold]{output_path}")

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()