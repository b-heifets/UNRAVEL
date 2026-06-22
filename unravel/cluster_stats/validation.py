#!/usr/bin/env python3

"""
Use ``cstats_validation`` (``cv``) from UNRAVEL to warp a cluster index from atlas space to tissue space, crop clusters, apply a segmentation mask, and quantify validation metrics (e.g., cell density, label density, and mean intensity) in each cluster (and optionally in atlas subregions within each cluster).

Prereqs:
    - Create cluster maps using ``clusters`` or ``cstats_fdr`` (note, the cluster index is reversed so that the largest cluster is 1)
    - Optional: ``cstats_fdr_range`` to determine the q value thresholds yielding significant clusters
    - ``cstats_mirror_indices`` to recursively mirror the cluster indices to the other hemisphere (if bilateral data was combined and processed w/ a hemispheric mask).
    - ``seg_ilastik`` to generate a segmentation mask in tissue space (e.g., to label c-Fos+ cells)

Inputs:
    - path/rev_cluster_index.nii.gz to warp from atlas space (rev = reverse, i.e., cluster IDs are from large to small)
    - rel_path/seg_img.nii.gz. 1st glob match processed

Outputs:
    - ./sample??/clusters/<cluster_index_dir>/outer_bounds.txt
    - ./sample??/clusters/<cluster_index_dir>/<args.metric>_data.csv
    - cluster_index_dir = Path(args.moving_img).name w/o "_rev_cluster_index" and ".nii.gz"

Note:
    - For -s, if a dir name is provided, the command will load ./sample??/seg_dir/sample??_seg_dir.nii.gz. 
    - If a relative path is provided, the command will load the image at the specified path.

Next steps:
    - ``cstats_summary_config``: Copy the cluster_summary.ini file to the current working directory for editing and use with ``cstats_summary``.
    - ``cstats_summary``: Aggregate and analyze cluster validation data from cstats_validation.    

Usage:
------
    cstats_validation -m <path/rev_cluster_index_to_warp_from_atlas_space.nii.gz> -s <rel_path/seg_img.nii.gz> [-me cell_density | label_density | mean_in_cluster | mean_in_seg_in_cluster] [-o <rel_path/output.csv>] [-c all or list of clusters (e.g., 1 3 4)] [-n <rel_path/native_image.zarr or .nii.gz>] [-fri <fixed_reg_input_for_reg>] [-inp nearestNeighbor or multiLabel] [-ro <reg_outputs_dir>] [-r <reg_res_in_microns>] [-md <metadata.txt>] [-zo <zoom_order>] [-pad <pad_percent_from_reg>] [-at <rel_path/native_atlas_in_tissue_space.nii.gz>] [-csv CCFv3-2020_info.csv] [-cc <connected_component_connectivity>] [-mi] [-d list of paths] [-p sample??] [-v]    
"""


