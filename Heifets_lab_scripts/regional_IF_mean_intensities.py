#!/usr/bin/env python3

import argparse 
import nibabel as nib
import numpy as np
import csv

def parse_args():
    DEFAULT_ATLAS = '/Users/Danielthy/Documents/_Heifets_lab_data/_UNRAVEL/testing/gubra_ano_combined_25um.nii.gz'
    parser = argparse.ArgumentParser(description='Measure mean intensity of immunofluorescence staining in brain regions.')
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz', default=DEFAULT_ATLAS, metavar='')
    parser.add_argument('-i', '--input', help='path/atlas_space_immunofluorescence_image.nii.gz', required=True, metavar='')
    parser.add_argument('-o', '--output', help='path/name.csv', default=None, metavar='')
    return parser.parse_args()

def calculate_mean_intensity(atlas, image):
    """Calculates mean intensity for each region in the atlas."""

    print("\nCalculating mean immunofluorescence intensity for each region in the atlas...\n")

    # Filter out background
    valid_mask = atlas > 0
    valid_atlas = atlas[valid_mask].astype(int)
    valid_image = image[valid_mask]

    # Use bincount to get sums for each region
    sums = np.bincount(valid_atlas, weights=valid_image)
    counts = np.bincount(valid_atlas)
    mean_intensities = sums / counts
    mean_intensities = np.nan_to_num(mean_intensities)

    # Convert to dictionary (ignore background)
    mean_intensities_dict = {i: mean_intensities[i] for i in range(1, len(mean_intensities))}

    # Optional: Print results
    for region, mean_intensity in mean_intensities_dict.items():
        print(f"  Region: {region}\tMean intensity: {mean_intensity}")

    return mean_intensities_dict


def write_to_csv(data, output_file):
    """Writes the data to a CSV file."""
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Region_Intensity", "Mean_IF_Intensity"])
        for key, value in data.items():
            writer.writerow([key, value])

def main():
    args = parse_args()

    # Load the images using nibabel
    atlas = nib.load(args.atlas)
    img = nib.load(args.input)

    atlas = atlas.get_fdata()
    img = img.get_fdata()

    # Calculate mean intensity
    mean_intensities = calculate_mean_intensity(atlas, img)

    if args.output is None:
        args.output = args.input.replace('.nii.gz', '_regional_mean_intensities.csv')

    # Write to CSV
    write_to_csv(mean_intensities, args.output)

if __name__ == "__main__":
    main()