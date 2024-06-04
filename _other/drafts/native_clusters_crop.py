#!/usr/bin/env python3

import argparse
from glob import glob
from pathlib import Path
import re
import numpy as np
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_nii
from unravel.core.img_tools import crop
from unravel.core.utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples, load_text_from_file


def parse_args():
    parser = argparse.ArgumentParser(description='Crop native image based on cluster bounding boxes', formatter_class=SuppressMetavar)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', action=SM)
    parser.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='If if inputs is .czi or .nii.gz: path/raw_image (otherwise the tif dir mattching -cn is used)', default=None, action=SM)
    parser.add_argument('-o', '--out_dir_name', help="Output folder name. If supplied as path (./sample??/clusters/output_folder), the basename will be used", action=SM)
    parser.add_argument('-cn', '--chann_name', help='Channel name (e.g., cfos or cfos_rb4). Default: ochann', default='ochann', action=SM)
    parser.add_argument('-x', '--xy_res', help='xy resolution in um', type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='z resolution in um', type=float, action=SM)
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = """
Currently, inputs are from native_clusters.sh
Run native_cluster_crop.py from the experiment directory containing sample?? folders or a sample?? folder.
Example usage: native_cluster_crop.py -o clusters_output_folder_name -cn ochann -x 3.5232 -z 5 -v
inputs: ./sample??/clusters/output_folder/bounding_boxes/outer_bounds.txt and ./sample??/clusters/output_folder/bounding_boxes/bounding_box_sample??_cluster_*.txt
outputs: ./sample??/clusters/output_folder/<chann_name>_cropped/<sample>_cluster_*.nii.gz"""
    return parser.parse_args()


@print_func_name_args_times()
def calculate_native_bbox(outer_bbox_text, inner_bbox_text):

    outer_bbox = [list(map(int, dim.split(':'))) for dim in outer_bbox_text.split(', ')]
    inner_bbox = [list(map(int, dim.split(':'))) for dim in inner_bbox_text.split(', ')]
    
    native_bbox = [[outer_start + inner_start, outer_start + inner_end] 
                    for (outer_start, _), (inner_start, inner_end) in zip(outer_bbox, inner_bbox)]

    # Convert to string
    x_start, x_end = native_bbox[0]
    y_start, y_end = native_bbox[1]
    z_start, z_end = native_bbox[2]
    native_bbox = f"{x_start}:{x_end}, {y_start}:{y_end}, {z_start}:{z_end}"    

    return native_bbox


def main():
    args = parse_args()

    samples = get_samples(args.dirs, args.pattern)

    if samples == ['.']:
        samples[0] = Path.cwd().name

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            # Resolve path to tif directory
            cwd = Path(".").resolve()

            sample_path = Path(sample).resolve() if sample != cwd.name else Path().resolve()

            if args.input:
                input_path = Path(args.input).resolve()
            else:
                input_path = Path(sample_path, args.chann_name).resolve()

            # Load image
            if args.xy_res is None or args.z_res is None:
                img, xy_res, z_res = load_3D_img(input_path, return_res=True)
            else:
                img = load_3D_img(input_path, return_res=False)
                xy_res, z_res = args.xy_res, args.z_res

            # Define output path
            output_dir = Path(sample_path, "clusters", args.out_dir_name, f"{args.chann_name}_cropped").resolve()
                
            # Define path to bounding box directory
            bbox_dir = Path(sample_path, "clusters", args.out_dir_name, "bounding_boxes").resolve()

            # Load outer bounding box
            outer_bbox = load_text_from_file(Path(bbox_dir, f"outer_bounds.txt"))
            print(f'\n    {outer_bbox=}\n')

            # Load inner bounding boxes and crop image for each cluster
            file_pattern = str(Path(bbox_dir, f"bounding_box_{sample}_cluster_*.txt")) # Define the pattern to match the file names
            file_list = glob(file_pattern) # Use glob to find files matching the pattern            
            clusters = [int(re.search(r"cluster_(\d+).txt", file).group(1)) for file in file_list] # Extract cluster IDs
            for cluster in clusters:
                # Load bounding box
                cluster_bbox = load_text_from_file(Path(bbox_dir, f"bounding_box_{sample}_cluster_{cluster}.txt"))
                print(f'\n    bounding_box_{sample}_cluster_{cluster}.txt: {cluster_bbox=}\n')

                # Calculate native bounding box
                native_bbox = calculate_native_bbox(outer_bbox, cluster_bbox)
                print(f'\n{    native_bbox=}\n')

                # Crop image
                cropped_img = crop(img, native_bbox)

                # Save cropped image
                dtype = img.dtype
                output = Path(output_dir, f"{sample}_cluster_{cluster}.nii.gz")
                save_as_nii(cropped_img, output, xy_res, z_res, data_type=dtype)

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()