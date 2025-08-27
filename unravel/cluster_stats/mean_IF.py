#!/usr/bin/env python3

"""
Use ``cstats_mean_IF`` (``cmi``) from UNRAVEL to measure mean intensity of immunofluorescence staining in clusters.

Prereqs: 
    - ``vstats``
    - ``cstats_fdr``

Inputs:
    - This can be run from the vstats directory (will process .nii.gz images in the current directory)

Outputs: 
    - ./cluster_mean_IF_{cluster_index}/image_name.csv for each image
    - Columns: sample, cluster_ID, mean_IF_intensity

Next steps:
    - cd cluster_mean_IF...
    - ``utils_prepend`` -sk <path/sample_key.csv> -f  # If needed
    - [``cstats_index`` and ``cstats_table``]  # for an xlsx table and anatomically ordered clusters that can be used with ``cstats_prism``
    - ``cstats_mean_IF_summary`` --order Control Treatment --labels Control Treatment -t ttest  # Plots each cluster and outputs a summary table w/ stats
    - ``cstats_mean_IF_summary`` --order group3 group2 group1 --labels Group_3 Group_2 Group_1  # Tukey tests

Usage:
------
    cstats_mean_IF -ci path/rev_cluster_index.nii.gz [-ip '`*`.nii.gz'] [-c 1 2 3] [-v]
"""

import csv
import nibabel as nib
import numpy as np
from pathlib import Path 
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_3D_img
from unravel.core.img_tools import label_IDs
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path/rev_cluster_index.nii.gz from ``cstats_fdr``', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-ip', '--input_pattern', help="Glob pattern(s) for NIfTI images to process. Default: '*.nii.gz'", default='*.nii.gz', nargs='*', action=SM)
    opts.add_argument('-c', '--clusters', help='Space-separated list of cluster IDs to process. Default: all clusters', nargs='*', type=int, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity', action='store_true', default=False)

    return parser.parse_args()

# TODO: process each cluster in parallel

def calculate_mean_intensity_in_clusters(cluster_index, img, clusters=None):
    """Calculates mean intensity in the img ndarray for each cluster in the cluster index ndarray and saves it to a CSV file."""

    print("\n  Calculating mean immunofluorescence intensity for each cluster...\n")

    # Filter out background
    valid_mask = cluster_index > 0
    cluster_index = cluster_index[valid_mask].ravel()
    img_masked = img[valid_mask].ravel()

    # Use bincount to sum intensities for each cluster and count voxels
    sums = np.bincount(cluster_index, weights=img_masked)
    counts = np.bincount(cluster_index)

    # Suppress the runtime warning and handle potential division by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        mean_intensities = sums / counts

    mean_intensities = np.nan_to_num(mean_intensities)

    # Convert to dictionary (ignore background)
    mean_intensities_dict = {i: mean_intensities[i] for i in range(1, len(mean_intensities))}

    # Filter the dictionary if a list of clusters is provided
    if clusters:
        mean_intensities_dict = {cluster: mean_intensities_dict[cluster] for cluster in clusters if cluster in mean_intensities_dict}

    # Optional: Print results for the filtered clsutedrs
    for cluster, mean_intensity in mean_intensities_dict.items():
        print(f"    Cluster ID: {cluster}\tMean intensity: {mean_intensity}")

    return mean_intensities_dict

def write_to_csv(data, output_file, sample):
    """Writes the data to a CSV file with sample name included."""
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["sample", "cluster_ID", "mean_IF_intensity"])
        for key, value in data.items():
            writer.writerow([sample, key, value])


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    cluster_index_img = load_3D_img(args.input, verbose=args.verbose)
    
    # Check that the cluster index is an integer type (signed or unsigned)
    if cluster_index_img.dtype not in [np.int8, np.int16, np.int32, np.int64, np.uint8, np.uint16, np.uint32, np.uint64]:
        raise ValueError('The cluster index must be an integer type (int8, int16, int32, int64, uint8, uint16, uint32, or uint64)')

    # Either use the provided list of region IDs or create it using unique intensities
    if args.clusters:
        clusters = args.clusters
    else:
        print(f'\nProcessing these clusters IDs from {Path(args.input).name}:')
        clusters = label_IDs(cluster_index_img, min_voxel_count=1, print_IDs=True, print_sizes=False)
        print()

    output_folder = Path(f'cluster_mean_IF_{str(Path(args.input).name).replace(".nii.gz", "")}')
    output_folder.mkdir(parents=True, exist_ok=True)

    files = match_files(args.input_pattern)
    for file in files:
        if str(file).endswith('.nii.gz'):
            
            nii = nib.load(file)
            img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()

            # Calculate mean intensity
            mean_intensities = calculate_mean_intensity_in_clusters(cluster_index_img, img, clusters)

            output_filename = str(file.name).replace('.nii.gz', '.csv')
            output = output_folder / output_filename

            parts = str(Path(file).name).split('_')
            sample = parts[1] 
            write_to_csv(mean_intensities, output, sample)

    print(f'CSVs with mean IF intensities output to ./{output_folder}/')

    verbose_end_msg()


if __name__ == '__main__':
    main()