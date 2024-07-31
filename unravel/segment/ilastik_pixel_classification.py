#!/usr/bin/env python3

"""
Use ``seg_ilastik`` from UNRAVEL to run a trained ilastik project (pixel classification) to segment features in images.

Usage:
------
    seg_ilastik -ie <path/ilastik_executable> -t cfos -o cfos_seg -ilp path/ilastik_project.ilp
    seg_ilastik -ie <path/ilastik_executable> -i <asterisk>.czi -o cfos_seg -ilp path/ilastik_project.ilp

To train an Ilastik project, organize training slices into folder (e.g., 3 slices from 3 samples per condition; ``seg_copy_tifs`` can help).

For info on training, see: https://b-heifets.github.io/UNRAVEL/guide.html#train-an-ilastik-project  
"""

import argparse
import os
import nibabel as nib
import numpy as np
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_tifs
from unravel.core.img_tools import pixel_classification
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples, print_func_name_args_times, initialize_progress_bar


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-ie', '--ilastik_exe', help='path/ilastik_executable.', required=True, action=SM)
    parser.add_argument('-ilp', '--ilastik_prj', help='path/ilastik_project.ilp', required=True, action=SM)
    parser.add_argument('-t', '--tifs_dir', help='path/input_dir_w_tifs', required=True, action=SM)
    parser.add_argument('-i', '--input', help='If path/input_dir_w_tifs does not exist, provide a rel_path/image to make it', action=SM)
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 1', default=1, type=int, metavar='')
    parser.add_argument('-o', '--output', help='output dir name', default=None, action=SM)
    parser.add_argument('-l', '--labels', help='List of segmetation label IDs to save as binary .nii.gz images. Default: 1', default=1, nargs='+', type=int, action=SM)
    parser.add_argument('-rmi', '--rm_in_tifs', help='Delete the dir w/ the input tifs (e.g., if a *.czi was the input)', action='store_true', default=False)
    parser.add_argument('-rmo', '--rm_out_tifs', help='Delete the dir w/ the output tifs', action='store_true', default=False)
    parser.add_argument('-log', '--ilastik_log', help='Show Ilastik log', action='store_true')
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: Consolidate pixel_segmentation() in unravel/core/img_tools.py


def count_files(directory):
    """Count the number of files in a directory, excluding subdirectories."""
    return sum(1 for entry in os.scandir(directory) if entry.is_file())

@print_func_name_args_times()
def save_labels_as_masks(tif_dir, labels, segmentation_dir, output_name):
    img = load_3D_img(tif_dir) 
    for label in labels:
        print(f"\n    Converting label {label} to mask and saving as .nii.gz in {segmentation_dir}\n")
        label_img = (img == label).astype(np.uint8)
        nifti_img = nib.Nifti1Image(label_img, np.eye(4))
        nib.save(nifti_img, segmentation_dir.joinpath(f"{output_name}_{label}.nii.gz"))


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            # Resolve path to sample folder
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

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