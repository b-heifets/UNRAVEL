#!/usr/bin/env python3

"""
Use ``rstats_mean_IF`` from UNRAVEL to measure mean intensity of immunofluorescence staining in brain regions in atlas space.

Inputs:
    - `*`.nii.gz
    - path/atlas.nii.gz

Outputs: 
    - ./rstats_mean_IF/image_name.csv with regional mean intensity values for each image

Next: 
    - cd rstats_mean_IF
    - ``rstats_mean_IF_summary``

Usage:
------
    rstats_mean_IF -i '<asterisk>.nii.gz' -a path/atlas [--regions 1 2 3] [-v]
"""

import csv
import nibabel as nib
import numpy as np
from pathlib import Path 
import pandas as pd
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_3D_img
from unravel.core.img_tools import label_IDs
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help="Pattern for NIfTI images to process (e.g., '*.nii.gz')", required=True, action=SM)
    reqs.add_argument('-a', '--atlas', help='Path/atlas.nii.gz', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-r', '--regions', help='Space-separated list of region intensities to process. Default: process all IDs', nargs='*', type=int, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def calculate_mean_intensity(atlas, image, regions=None, verbose=False):
    """Calculates mean intensity for each region in the atlas."""

    if verbose:
        print("\n    Calculating mean immunofluorescence intensity for each region in the atlas...\n")

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

    # Filter the dictionary if `regions` is provided and not empty
    if regions is not None:
        # Ensure `regions` is a list or set to prevent ambiguity
        regions_set = set(regions) if not isinstance(regions, set) else regions
        mean_intensities_dict = {region: mean_intensities_dict.get(region, 0) for region in regions_set}
        mean_intensities_dict.pop(0, None)  # Drop the background
        # mean_intensities_dict = {region: mean_intensities_dict[region] for region in regions if region in mean_intensities_dict}  # Original line

    # Print the results
    if verbose:
        region_mean_df = pd.DataFrame(mean_intensities_dict.items(), columns=['Region', 'Mean_intensity'])
        print(f'\n{region_mean_df}\n')

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
        atlas_img = load_3D_img(args.atlas, verbose=args.verbose)
        region_intensities = label_IDs(atlas_img, min_voxel_count=1, print_IDs=True, print_sizes=False)
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
            mean_intensities = calculate_mean_intensity(atlas, img, region_intensities, args.verbose)

            output_filename = str(file.name).replace('.nii.gz', '.csv')
            output = output_folder / output_filename

            write_to_csv(mean_intensities, output)

    print('CSVs with regional mean IF intensities output to ./rstats_mean_IF/')

    verbose_end_msg()


if __name__ == '__main__':
    main()