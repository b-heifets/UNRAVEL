#!/usr/bin/env python3

import argparse
import csv
from argparse import RawTextHelpFormatter
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
import numpy as np
from unravel_config import Configuration
from unravel_img_tools import load_3D_img
from unravel_utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Measure mean intensity of immunofluorescence staining in brain regions for segmented voxels.', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, metavar='')
    parser.add_argument('-i', '--input', help='path/fluo_image or path/fluo_img_dir relative to sample?? folder', required=True, metavar='')
    parser.add_argument('-s', '--seg_dir', help='Name of folder with segmentation outputs (e.g., ochann_seg_ilasik_1)', required=True, metavar='')
    parser.add_argument('-o', '--output', help='path/name.csv relative to ./sample??/', default=None, metavar='')
    parser.add_argument('-r', '--regions', nargs='*', type=int, help='Optional: Space-separated list of region intensities to process. Default: Process all regions', default=None)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Run from experiment folder containing sample?? folders.
    Example usage: regional_IF_mean_intensities_in_segmented_voxels.py -i ochann -s ochann_seg_ilastik_1

    inputs: ./sample??/ochann_seg_ilastik_1/sample??_ABA_ochann_seg_ilastik_1.nii.gz & path/fluo_image
    outputs: ./sample??/ochann_seg_ilastik_1/sample??_ABA_ochann_seg_ilastik_1_regional_mean_intensities_in_seg_voxels.csv
    """
    return parser.parse_args()


@print_func_name_args_times()
def calculate_mean_intensity(fluo_image_path, ABA_seg_image_path, regions=None):
    """Calculates mean intensity for each region in the atlas."""

    print("\n  Calculating mean immunofluorescence intensity for each region in the atlas...\n")

    # Load the images
    fluo_img = load_3D_img(fluo_image_path, return_res=False)
    ABA_seg = load_3D_img(ABA_seg_image_path, return_res=False)

    # Use bincount to get fluo intensity sums for each region
    sums = np.bincount(ABA_seg, weights=fluo_img) # Sum of intensities in each region (excluding background)
    counts = np.bincount(ABA_seg) # Number of voxels in each region (excluding background)

    # Suppress the runtime warning and handle potential division by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        mean_intensities = sums / counts

    mean_intensities = np.nan_to_num(mean_intensities)

    # Convert to dictionary
    mean_intensities_dict = {i: mean_intensities[i] for i in range(1, len(mean_intensities))}

    # Filter the dictionary if regions are provided
    if regions:
        mean_intensities_dict = {region: mean_intensities_dict[region] for region in regions if region in mean_intensities_dict}

    # Print results
    for region, mean_intensity in mean_intensities_dict.items():
        print(f"    Region: {region}\tMean intensity in segmented voxels: {mean_intensity}")

    return mean_intensities_dict


def write_to_csv(data, output_file):
    """Writes the data to a CSV file."""
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Region_Intensity", "Mean_IF_Intensity_in_Seg_Voxels"])
        for key, value in data.items():
            writer.writerow([key, value])


def main():
    args = parse_args()

    samples = get_samples(args.dirs, args.pattern)

    if samples == ['.']:
        samples[0] = Path.cwd().name

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            cwd = Path(".").resolve()

            sample_path = Path(sample).resolve() if sample != cwd.name else Path().resolve()

            # Resolve paths
            fluo_image_path = Path(sample_path, args.input)
            ABA_seg_image_path = Path(sample_path, args.seg_dir, f"{sample}_ABA_{args.seg_dir}.nii.gz")

            # Use the provided list of regional intensities (if any)
            region_intensities = args.regions

            # Calculate mean intensity
            mean_intensities = calculate_mean_intensity(fluo_image_path, ABA_seg_image_path, region_intensities)

            # Write to CSV
            if args.output:
                write_to_csv(mean_intensities, args.output)
            else: 
                output = ABA_seg_image_path.replace('.nii.gz', '_regional_mean_intensities_in_seg_voxels.csv')
                write_to_csv(mean_intensities, output)

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()