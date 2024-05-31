#!/usr/bin/env python3

import argparse
import os
import nibabel as nib
import numpy as np
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.argparse_utils import SuppressMetavar, SM
from unravel.config import Configuration
from unravel.img_io import load_3D_img, save_as_tifs
from unravel.img_tools import ilastik_segmentation
from unravel.utils import get_samples, initialize_progress_bar, print_cmd_and_times, print_func_name_args_times

def parse_args():
    parser = argparse.ArgumentParser(description="Run Ilastik's pixel classification workflow on a tif series", formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-ilp', '--ilastik_prj', help='path/ilastik_project.ilp', required=True, action=SM)
    parser.add_argument('-t', '--tifs_dir', help='path/input_dir_w_tifs', required=True, action=SM)
    parser.add_argument('-i', '--input', help='If path/input_dir_w_tifs does not exist, provide a rel_path/image to make it', action=SM)
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 1', default=1, type=int, metavar='')
    parser.add_argument('-o', '--output', help='output dir name', default=None, action=SM)
    parser.add_argument('-l', '--labels', help='List of segmetation label IDs to save as binary .nii.gz images. Default: 1', nargs='+', type=int, action=SM)
    parser.add_argument('-rmi', '--rm_in_tifs', help='Delete the dir w/ the input tifs (e.g., if a *.czi was the input)', action='store_true', default=False)
    parser.add_argument('-rmo', '--rm_out_tifs', help='Delete the dir w/ the output tifs', action='store_true', default=False)
    parser.add_argument('-log', '--ilastik_log', help='Show Ilastik log', action='store_true')
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = """Usage:
ilastik_segmentation.py -t cfos -o cfos_seg -ilp path/ilastik_project.ilp
ilastik_segmentation.py -i *.czi -t cfos -o cfos_seg -ilp path/ilastik_project.ilp

This script is for running Ilastik's pixel classification workflow in headless mode for each sample. 

To train an Ilastik project, organize training slices into folder (e.g., 3 slices from 3 samples per condition; copy_tifs.py can help).

Add the following the .bashrc or .zshrc (update the path and version): 
export PATH=/usr/local/ilastik-1.3.3post3-Linux:$PATH 
alias ilastik=run_ilastik.sh

Launch ilastik (e.g., by running: ilastik # if )
Pixel Classification -> save as <EXP>_rater1.ilp 
https://www.ilastik.org/documentation/pixelclassification/pixelclassification

1. Input Data 
   Drag training slices into ilastik GUI
   ctrl+A -> right click -> Edit shared properties -> Storage: Copy into project file -> Ok 

2. Feature Selection
   Select Features... -> select all features (control+a) or an optimized subset (faster but less accurate)
   (To choose a subset of features, initially select all [control+a], train, turn off Live Updates, click Suggest Features, select a subset, and train again) 

3. Training
   Double click yellow square -> click yellow rectangle (Color for drawing) -> click in triangle and drag to the right to change color to red -> ok
   Adjust brightness and contrast as needed (select gradient button and click and drag slowly in the image as needed; faster if zoomed in)
   Use control + mouse wheel scroll to zoom, press mouse wheel and drag image to pan
   With label 1 selected, paint on cells
   With label 2 selected, paint on background
   Turn on Live Update to preview pixel classification (faster if zoomed in) and refine training. 
   If label 1 fuses neighboring cells, draw a thin line in between them with label 2. 
   Toggle eyes show/hide layers and/or adjust transparency of layers. 
   s will toggle segmentation on and off.
   p will toggle prediction on and off.
   If you accidentally pressa and add an extra label, turn off Live Updates and press X to delete the extra label
   If you want to go back to steps 1 & 2, turn off Live Updates off
   ChangeCurrent view to see other training slices. Check segmentation for these and refine as needed.
   Save the project in experiment summary folder and close if using this script to run ilastik in headless mode for segmenting all images. 
"""
    return parser.parse_args()

# TODO: Consolidate ilastik_segmentation() in unravel_img_tools.py


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


def main():
    args = parse_args()

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            # Resolve path to sample folder
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            # Define output and skip processing if it already exists
            segmentation_dir = sample_path / args.output
            output_tif_dir = segmentation_dir / args.output
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
            ilastik_segmentation(str(input_tif_dir), str(args.ilastik_prj), str(output_tif_dir), ilastik_log=args.ilastik_log)

            # Convert each label to a binary mask and save as .nii.gz
            save_labels_as_masks(output_tif_dir, args.labels, segmentation_dir, args.output)

            # Remove input tifs if requested
            if args.rm_in_tifs: 
                Path(input_tif_dir).unlink()

            # Remove output tifs if requested
            if args.rm_out_tifs: 
                Path(output_tif_dir).unlink()

            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
