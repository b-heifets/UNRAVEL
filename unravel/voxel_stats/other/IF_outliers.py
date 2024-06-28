#!/usr/bin/env python3

"""
Loads .nii.gz images matching pattern, gets the mean intensity of voxels using the mask, checks for outliers (>3*SD +/- the mean), and plots results

Usage:
------ 
    path/IF_outliers.py -p '<asterisk>.nii.gz' -m path/mask.nii.gz -o means_in_mask_plot.pdf -v
"""

import argparse
import glob
import os
import numpy as np
import matplotlib.pyplot as plt
from rich import print
from rich.live import Live

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-p', '--pattern', help='Regex pattern in quotes for matching .nii.gz images', default=None, action=SM)
    parser.add_argument('-m', '--mask', help='path/mask.nii.gz', default=None, action=SM)
    parser.add_argument('-o', '--output', help='path/name.[pdf/png]. Default: means_in_mask.pdf ', default='means_in_mask.pdf', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


def mean_intensity_within_mask(image, mask):
    return np.mean(image[mask > 0])

def detect_outliers(values):
    mean_val = np.mean(values)
    std_dev = np.std(values)
    lower_bound = mean_val - 3 * std_dev
    upper_bound = mean_val + 3 * std_dev
    
    outliers = [(i, v) for i, v in enumerate(values) if v < lower_bound or v > upper_bound]
    return outliers


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    mask = load_3D_img(args.mask)

    # Collect .nii.gz files matching the pattern
    images = [f for f in glob.glob(args.pattern) if os.path.basename(f) != args.mask]

    mean_values = []

    # For each image, calculate the mean intensity value within the masked region.
    progress = initialize_progress_bar(total_tasks=len(images))
    task_id = progress.add_task("[red]Getting means...", total=len(images))
    with Live(progress):
        for idx, img in enumerate(images):
            image = load_3D_img(img)
            mean_intensity = mean_intensity_within_mask(image, mask)
            mean_values.append(mean_intensity)
            print(f"{idx} Mean in mask for {img}: {mean_intensity}")
            progress.update(task_id, advance=1)

    # Plot mean values
    plt.scatter(range(len(mean_values)), mean_values)
    plt.xlabel('Image Index')
    plt.ylabel('Mean Intensity within mask')
    plt.title('Mean Intensities within mask for each image')
    plt.savefig(args.output)

    # Detect outliers
    outliers = detect_outliers(mean_values)
    if outliers:
        for idx, value in outliers:
            print(f"Potential outlier: {images[idx]} with mean intensity value: {value}")
    else:
        print("No outliers detected!")

    verbose_end_msg()


if __name__ == '__main__':
    main()