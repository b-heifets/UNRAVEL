#!/usr/bin/env python3

"""
Use ``gta_auto_crop`` (``gta_ac``) from UNRAVEL to automatically crop 3D images for all `ID_*` directories based on the brain bounding box.

Inputs:
    - One or more 3D image files (e.g., directory with tifs)

Outputs:
    - ./bbox/: Saves average intensity projections (AIPs) for two axes (coronal and sagittal) w/ & w/o mask outlines.
    - ./bbox/: Saves thresholded AIPs as binary masks.
    - ./bbox/: Saves bounding box coordinates of the largest connected component in a text file.
    - ./bbox/: Saves the bounding box coordinates with padding in a text file.
    - ./: Crops the original 3D image based on the bounding box w/ padding and saves it as a tif series to ./<tif_dir>_cropped/.

Note:
    - This currently uses a simple thresholding method to identify brain tissue, which works well for GTA data.
    - Future improvements could include more advanced segmentation techniques, such as machine learning-based methods.
    - For simplicity and processing with Ilastik, this outputs as a TIFF series.
    - The TIFF series can be converted with ``io_convert_img`` (``conv``) to other formats if needed.

Next steps:
    - Aggregate the average intensity projections (AIPs) from the green channel with the outline to check the cropping.
    - Use ``gta_bbox_crop`` (``gta_bc``) to crop the other channels (e.g., red) using the bounding box from the green channel.
    - To save space, the original TIFF directories may be deleted. Run from TIFFs/ directory: `rm -rf **/green **/red`
    - ``reg_prep`` to prepare the cropped images for registration.
    - ``seg_copy_tifs`` to copy select TIFFs to a common directory to train an Ilastik project for cell segmentation.

Usage:
------
    gta_ac [-i green] [-o bbox] [-t 40] [-pad 0.02] [--force] [-d ID_123 ID_456 ...] [-p pattern] [-v]
"""

