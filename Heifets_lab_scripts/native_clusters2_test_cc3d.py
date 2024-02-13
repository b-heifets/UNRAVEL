#!/usr/bin/env python3

import argparse
import concurrent.futures #youtube.com/watch?v=fKl2JW_qrso
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
    parser.add_argument('-de', '--density', help='Density to measure: cell_density (default) or label_density', default='cell_density', choices=['cell_density', 'label_density'], action=SM)
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

    # Optional args
    parser.add_argument('-cc', '--connect', help='Connected component connectivity (6, 18, or 26). Default: 6', type=int, default=6, metavar='')

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
                output_path = resolve_relative_path(sample_path, Path("clusters", cluster_index_dir, f"{args.density}_data.csv"), make_parents=True)
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
                clusters = args.clusters
            clusters = [int(cluster) for cluster in clusters]

            # Crop outer space around all clusters 
            native_cluster_index_cropped, outer_xmin, outer_xmax, outer_ymin, outer_ymax, outer_zmin, outer_zmax = crop_outer_space(native_cluster_index, output_path)

            # Load image metadata from .txt
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(args.metadata)
            if xy_res is None or z_res is None: 
                print("    [red bold]./sample??/parameters/metadata.txt missing. cd to sample?? dir and run: metadata.py")

            # Apply connected components labeling of clusters to get bounding boxes
            connectivity = args.connect  # Use the connectivity specified by the user
            labels_out, n = cc3d.connected_components(native_cluster_index_cropped, connectivity=connectivity, return_N=True, out_dtype=np.uint32)

            # Get statistics for each labeled component
            stats = cc3d.statistics(labels_out)

            # Map new labels to original cluster IDs using centroids
            centroid_to_original_id = {}
            for label_id, centroid in stats['centroids'].items():
                if label_id == 0:  # Skip background
                    continue
                original_id = native_cluster_index_cropped[int(centroid[0]), int(centroid[1]), int(centroid[2])]
                centroid_to_original_id[label_id] = original_id

            # Load the segmentation image and crop it to the outer bounds of all clusters
            if Path(sample_path, args.seg).is_dir():
                seg_img = load_3D_img(Path(sample_path, args.seg, f"{sample_path.name}_{args.seg}.nii.gz"))
            else:
                seg_img = load_3D_img(resolve_relative_path(sample_path, args.seg))
            seg_cropped = seg_img[outer_xmin:outer_xmax, outer_ymin:outer_ymax, outer_zmin:outer_zmax]
            seg_cropped = seg_cropped.squeeze()  # Removes single-dimensional elements from array

            # Get bounding boxes for each cluster
            cluster_bbox_data = []
            for label_id in range(1, n + 1):  # Skip the background label 0
                if label_id not in centroid_to_original_id:
                    continue
                original_id = centroid_to_original_id[label_id]
                bbox = stats['bounding_boxes'][label_id]
                xmin, ymin, zmin, xmax, ymax, zmax = bbox
                cluster_bbox_data.append((original_id, xmin, xmax, ymin, ymax, zmin, zmax))

            # Process each cluster to count cells or measure volume, in parallel
            cluster_data_results = density_in_cluster_parallel(cluster_bbox_data, native_cluster_index_cropped, seg_cropped, xy_res, z_res, args.connect, args.density)

            # Process cluster_data_results to save to CSV or perform further analysis
            data_list = []
            for result in cluster_data_results:
                cluster_ID, cell_count_or_seg_vol, cluster_volume_in_cubic_mm, density_measure, xmin, xmax, ymin, ymax, zmin, zmax = result

                # Prepare the data dictionary based on the density measure type
                if args.density == "cell_density":
                    data = {
                        "sample": sample_path.name, 
                        "cluster_ID": cluster_ID, 
                        "cell_count": cell_count_or_seg_vol,  
                        "cluster_volume_in_cubic_mm": cluster_volume_in_cubic_mm, 
                        "cell_density": density_measure, 
                        "xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax, "zmin": zmin, "zmax": zmax
                    }
                else: 
                    data = {
                        "sample": sample_path.name, 
                        "cluster_ID": cluster_ID, 
                        "label_volume_in_cubic_mm": cell_count_or_seg_vol,  
                        "cluster_volume_in_cubic_mm": cluster_volume_in_cubic_mm, 
                        "label_density": density_measure, 
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


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()