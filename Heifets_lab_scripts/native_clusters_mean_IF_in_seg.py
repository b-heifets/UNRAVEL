#!/usr/bin/env python3

import argparse
from argparse import RawTextHelpFormatter
from glob import glob
from pathlib import Path
import re
import numpy as np
from rich import print
from rich.live import Live
from rich.traceback import install
from unravel_config import Configuration
from unravel_img_tools import load_3D_img
from unravel_utils import print_cmd_and_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Crop native image based on cluster bounding boxes', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, metavar='')
    parser.add_argument('-i', '--input', help='<path/fluo_image> if inputs is .czi or .nii.gz: path/raw_image (otherwise the tif dir mattching -cn is used)', default=None, metavar='')
    parser.add_argument('-o', '--out_dir_name', help="Output folder name. If supplied as path (./sample??/clusters/output_folder), the basename will be used", metavar='')
    parser.add_argument('-cn', '--chann_name', help='Channel name (e.g., cfos or cfos_rb4). Default: ochann', default='ochann', metavar='')
    parser.add_argument('-s', '--seg_dir', help='Name of segmentation dir (e.g., cfos_seg_ilastik_1)', metavar='')
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = """
usage: native_clusters_mean_IF_in_seg.py -o glm_iba1_rb20_cbsMeth_v_meth_18000p_vox_p_tstat1_FDR0.2_MinCluster100 -cn iba1_rb20 -s iba1_seg_ilastik_1 -v

First run native_clusters_crop.py to crop fluo images for each cluster.

Currently, inputs are from native_clusters.sh
Run native_cluster_crop.py from the experiment directory containing sample?? folders or a sample?? folder.
inputs: ./sample??/clusters/output_folder/bounding_boxes/outer_bounds.txt and ./sample??/clusters/output_folder/bounding_boxes/bounding_box_sample??_cluster_*.txt
outputs: ./reg_input/autofl_*um_tifs_ilastik_brain_seg/slice_????.tif series, ./reg_input/autofl_*um_brain_mask.nii.gz, and ./reg_input/autofl_*um_masked.nii.gz

next script: cluser_mean_IF_in_seg.sh
"""
    return parser.parse_args()


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

            # Define output path
            output_dir = Path(sample_path, "clusters", args.out_dir_name, f"{args.chann_name}_cropped").resolve()
                
            # Define path to bounding box directory
            bbox_dir = Path(sample_path, "clusters", args.out_dir_name, "bounding_boxes").resolve()

            # Get cluster IDs
            file_pattern = str(Path(bbox_dir, f"bounding_box_{sample}_cluster_*.txt")) # Define the pattern to match the file names
            file_list = glob(file_pattern) # Use glob to find files matching the pattern            
            clusters = [int(re.search(r"cluster_(\d+).txt", file).group(1)) for file in file_list] # Extract cluster IDs
            for cluster in clusters:

                # Load cropped image
                cropped_img_path = Path(output_dir, f"{sample}_{args.chann_name}_cluster_{cluster}.nii.gz")
                cropped_img = load_3D_img(cropped_img_path, return_res=False)

                # Load segmentation
                seg_img_dir_path = Path(output_dir.parent, f"{args.seg_dir}_cropped", "3D_counts", f"crop_{args.seg_dir}_{sample}_native_cluster_{cluster}_3dc")
                seg_img_path = Path(seg_img_dir_path, f"crop_{args.seg_dir}_{sample}_native_cluster_{cluster}.nii.gz")
                seg_img = load_3D_img(seg_img_path, return_res=False)

                # Calculate and save the mean fluo intensity of voxels within the cluster that were segmented
                mean_intensity = np.mean(cropped_img[seg_img > 0])
                output = Path(seg_img_dir_path,f"crop_{args.seg_dir}_{sample}_native_cluster_{cluster}_mean_IF_in_seg.txt") 
                with open(output, 'w') as f:
                    f.write(f"{mean_intensity}")
                print(f'\n    Mean {args.chann_name} intensity in {sample} {cluster} {args.seg_dir}: {mean_intensity}\n')

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()