import concurrent.futures
import cc3d
import numpy as np
import os
import pandas as pd
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration 
from unravel.core.img_io import load_3D_img, load_image_metadata_from_txt, load_nii_subset, resolve_path
from unravel.core.img_tools import label_IDs
from unravel.core.utils import get_pad_percent, log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples, print_func_name_args_times
from unravel.warp.to_native import to_native


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-m', '--moving_img', help='path/*_rev_cluster_index.nii.gz to warp from atlas space', required=True, action=SM)
    reqs.add_argument('-s', '--seg', help='rel_path/seg_img.nii.gz. 1st glob match processed', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-me', '--metric', help='Metric to measure: cell_density (default), label_density, mean_in_cluster, or mean_in_seg_in_cluster', default='cell_density', choices=['cell_density', 'label_density', 'mean_in_cluster', 'mean_in_seg_in_cluster'], action=SM)
    opts.add_argument('-i', '--intensity_img', help='rel_path/intensity image used for mean_in_cluster or mean_in_seg_in_cluster (e.g., .czi, .ome.tif, .tif, .nii.gz, .h5, .zarr, or dir of tifs)', default=None, action=SM)
    opts.add_argument('-ch', '--channel', help='Channel number for .czi images. Default: 0', default=0, type=int, action=SM)
    opts.add_argument('-o', '--output', help='rel_path/clusters_info.csv. Default: clusters/<cluster_index_dir>/<metric>_data.csv or <metric>_by_subregion_data.csv when --atlas_tissue is used', default=None, action=SM)
    opts.add_argument('-c', '--clusters', help='Clusters to process: all or list of clusters (e.g., 1 3 4). Default: Processes all clusters', nargs='*', default='all', action=SM)
    opts.add_argument('-at', '--atlas_tissue', help='rel_path/native atlas in tissue space (e.g., native/native_atlas_CCFv3_2020_30um.nii.gz from to_native). When provided, metrics are measured per atlas subregion within each cluster.', default=None, action=SM)
    opts.add_argument('-csv', '--info_csv_path', help='CSV name or path/name.csv for regional info with -at. Default: CCFv3-2020_info.csv', default='CCFv3-2020_info.csv', action=SM)
    opts.add_argument('-idc', '--region_id_col', help="Column in info_csv_path to use for region IDs with --atlas_tissue. Default: lowered_ID", default='lowered_ID', choices=['lowered_ID', 'structure_ID'], action=SM)

    # Optional to_native() args
    opts_to_native = parser.add_argument_group('Optional args for to_native()')
    opts_to_native.add_argument('-n', '--native_idx', help='Load/save native cluster index from/to rel_path/native_image.zarr (fast) or rel_path/native_image.nii.gz if provided', default=None, action=SM)
    opts_to_native.add_argument('-fri', '--fixed_reg_in', help='Fixed input for registration (unravel.register.reg). Default: autofl_50um_masked_fixed_reg_input.nii.gz', default="autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)    
    opts_to_native.add_argument('-inp', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor \[default], multiLabel)', default="nearestNeighbor", action=SM)
    opts_to_native.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from unravel.register.reg (e.g., transforms). Default: reg_outputs", default="reg_outputs", action=SM)
    opts_to_native.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    opts_to_native.add_argument('-md', '--metadata', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    opts_to_native.add_argument('-zo', '--zoom_order', help='SciPy zoom order for scaling to full res. Default: 0 (nearest-neighbor)', default='0',type=int, action=SM)
    opts_to_native.add_argument('-pad', '--pad_percent', help='Padding percentage from ``reg``. Default: from parameters/pad_percent.txt or 0.25.', type=float, action=SM)

    # Compatability args
    compatability = parser.add_argument_group('Compatability options for to_native()')
    compatability.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)

    # Optional arg for count_cells()
    opts_cell_counts = parser.add_argument_group('Optional args for count_cells()')
    opts_cell_counts.add_argument('-cc', '--connect', help='Connected component connectivity (6, 18, or 26). Default: 6', type=int, default=6, action=SM)
    
    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: QC. Aggregate .csv results for all samples if args.dirs, script to load image subset.
# TODO: Make config file for defaults or a command_generator.py script
# TODO: Use glob for -s to load the first match. If no match, print a message and continue to the next sample. Afterwards, update in help: "For -s, if a dir name is provided, the command will load ./sample??/seg_dir/sample??_seg_dir.nii.gz."
# TODO: Consider removing the -o option. Have I used this so far? If not, remove it.
# TODO: Like in ``rstats``, add this option: '-2p', '--stpt', help='For serial-2 photon data, use this flag to interleave blank slices (prevents cells from fusing across slices during counting)'
# TODO: Minimize columns in outputs (e.g., remove redundancy in new schema colums: sample,cluster_ID,metric,value,value_type,support,support_type,aggregation_method,cluster_volume,cell_count,cell_density,xmin,xmax,ymin,ymax,zmin,zmax)

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

def load_ccfv3_lookup(info_csv_path, region_id_col='lowered_ID'):
    """Load region lookup from a built-in or user-provided CCFv3 info CSV.

    Parameters
    ----------
    info_csv_path : str or Path
        Path to a custom info CSV, or one of the built-in names
        ('CCFv3-2017_info.csv', 'CCFv3-2020_info.csv').
    region_id_col : str, optional
        Column to use as the region-ID key. Default: 'lowered_ID'.
        Common options:
            - 'lowered_ID'
            - 'structure_ID'

    Returns
    -------
    dict
        Mapping: region ID -> {'abbreviation': ..., 'region_name': ...}
    """
    columns_to_load = [region_id_col, 'abbreviation', 'full_structure_name']

    if info_csv_path in ['CCFv3-2017_info.csv', 'CCFv3-2020_info.csv']:
        info_df = pd.read_csv(
            Path(__file__).parent.parent / 'core' / 'csvs' / info_csv_path,
            usecols=columns_to_load
        )
    else:
        info_df = pd.read_csv(info_csv_path, usecols=columns_to_load)

    info_df[region_id_col] = pd.to_numeric(info_df[region_id_col], errors='coerce')

    lookup = {}
    for _, row in info_df.iterrows():
        if pd.isna(row[region_id_col]):
            continue

        lookup[int(row[region_id_col])] = {
            'abbreviation': row['abbreviation'] if pd.notna(row['abbreviation']) else np.nan,
            'region_name': row['full_structure_name'] if pd.notna(row['full_structure_name']) else np.nan,
        }

    return lookup

def metric_in_cluster(cluster_data, native_cluster_index_cropped, seg_cropped, xy_res, z_res,
                      connectivity=6, metric='cell_density', intensity_cropped=None):
    """Measure a validation metric in the current cluster.

    Supported metrics:
        - cell_density
        - label_density
        - mean_in_cluster
        - mean_in_seg_in_cluster

    Returns:
        cluster_ID, primary_value, cluster_volume_in_cubic_mm, metric_value,
        xmin, xmax, ymin, ymax, zmin, zmax
    """
    cluster_ID, xmin, xmax, ymin, ymax, zmin, zmax = cluster_data

    # Crop the cluster from the native cluster index
    cropped_cluster = native_cluster_index_cropped[xmin:xmax, ymin:ymax, zmin:zmax]

    # Crop segmentation image for the current cluster bbox
    seg_in_cluster = seg_cropped[xmin:xmax, ymin:ymax, zmin:zmax].copy()

    # Restrict to the current cluster only
    cluster_mask = cropped_cluster == cluster_ID
    seg_in_cluster[~cluster_mask] = 0

    # Cluster volume
    cluster_voxel_count = np.count_nonzero(cluster_mask)
    cluster_volume_in_cubic_mm = ((xy_res**2) * z_res) * cluster_voxel_count / 1e9

    if metric == "cell_density":
        cell_count = count_cells(seg_in_cluster, connectivity=connectivity)
        cell_density = cell_count / cluster_volume_in_cubic_mm if cluster_volume_in_cubic_mm > 0 else np.nan
        return cluster_ID, cell_count, cluster_volume_in_cubic_mm, cell_density, xmin, xmax, ymin, ymax, zmin, zmax

    elif metric == "label_density":
        seg_voxel_count = np.count_nonzero(seg_in_cluster)
        seg_volume_in_cubic_mm = ((xy_res**2) * z_res) * seg_voxel_count / 1e9
        label_density = (seg_volume_in_cubic_mm / cluster_volume_in_cubic_mm * 100) if cluster_volume_in_cubic_mm > 0 else np.nan
        return cluster_ID, seg_volume_in_cubic_mm, cluster_volume_in_cubic_mm, label_density, xmin, xmax, ymin, ymax, zmin, zmax

    elif metric == "mean_in_cluster":
        if intensity_cropped is None:
            raise ValueError("intensity_cropped is required for mean_in_cluster")

        intensity_in_cluster = intensity_cropped[xmin:xmax, ymin:ymax, zmin:zmax]
        voxel_count = cluster_voxel_count
        mean_intensity = float(intensity_in_cluster[cluster_mask].mean()) if voxel_count > 0 else np.nan
        return cluster_ID, voxel_count, cluster_volume_in_cubic_mm, mean_intensity, xmin, xmax, ymin, ymax, zmin, zmax

    elif metric == "mean_in_seg_in_cluster":
        if intensity_cropped is None:
            raise ValueError("intensity_cropped is required for mean_in_seg_in_cluster")

        intensity_in_cluster = intensity_cropped[xmin:xmax, ymin:ymax, zmin:zmax]
        seg_mask = seg_in_cluster > 0
        voxel_count = np.count_nonzero(seg_mask)
        mean_intensity = float(intensity_in_cluster[seg_mask].mean()) if voxel_count > 0 else np.nan
        return cluster_ID, voxel_count, cluster_volume_in_cubic_mm, mean_intensity, xmin, xmax, ymin, ymax, zmin, zmax

    else:
        raise ValueError(
            f"Unsupported metric: {metric} "
            f"(Use -me with 'cell_density', 'label_density', 'mean_in_cluster', or 'mean_in_seg_in_cluster')"
        )
    
@print_func_name_args_times()
def metric_in_cluster_parallel(cluster_bbox_results, native_cluster_index_cropped, seg_cropped, xy_res, z_res, connectivity=6, metric='cell_density', intensity_cropped=None):
    """Measure a validation metric in each cluster in parallel. Return list of results."""
    results = []
    num_cores = os.cpu_count()
    workers = min(num_cores, len(cluster_bbox_results)) 
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_cluster = {executor.submit(metric_in_cluster, cluster_data, native_cluster_index_cropped, seg_cropped, xy_res, z_res, connectivity, metric, intensity_cropped): cluster_data[0] for cluster_data in cluster_bbox_results} # cluster_data[0] is the cluster_ID
        for future in concurrent.futures.as_completed(future_to_cluster):
            cluster_ID = future_to_cluster[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                print(f'Cluster {cluster_ID} generated an exception: {exc}')
    return results

def metric_in_subregions_of_cluster(cluster_data, native_cluster_index_cropped, atlas_cropped, seg_cropped,
                                    xy_res, z_res, connectivity=6, metric='cell_density',
                                    intensity_cropped=None, region_lookup=None):
    """Measure a metric in each atlas subregion within the current cluster.

    Returns:
        list of dicts, one row per (cluster_ID, region_ID)
    """
    cluster_ID, xmin, xmax, ymin, ymax, zmin, zmax = cluster_data

    cropped_cluster = native_cluster_index_cropped[xmin:xmax, ymin:ymax, zmin:zmax]
    cluster_mask = cropped_cluster == cluster_ID

    seg_in_cluster = seg_cropped[xmin:xmax, ymin:ymax, zmin:zmax].copy()
    seg_in_cluster[~cluster_mask] = 0

    atlas_in_cluster = atlas_cropped[xmin:xmax, ymin:ymax, zmin:zmax].copy()
    atlas_in_cluster[~cluster_mask] = 0

    intensity_in_cluster = None
    if metric in ["mean_in_cluster", "mean_in_seg_in_cluster"]:
        if intensity_cropped is None:
            raise ValueError("intensity_cropped is required for mean-based metrics")
        intensity_in_cluster = intensity_cropped[xmin:xmax, ymin:ymax, zmin:zmax]

    cluster_voxel_count = np.count_nonzero(cluster_mask)
    cluster_volume_in_cubic_mm = ((xy_res**2) * z_res) * cluster_voxel_count / 1e9

    region_IDs = np.unique(atlas_in_cluster)
    region_IDs = region_IDs[region_IDs > 0]

    rows = []

    for region_ID in region_IDs:
        region_mask = atlas_in_cluster == region_ID
        region_voxel_count = np.count_nonzero(region_mask)
        if region_voxel_count == 0:
            continue

        subregion_volume_in_cubic_mm = ((xy_res**2) * z_res) * region_voxel_count / 1e9

        if metric == "cell_density":
            seg_in_region = seg_in_cluster.copy()
            seg_in_region[~region_mask] = 0
            primary_value = count_cells(seg_in_region, connectivity=connectivity)
            metric_value = primary_value / subregion_volume_in_cubic_mm if subregion_volume_in_cubic_mm > 0 else np.nan
            primary_header = "cell_count"
            metric_header = "cell_density"
            value_type = "density"
            support_type = "cell_count"
            aggregation_method = "recompute_from_support_and_volume"

        elif metric == "label_density":
            seg_voxel_count = np.count_nonzero(seg_in_cluster[region_mask])
            primary_value = ((xy_res**2) * z_res) * seg_voxel_count / 1e9
            metric_value = (primary_value / subregion_volume_in_cubic_mm * 100) if subregion_volume_in_cubic_mm > 0 else np.nan
            primary_header = "label_volume"
            metric_header = "label_density"
            value_type = "density"
            support_type = "label_volume"
            aggregation_method = "recompute_from_support_and_volume"

        elif metric == "mean_in_cluster":
            primary_value = region_voxel_count
            metric_value = float(intensity_in_cluster[region_mask].mean()) if primary_value > 0 else np.nan
            primary_header = "subregion_voxel_count"
            metric_header = "mean_intensity"
            value_type = "mean_intensity"
            support_type = "subregion_voxel_count"
            aggregation_method = "weighted_mean_by_support"

        elif metric == "mean_in_seg_in_cluster":
            seg_region_mask = region_mask & (seg_in_cluster > 0)
            primary_value = np.count_nonzero(seg_region_mask)
            metric_value = float(intensity_in_cluster[seg_region_mask].mean()) if primary_value > 0 else np.nan
            primary_header = "seg_voxel_count"
            metric_header = "mean_intensity"
            value_type = "mean_intensity"
            support_type = "seg_voxel_count"
            aggregation_method = "weighted_mean_by_support"

        else:
            raise ValueError(f"Unsupported metric: {metric}")

        row = {
            "cluster_ID": cluster_ID,
            "region_ID": int(region_ID),
            "metric": metric,
            "value": metric_value,
            "value_type": value_type,
            "support": primary_value,
            "support_type": support_type,
            "aggregation_method": aggregation_method,
            "cluster_volume": cluster_volume_in_cubic_mm,
            "subregion_volume": subregion_volume_in_cubic_mm,
            primary_header: primary_value,
            metric_header: metric_value,
            "xmin": xmin, "xmax": xmax,
            "ymin": ymin, "ymax": ymax,
            "zmin": zmin, "zmax": zmax
        }

        if region_lookup is not None:
            region_info = region_lookup.get(int(region_ID), {})
            row["abbreviation"] = region_info.get("abbreviation", np.nan)
            row["region_name"] = region_info.get("region_name", np.nan)

        rows.append(row)

    return rows

@print_func_name_args_times()
def metric_in_subregions_of_cluster_parallel(cluster_bbox_results, native_cluster_index_cropped, atlas_cropped,
                                             seg_cropped, xy_res, z_res, connectivity=6,
                                             metric='cell_density', intensity_cropped=None,
                                             region_lookup=None):
    """Measure a metric in atlas subregions within each cluster, in parallel."""
    results = []
    num_cores = os.cpu_count()
    workers = min(num_cores, len(cluster_bbox_results))

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_cluster = {
            executor.submit(
                metric_in_subregions_of_cluster,
                cluster_data,
                native_cluster_index_cropped,
                atlas_cropped,
                seg_cropped,
                xy_res,
                z_res,
                connectivity,
                metric,
                intensity_cropped,
                region_lookup
            ): cluster_data[0]
            for cluster_data in cluster_bbox_results
        }

        for future in concurrent.futures.as_completed(future_to_cluster):
            cluster_ID = future_to_cluster[future]
            try:
                results.extend(future.result())
            except Exception as exc:
                print(f'Cluster {cluster_ID} generated an exception: {exc}')

    return results


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)
    region_lookup = (
        load_ccfv3_lookup(args.info_csv_path, region_id_col=args.region_id_col)
        if args.atlas_tissue else None
    )

    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:
            
            # Define output path
            cluster_index_dir = str(Path(args.moving_img).name).replace(".nii.gz", "").replace("_rev_cluster_index_", "_")
            if args.output:
                output_path = resolve_path(sample_path, args.output)
            else:
                default_name = (
                    f"{args.metric}_by_subregion_data.csv"
                    if args.atlas_tissue else
                    f"{args.metric}_data.csv"
                )
                output_path = resolve_path(
                    sample_path,
                    Path("clusters", cluster_index_dir, default_name),
                    make_parents=True
                )

            # Skip if the chosen output exists
            if output_path.exists():
                print(f"\n    {output_path} already exists. Skipping {sample_path.name}.\n")
                progress.update(task_id, advance=1)
                continue
            
            # Use lower bit-depth possible for cluster index
            rev_cluster_index = load_3D_img(args.moving_img, verbose=args.verbose)

            # Check if any clusters are present and raise exception if not
            if np.count_nonzero(rev_cluster_index) == 0:
                raise ValueError(f"No clusters detected in {args.moving_img}.")
                
            # Define paths relative to sample?? folder 
            native_idx_path = resolve_path(sample_path, args.native_idx) if args.native_idx else None
            
            # Load cluster index and convert to ndarray 
            if native_idx_path and native_idx_path.exists():
                native_cluster_index = load_3D_img(native_idx_path, verbose=args.verbose)
            else:
                fixed_reg_input = Path(sample_path, args.reg_outputs, args.fixed_reg_in) 
                if not fixed_reg_input.exists():
                    fixed_reg_input = sample_path / args.reg_outputs / "autofl_50um_fixed_reg_input.nii.gz"
                pad_percent = get_pad_percent(sample_path / args.reg_outputs, args.pad_percent)
                native_cluster_index = to_native(sample_path=sample_path, reg_outputs=args.reg_outputs, fixed_reg_in=fixed_reg_input, moving_img_path=args.moving_img, metadata_rel_path=args.metadata, reg_res=args.reg_res, miracl=args.miracl, zoom_order=args.zoom_order, interpol=args.interpol, output=native_idx_path, pad_percent=pad_percent)

            # Get clusters to process
            if args.clusters == "all" or args.clusters == ["all"] or args.clusters is None:
                clusters = label_IDs(rev_cluster_index)
            else:
                clusters = [int(cluster) for cluster in args.clusters]

            # Crop outer space around all clusters 
            native_cluster_index_cropped, outer_xmin, outer_xmax, outer_ymin, outer_ymax, outer_zmin, outer_zmax = crop_outer_space(native_cluster_index, output_path)

            # Load image metadata from .txt
            metadata_path = resolve_path(sample_path, args.metadata)
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(metadata_path)
            if xy_res is None or z_res is None: 
                print("    [red bold]./sample??/parameters/metadata.txt missing. cd to sample?? dir and run: io_metadata")
                progress.update(task_id, advance=1)
                continue

            # Get bounding boxes for each cluster in parallel
            cluster_bbox_data = cluster_bbox_parallel(native_cluster_index_cropped, clusters)

            # Load the segmentation image and crop it to the outer bounds of all clusters
            seg_path = next(sample_path.glob(str(args.seg)), None)
            if seg_path is None:
                print(f"\n    [red bold]No files match the pattern {args.seg} in {sample_path}\n")
                progress.update(task_id, advance=1)
                continue
            seg_cropped = load_nii_subset(seg_path, outer_xmin, outer_xmax, outer_ymin, outer_ymax, outer_zmin, outer_zmax)

            # Load the atlas image and crop it to the outer bounds of all clusters if --atlas_tissue is provided
            atlas_cropped = None
            if args.atlas_tissue:
                atlas_path = next(sample_path.glob(str(args.atlas_tissue)), None)
                if atlas_path is None:
                    print(f"\n    [red bold]No files match the pattern {args.atlas_tissue} in {sample_path}\n")
                    progress.update(task_id, advance=1)
                    continue

                atlas_img = load_3D_img(atlas_path, verbose=args.verbose)
                atlas_cropped = atlas_img[
                    outer_xmin:outer_xmax,
                    outer_ymin:outer_ymax,
                    outer_zmin:outer_zmax
                ]
                del atlas_img

                if atlas_cropped.shape != seg_cropped.shape:
                    raise ValueError(
                        f"Atlas image shape {atlas_cropped.shape} does not match segmentation shape {seg_cropped.shape} "
                        f"after cropping for {sample_path.name}."
                    )

            # Load the intensity image and crop it to the outer bounds of all clusters if needed for the chosen metric
            intensity_cropped = None
            if args.metric in ["mean_in_cluster", "mean_in_seg_in_cluster"]:
                if args.intensity_img is None:
                    raise ValueError("--intensity_img is required for mean_in_cluster or mean_in_seg_in_cluster.")

                intensity_path = next(sample_path.glob(str(args.intensity_img)), None)
                if intensity_path is None:
                    print(f"\n    [red bold]No files match the pattern {args.intensity_img} in {sample_path}\n")
                    progress.update(task_id, advance=1)
                    continue

                intensity_img = load_3D_img(intensity_path, channel=args.channel, verbose=args.verbose)
                intensity_cropped = intensity_img[
                    outer_xmin:outer_xmax,
                    outer_ymin:outer_ymax,
                    outer_zmin:outer_zmax
                ]
                del intensity_img

                if intensity_cropped.shape != seg_cropped.shape:
                    raise ValueError(
                        f"Intensity image shape {intensity_cropped.shape} does not match segmentation shape {seg_cropped.shape} "
                        f"after cropping for {sample_path.name}."
                    )

            # Process each cluster to count cells or measure volume, in parallel
            if args.atlas_tissue:
                data_list = metric_in_subregions_of_cluster_parallel(
                    cluster_bbox_data,
                    native_cluster_index_cropped,
                    atlas_cropped,
                    seg_cropped,
                    xy_res,
                    z_res,
                    args.connect,
                    args.metric,
                    intensity_cropped,
                    region_lookup
                )

                if not data_list:
                    print(f"\n    [yellow]No atlas subregions overlapped the selected clusters in {sample_path.name}\n")
                    progress.update(task_id, advance=1)
                    continue

                for row in data_list:
                    row["sample"] = sample_path.name

                df = pd.DataFrame(data_list)
                df_sorted = df.sort_values(by=['cluster_ID', 'region_ID'], ascending=True)

            else:
                # Original per-cluster behavior
                cluster_data_results = metric_in_cluster_parallel(
                    cluster_bbox_data,
                    native_cluster_index_cropped,
                    seg_cropped,
                    xy_res,
                    z_res,
                    args.connect,
                    args.metric,
                    intensity_cropped
                )

                data_list = []
                for result in cluster_data_results:
                    cluster_ID, primary_value, cluster_volume_in_cubic_mm, metric_value, xmin, xmax, ymin, ymax, zmin, zmax = result

                    if args.metric == "cell_density":
                        primary_header, metric_header = "cell_count", "cell_density"
                        value_type = "density"
                        support_type = "cell_count"
                        aggregation_method = "recompute_from_support_and_volume"

                    elif args.metric == "label_density":
                        primary_header, metric_header = "label_volume", "label_density"
                        value_type = "density"
                        support_type = "label_volume"
                        aggregation_method = "recompute_from_support_and_volume"

                    elif args.metric == "mean_in_cluster":
                        primary_header, metric_header = "cluster_voxel_count", "mean_intensity"
                        value_type = "mean_intensity"
                        support_type = "cluster_voxel_count"
                        aggregation_method = "weighted_mean_by_support"

                    elif args.metric == "mean_in_seg_in_cluster":
                        primary_header, metric_header = "seg_voxel_count", "mean_intensity"
                        value_type = "mean_intensity"
                        support_type = "seg_voxel_count"
                        aggregation_method = "weighted_mean_by_support"

                    else:
                        raise ValueError(f"Unsupported metric: {args.metric}")

                    data = {
                        "sample": sample_path.name,
                        "cluster_ID": cluster_ID,
                        "metric": args.metric,
                        "value": metric_value,
                        "value_type": value_type,
                        "support": primary_value,
                        "support_type": support_type,
                        "aggregation_method": aggregation_method,
                        "cluster_volume": cluster_volume_in_cubic_mm,
                        primary_header: primary_value,
                        metric_header: metric_value,
                        "xmin": xmin, "xmax": xmax,
                        "ymin": ymin, "ymax": ymax,
                        "zmin": zmin, "zmax": zmax
                    }

                    data_list.append(data)

                df = pd.DataFrame(data_list)
                df_sorted = df.sort_values(by='cluster_ID', ascending=True)

            df_sorted.to_csv(output_path, index=False)
            print(f"\n    Output: [default bold]{output_path}")

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()