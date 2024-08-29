#!/usr/bin/env python3

"""
Use ``seg_ilastik`` from UNRAVEL to use a trained ilastik project (pixel classification) to segment features (e.g., c-Fos+ cells) in images.

Prereqs: 
    - Organize training tif slices (from ``seg_copy_tifs``) into a single folder.
    - Train an Ilastik project with the desired features (https://b-heifets.github.io/UNRAVEL/guide.html#train-an-ilastik-project).
    - Add training slices (tifs) into folder (e.g., 3 slices from 3 samples per condition).
    - ``seg_copy_tifs`` can aggregate these slices into a single folder for training.

Ilastik executable files for each OS:
    - Linux: /usr/local/ilastik-1.3.3post3-Linux/run_ilastik.sh
    - Mac: /Applications/Ilastik.app/Contents/ilastik-release/run_ilastik.sh
    - Windows: C:\\Program Files\\ilastik-1.3.3post3\\run_ilastik.bat

Note:
    - This module uses tifs for processing with Ilastik.
    - If your raw images are not tifs, use -i to make them from a .czi or another image format.

Usage if input tifs exist:
--------------------------
    seg_ilastik -ie path/ilastik_executable -ilp path/ilastik_project.ilp -t cfos -o cfos_seg [-l 1 2 3] [-rmo] [-d path/to/sample??] [-p sample??] [-v]

Usage if input tifs need to be created:
-----------------------------------------------------------------
    seg_ilastik -ie path/ilastik_executable -ilp path/ilastik_project.ilp -i <asterisk>.czi -o cfos_seg [-l 1 2 3] [-rmi] [-rmo] [-d path/to/sample??] [-p sample??] [-v]
"""

import os
import nibabel as nib
import numpy as np
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_rich_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_tifs
from unravel.core.img_tools import pixel_classification
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples, print_func_name_args_times, initialize_progress_bar


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-ie', '--ilastik_exe', help='path/ilastik_executable.', required=True, action=SM)
    reqs.add_argument('-ilp', '--ilastik_prj', help='path/ilastik_project.ilp', required=True, action=SM)
    reqs.add_argument('-t', '--tifs_dir', help='path/input_dir_w_tifs', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='output dir name', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help='If path/input_dir_w_tifs does not exist, provide a rel_path/image to make it', action=SM)
    opts.add_argument('-c', '--channel', help='.czi channel number (if this is the input image type). Default: 1', default=1, type=int, metavar='')
    opts.add_argument('-l', '--labels', help='List of segmetation label IDs to save as binary .nii.gz images. Default: 1', default=1, nargs='*', type=int, action=SM)
    opts.add_argument('-rmi', '--rm_in_tifs', help='Delete the dir w/ the input tifs (e.g., if a *.czi was the input)', action='store_true', default=False)
    opts.add_argument('-rmo', '--rm_out_tifs', help='Delete the dir w/ the output tifs. These have all labels. .nii.gz output(s) are smaller.', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Group args
# TODO: Test rich formating for help messages
# TODO: Consolidate -i and -t into one arg


def count_files(directory):
    """Count the number of files in a directory, excluding subdirectories."""
    return sum(1 for entry in os.scandir(directory) if entry.is_file())

@print_func_name_args_times()
def save_labels_as_masks(tif_dir, labels, segmentation_dir, output_name):
    img = load_3D_img(tif_dir) 
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

            # Define output and skip processing if it already exists
            segmentation_dir = sample_path / args.output
            output_tif_dir = segmentation_dir / args.output
            if not isinstance(args.labels, list):
                args.labels = [args.labels]
            last_label = args.labels[-1]
            final_output = segmentation_dir.joinpath(f"{args.output}_{last_label}.nii.gz")
            if final_output.exists():
                print(f"\n\n    {final_output.name} already exists. Skipping.\n")
                continue
            
            # Define path to input tifs and create them if they don't exist
            input_tif_dir = sample_path / args.tifs_dir
            if not input_tif_dir.exists():
                img_path = next(sample_path.glob(str(args.input)), None)
                img = load_3D_img(img_path, channel=args.channel) 
                save_as_tifs(img, input_tif_dir)

            # Perform pixel classification and output segmented tifs to output dir
            output_tif_dir.mkdir(exist_ok=True, parents=True)
            pixel_classification(str(input_tif_dir), str(args.ilastik_prj), str(output_tif_dir), args.ilastik_exe)

            # Convert each label to a binary mask and save as .nii.gz
            save_labels_as_masks(output_tif_dir, args.labels, segmentation_dir, args.output)

            # Remove input tifs if requested
            if args.rm_in_tifs: 
                Path(input_tif_dir).unlink()

            # Remove output tifs if requested
            if args.rm_out_tifs: 
                Path(output_tif_dir).unlink()

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()