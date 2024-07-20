#!/usr/bin/env python3

"""
Use ``rstats_mean_IF`` from UNRAVEL to measure mean intensity of immunofluorescence staining in brain regions in atlas space.

Usage:
------
    rstats_mean_IF -i '<asterisk>.nii.gz' -a path/atlas

Outputs: 
    - ./rstats_mean_IF/image_name.csv for each image

Next: 
    - cd rstats_mean_IF
    - ``rstats_mean_IF_summary``
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
    parser.add_argument('-i', '--input', help="Pattern for NIfTI images to process (e.g., '*.nii.gz')", required=True, action=SM)
    parser.add_argument('-a', '--atlas', help='Path/atlas.nii.gz', required=True, action=SM)
    parser.add_argument('-r', '--regions', help='Space-separated list of region intensities to process', nargs='*', type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


def calculate_mean_intensity(atlas, image, regions=None):
    """Calculates mean intensity for each region in the atlas."""

    print("\n  Calculating mean immunofluorescence intensity for each region in the atlas...\n")

    # Filter out background
    valid_mask = atlas > 0
    valid_atlas = atlas[valid_mask].astype(int)  # Convert to int for bincount
    valid_image = image[valid_mask]

    # Use bincount to sum intensities for each cluster and count voxels
    sums = np.bincount(valid_atlas, weights=valid_image)
    counts = np.bincount(valid_atlas)

    # Suppress the runtime warning and handle potential division by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        mean_intensities = sums / counts

    mean_intensities = np.nan_to_num(mean_intensities)

    # Convert to dictionary (ignore background)
    mean_intensities_dict = {i: mean_intensities[i] for i in range(1, len(mean_intensities))}

    # Filter the dictionary if regions are provided
    if regions:
        mean_intensities_dict = {region: mean_intensities_dict[region] for region in regions if region in mean_intensities_dict}

    # Optional: Print results for the filtered regions
    for region, mean_intensity in mean_intensities_dict.items():
        print(f"    Region: {region}\tMean intensity: {mean_intensity}")

    return mean_intensities_dict

def write_to_csv(data, output_file):
    """Writes the data to a CSV file."""
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Region_Intensity", "Mean_IF_Intensity"])
        for key, value in data.items():
            writer.writerow([key, value])


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Either use the provided list of region IDs or create it using unique intensities
    if args.regions:
        region_intensities = args.regions
    else:
        print(f'\nProcessing these region IDs from {args.atlas}')
        region_intensities = uniq_intensities(args.atlas)
        print()

    atlas_nii = nib.load(args.atlas)
    atlas = atlas_nii.get_fdata(dtype=np.float32)

    output_folder = Path('rstats_mean_IF')
    output_folder.mkdir(parents=True, exist_ok=True)

    files = Path().cwd().glob(args.input)
    for file in files:
        if str(file).endswith('.nii.gz'):
            
            nii = nib.load(file)
            img = nii.get_fdata(dtype=np.float32)

            # Calculate mean intensity
            mean_intensities = calculate_mean_intensity(atlas, img, region_intensities)

            output_filename = str(file.name).replace('.nii.gz', '.csv')
            output = output_folder / output_filename

            write_to_csv(mean_intensities, output)

    print('CSVs with regional mean IF intensities output to ./rstats_mean_IF/')

    verbose_end_msg()


if __name__ == '__main__':
    main()