import cc3d
import numpy as np
import tifffile
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from scipy.ndimage import binary_erosion

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_3D_img, save_as_tifs
from unravel.core.utils import get_stem, log_command, match_files, verbose_start_msg, verbose_end_msg, get_samples, initialize_progress_bar


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help='Name of a directory with TIFFs in the "ID_*" directories. Default: green', default='green', action=SM)
    opts.add_argument('-o', '--output', help='Output directory for average intensity projections and masks. Default: bbox', default='bbox', action=SM)
    opts.add_argument('-t', '--threshold', help='Intensity value for thresholding brain tissue (default: 40)', default=40, type=int, action=SM)
    opts.add_argument('-pad', '--pad_percent', help='Percentage of padding to add to each dimension of the brain bbox. Default: 0.02 (2%%).', default=0.02, type=float, action=SM)
    opts.add_argument('-f', '--force', help='Force overwrite existing output files. Default: False', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to "ID*" dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: ID_*', default='ID_*', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def create_outline(mask):
    """Create an outline mask by eroding the original mask and subtracting it from the original mask."""
    eroded_mask = binary_erosion(mask)
    outline_mask = mask.astype(np.uint8) - eroded_mask.astype(np.uint8)
    return outline_mask


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:

            img_path = sample_path / args.input

            output_dir = sample_path / args.output
            output_dir.mkdir(parents=True, exist_ok=True)

            # Define output paths
            img_stem = get_stem(img_path)
            coronal_aip_path = str(output_dir / f"{img_stem}_coronal_aip.tif")
            sagittal_aip_path = str(output_dir / f"{img_stem}_sagittal_aip.tif")
            coronal_aip_thr_path = str(output_dir / f"{img_stem}_coronal_aip_thresh{args.threshold}.tif")
            sagittal_aip_thr_path = str(output_dir / f"{img_stem}_sagittal_aip_thresh{args.threshold}.tif")
            coronal_aip_outline_path = str(output_dir / f"{img_stem}_coronal_aip_outline.tif")
            sagittal_aip_outline_path = str(output_dir / f"{img_stem}_sagittal_aip_outline.tif")
            bbox_file = output_dir / f"{img_stem}_bbox_zyx.txt"
            pad_percent_txt = output_dir / f"{img_stem}_pad_percent.txt"
            bbox_pad_file = output_dir / f"{img_stem}_bbox_pad_zyx.txt"
            output_cropped = img_path.parent / f"{img_stem}_cropped"

            if not args.force and output_cropped.exists() and any(output_cropped.iterdir()):
                print(f"\n\n    {output_cropped} already exists. Skipping.\n")
                continue

            if args.force and output_cropped.exists():
                for file in output_cropped.iterdir():
                    file.unlink()

            img = load_3D_img(img_path, desired_axis_order='zyx', verbose=args.verbose)

            # Create/save average intensity projections (AIPs) for 2 axes (coronal [x, y] and sagittal [y, z])
            aip_coronal = img.mean(axis=0)
            aip_sagittal = img.mean(axis=2)

            # Save AIPs as .tif files
            tifffile.imwrite(coronal_aip_path, aip_coronal.astype(np.uint16))
            tifffile.imwrite(sagittal_aip_path, aip_sagittal.astype(np.uint16))

            # Threshold the AIPs
            aip_coronal_thresh = aip_coronal > args.threshold # Binary thresholding
            aip_sagittal_thresh = aip_sagittal > args.threshold

            # Save thresholded AIPs
            tifffile.imwrite(coronal_aip_thr_path, aip_coronal_thresh.astype(np.uint8) * 255)
            tifffile.imwrite(sagittal_aip_thr_path, aip_sagittal_thresh.astype(np.uint8) * 255)

            # Get mean in brain masks
            aip_coronal_mean = aip_coronal[aip_coronal_thresh].mean()
            aip_sagittal_mean = aip_sagittal[aip_sagittal_thresh].mean()

            # Create outlines for the AIPs
            aip_coronal_outline = create_outline(aip_coronal_thresh)
            aip_sagittal_outline = create_outline(aip_sagittal_thresh)

            # Add the outlines to the AIPs
            aip_coronal_with_outline = aip_coronal.copy()
            aip_sagittal_with_outline = aip_sagittal.copy()
            aip_coronal_with_outline[aip_coronal_outline > 0] = aip_coronal_mean
            aip_sagittal_with_outline[aip_sagittal_outline > 0] = aip_sagittal_mean

            # Save the AIPs with outlines
            tifffile.imwrite(coronal_aip_outline_path, aip_coronal_with_outline.astype(np.uint16))
            tifffile.imwrite(sagittal_aip_outline_path, aip_sagittal_with_outline.astype(np.uint16))

            # Use ccd3d to find connected components in the thresholded AIPs
            labels_coronal = cc3d.connected_components(aip_coronal_thresh, connectivity=4) # each object will have a unique label
            labels_sagittal = cc3d.connected_components(aip_sagittal_thresh, connectivity=4)
            pixel_count_coronal = np.bincount(labels_coronal.ravel())[1:]  # Exclude background (label 0)
            pixel_count_sagittal = np.bincount(labels_sagittal.ravel())[1:]  # Exclude background (label 0)
            largest_label_coronal = np.argmax(pixel_count_coronal) + 1  # +1 to adjust for background label
            largest_label_sagittal = np.argmax(pixel_count_sagittal) + 1  # +1 to adjust for background label

            # Get the bounding box of the largest connected component
            stats_coronal = cc3d.statistics(labels_coronal)
            stats_sagittal = cc3d.statistics(labels_sagittal)
            largest_component_bbox_coronal = stats_coronal['bounding_boxes'][largest_label_coronal]
            largest_component_bbox_sagittal = stats_sagittal['bounding_boxes'][largest_label_sagittal]

            # bbox is (x_slice, y_slice, z_slice)
            y_slice, x_slice, _ = largest_component_bbox_coronal
            xmin, xmax = x_slice.start, x_slice.stop
            ymin, ymax = y_slice.start, y_slice.stop

            # Extract the sagittal bounding box coordinates
            y_slice, _, _ = largest_component_bbox_sagittal
            zmin, zmax = y_slice.start, y_slice.stop

            # Save the bounding box to a file
            with open(bbox_file, "w") as file:
                file.write(f"{zmin}:{zmax}, {ymin}:{ymax}, {xmin}:{xmax}")

            # Write the pad percentage to a file
            with open(pad_percent_txt, "w") as file:
                file.write(f"{args.pad_percent}")

            # Calculate padding based on the specified percentage
            pad_factor = 1 + 2 * args.pad_percent
            x_size = xmax - xmin
            y_size = ymax - ymin
            z_size = zmax - zmin
            pad_width_x = round(((x_size * pad_factor) - x_size) / 2)
            pad_width_y = round(((y_size * pad_factor) - y_size) / 2)
            pad_width_z = round(((z_size * pad_factor) - z_size) / 2)

            # Adjust the bounding box with padding
            xmin = max(0, xmin - pad_width_x)
            xmax = min(img.shape[2], xmax + pad_width_x)
            ymin = max(0, ymin - pad_width_y)
            ymax = min(img.shape[1], ymax + pad_width_y)
            zmin = max(0, zmin - pad_width_z)
            zmax = min(img.shape[0], zmax + pad_width_z)

            # Save the adjusted bounding box to a file
            with open(bbox_pad_file, "w") as file:
                file.write(f"{zmin}:{zmax}, {ymin}:{ymax}, {xmin}:{xmax}")

            # Crop/save the original 3D image using the bounding box
            img_cropped = img[zmin:zmax, ymin:ymax, xmin:xmax]
            save_as_tifs(img_cropped, output_cropped, ndarray_axis_order='zyx')

            progress.update(task_id, advance=1)


    verbose_end_msg()

if __name__ == "__main__":
    main()
