#!/usr/bin/env python3

"""
Use ``seg_ilastik`` (``si``) from UNRAVEL to use segment features of interest using Ilastik.

Prereqs: 
    - Organize training tifs into a folder (e.g., w/ ``seg_copy_tifs``) .
    - Train Ilastik (https://b-heifets.github.io/UNRAVEL/guide.html#train-an-ilastik-project).

Inputs:
    - ilastik_project: path/ilastik_project.ilp
    - Input: path/tif_dir or path/image (relative to current dir or sample??/)
    - Input image types: .tif, .czi, .nii.gz, .h5, .zarr
    - If glob is used, the first match is used.

Outputs:
    - seg_dir/seg_dir/`*`.tif series (segmented images; delete w/ --rm_out_tifs)
    - Optional: seg_dir/seg_dir_<label>.nii.gz (binary masks for each label specified w/ --labels)
    - Skips processing if output already exists (.nii.gz with --labels or .tif without)

Note:
    - Ilastik executable files for each OS (update path and version as needed):
    - Linux and WSL: /usr/local/ilastik-1.4.0.post1-Linux/run_ilastik.sh
    - Mac: /Applications/ilastik-1.4.0.post1-OSX.app/Contents/ilastik-release/run_ilastik.sh
    - Windows: C:\\Program Files\\ilastik-1.4.0.post1\\run_ilastik.bat

Usage:
------
    seg_ilastik -ie path/ilastik_executable -ilp path/ilastik_project.ilp -i <tif_dir or image> -o seg_dir [--labels 1 2 3] [--rm_out_tifs] [For .czi: --channel 1] [-d list of paths] [-p sample??] [-v]
"""

import os
import nibabel as nib
import numpy as np
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_tifs
from unravel.core.img_tools import pixel_classification
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples, print_func_name_args_times, initialize_progress_bar


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-ie', '--ilastik_exe', help='path/ilastik_executable.', required=True, action=SM)
    reqs.add_argument('-ilp', '--ilastik_prj', help='path/ilastik_project.ilp', required=True, action=SM)
    reqs.add_argument('-i', '--input', help='Relative path to dir with tifs or an image (.nii.gz, .h5, .zarr).', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='Output dir name', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-l', '--labels', help='Space-separated list of segmetation label IDs to save as 3D binary .nii.gz images', nargs='*', type=int, action=SM)
    opts.add_argument('-rmo', '--rm_out_tifs', help='Delete the dir w/ the output tifs. These have all labels. .nii.gz output(s) are smaller.', action='store_true', default=False)
    opts.add_argument('-c', '--channel', help='.czi channel number (if this is the input image type). Default: 1', default=1, type=int, metavar='')

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def count_files(directory):
    """Count the number of files in a directory, excluding subdirectories."""
    return sum(1 for entry in os.scandir(directory) if entry.is_file())

@print_func_name_args_times()
def save_labels_as_masks(tif_dir, labels, segmentation_dir, output_name, verbose=False):
    img = load_3D_img(tif_dir, verbose=verbose) 
    for label in labels:
        print(f"\n    Converting label {label} to binary mask and saving as .nii.gz in {segmentation_dir}\n")
        # img == label creates a boolean array where pixels equal to label are True (1) and all others are False (0).
        label_img = (img == label).astype(np.uint8)
        nifti_img = nib.Nifti1Image(label_img, np.eye(4))
        nib.save(nifti_img, segmentation_dir.joinpath(f"{output_name}_{label}.nii.gz"))


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

            # Define paths
            input_path = sample_path / args.input
            segmentation_dir = sample_path / args.output
            output_tif_dir = segmentation_dir / args.output

            img = None

            # Check for final output and skip if it already exists
            if args.labels is not None:
                labels = [label for label in args.labels]
            else:
                labels = []
            if labels:
                last_label = args.labels[-1]
                final_output = segmentation_dir / f"{args.output}_{last_label}.nii.gz"
                if final_output.exists():
                    print(f"\n\n    {final_output} already exists. Skipping.\n")
                    continue
            else:
                # No labels provided, so check if the output directory already contains the expected number of TIFFs
                if input_path.is_dir() and any(input_path.glob("*.tif")):
                    input_tif_dir = input_path
                    input_z_size = count_files(input_tif_dir)
                else:
                    # Load the image
                    matches = sorted(Path(sample_path).glob(args.input))
                    if not matches:
                        raise FileNotFoundError(f"No files matching '{args.input}' found in {sample_path}")
                    image_path = matches[0]  # Use the first match after sorting
                    if args.verbose:
                        print(f"    Using {image_path} as the input image.")
                    img = load_3D_img(image_path, channel=args.channel, verbose=args.verbose)
                    input_z_size = img.shape[2]

                # Count the number of TIFFs in the output directory
                if output_tif_dir.exists():
                    output_z_size = count_files(output_tif_dir)
                else:
                    output_z_size = 0
                
                # If the number of TIFFs in the output directory matches the number of TIFFs in the input directory, skip
                if input_z_size == output_z_size:
                    print(f"\n\n    {output_tif_dir} already contains {output_z_size} TIFFs. Skipping.\n")
                    continue
            
            # If input tifs do not exist, create them from another image format
            if input_path.is_dir() and any(input_path.glob("*.tif")):
                input_tif_dir = input_path
                remove_tmp_tifs = False
            else:
                remove_tmp_tifs = True
                input_tif_name = str(input_path.name).removesuffix(".czi").removesuffix(".nii.gz").removesuffix(".zarr").removesuffix(".h5")
                input_tif_dir = segmentation_dir / f"{input_tif_name}_tifs"
                save_as_tifs(img, input_tif_dir)

            # Perform pixel classification and output segmented tifs to output dir
            output_tif_dir.mkdir(exist_ok=True, parents=True)
            pixel_classification(str(input_tif_dir), str(args.ilastik_prj), str(output_tif_dir), args.ilastik_exe)

            # Convert each label to a binary mask and save as .nii.gz if labels are provided
            if labels:
                save_labels_as_masks(output_tif_dir, args.labels, segmentation_dir, args.output, verbose=args.verbose)

            # Remove input TIFFs if they were created just for pixel_classification()
            if remove_tmp_tifs:
                Path(input_tif_dir).unlink()

            # Remove output TIFFs if requested
            if args.rm_out_tifs:
                Path(output_tif_dir).unlink()

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()