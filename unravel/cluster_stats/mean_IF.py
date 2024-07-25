#!/usr/bin/env python3

"""
Use ``cluster_mean_IF`` from UNRAVEL to measure mean intensity of immunofluorescence staining in clusters.

Usage:
------
    cluster_mean_IF -ci path/rev_cluster_index.nii.gz

Prereqs: 
    - vstats
    - cluster_fdr

Inputs:
    - This can be run from the vstats directory (will process .nii.gz images in the current directory)

Outputs: 
    - ./cluster_mean_IF_{cluster_index}/image_name.csv for each image
    - Columns: sample, cluster_ID, mean_IF_intensity

Next: 
    - cd cluster_mean_IF...
    - utils_prepend -sk <path/sample_key.csv> -f  # If needed
    - [cluster_index and cluster_table]  # for an xlsx table and anatomically ordered clusters that can be used with cluster_prism
    - cluster_mean_IF_summary --order Control Treatment --labels Control Treatment -t ttest  # Plots each cluster and outputs a summary table w/ stats
    - cluster_mean_IF_summary --order group3 group2 group1 --labels Group_3 Group_2 Group_1  # Tukey tests
"""

import argparse
import csv
import nibabel as nib
import numpy as np
from pathlib import Path 
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.image_tools.unique_intensities import uniq_intensities


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-ip', '--input_pattern', help="Pattern for NIfTI images to process relative to cwd. Default: '*.nii.gz'", default='*.nii.gz', action=SM)
    parser.add_argument('-ci', '--cluster_index', help='Path/rev_cluster_index.nii.gz from ``cluster_fdr``', required=True, action=SM)
    parser.add_argument('-c', '--clusters', help='Space-separated list of cluster IDs to process. Default: all clusters', nargs='*', type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: process each cluster in parallel

def calculate_mean_intensity_in_clusters(cluster_index, img, clusters=None):
    """Calculates mean intensity in the img ndarray for each cluster in the cluster index ndarray and saves it to a CSV file."""

    print("\n  Calculating mean immunofluorescence intensity for each cluster...\n")

    # Filter out background
    valid_mask = cluster_index > 0
    cluster_index = cluster_index[valid_mask].astype(int)  # Ensure int for bincount
    img_masked = img[valid_mask]

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

    # Either use the provided list of region IDs or create it using unique intensities
    if args.clusters:
        clusters = args.clusters
    else:
        print(f'\nProcessing these clusters IDs from {Path(args.cluster_index).name}:')
        clusters = uniq_intensities(args.cluster_index)
        print()

    output_folder = Path(f'cluster_mean_IF_{str(Path(args.cluster_index).name).replace(".nii.gz", "")}')
    output_folder.mkdir(parents=True, exist_ok=True)

    files = Path().cwd().glob(args.input_pattern)
    for file in files:
        if str(file).endswith('.nii.gz'):
            
            nii = nib.load(file)
            img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()

            cluster_index = nib.load(args.cluster_index)
            cluster_index = np.asanyarray(cluster_index.dataobj, dtype=cluster_index.header.get_data_dtype()).squeeze()

            # Calculate mean intensity
            mean_intensities = calculate_mean_intensity_in_clusters(cluster_index, img, clusters)

            output_filename = str(file.name).replace('.nii.gz', '.csv')
            output = output_folder / output_filename

            parts = str(Path(file).name).split('_')
            sample = parts[1] 
            write_to_csv(mean_intensities, output, sample)

    print(f'CSVs with mean IF intensities output to ./{output_folder}/')

    verbose_end_msg()


if __name__ == '__main__':
    main()