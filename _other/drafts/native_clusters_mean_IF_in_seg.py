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
from unravel.core.img_io import load_3D_img
from unravel.core.utils import print_cmd_and_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='For each cluster, load cropped <ochann>, cluster mask, and <*_seg_ilastik_1> and mul together to measure mean IF in segmented voxels', formatter_class=SuppressMetavar)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', action=SM)
    parser.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, action=SM)
    parser.add_argument('-c', '--clusters_dir', help='Path relative to sample?? with cluster data: clusters/<output_dir>', action=SM)
    parser.add_argument('-i', '--input_dir', help='Dir in <output_dir> with cropped immunofluo images', action=SM)
    parser.add_argument('-s', '--seg_dir', help='Dir in <output_dir> with cropped segmentation image', action=SM)
    parser.add_argument('-o', '--out_dir', help='Output dir prefix (e.g., th_seg_ilastik_3)', action=SM)
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = """
Example usage: native_clusters_mean_IF_in_seg.py -c clusters/output_folder -i iba1_rb20_cropped -s iba1_seg_ilastik_1/sample03_iba1_seg_ilastik_1.nii.gz_cropped -o th_seg_ilastik_3 -v

-o glm_iba1_rb20_cbsMeth_v_meth_18000p_vox_p_tstat1_FDR0.2_MinCluster100 -cn iba1_rb20 -s iba1_seg_ilastik_1 -v

Run native_clusters_mean_IF_in_seg.py from the experiment directory containing sample?? folders or a sample?? folder.

Version 2 allows for more flexibility (e.g., use seg from one label as a mask for another label), but paths in args more complex.
"""
    return parser.parse_args()

def binarize(array, threshold=0.5):
    return (array > threshold).astype(int)

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

            # Define input path
            clusters_dir_path = Path(sample_path, args.clusters_dir).resolve()
                
            # Define path to bounding box directory
            bbox_dir = Path(clusters_dir_path, "bounding_boxes")

            # Get cluster IDs
            file_pattern = str(Path(bbox_dir, f"bounding_box_{sample}_cluster_*.txt")) # Define the pattern to match the file names
            file_list = glob(file_pattern) # Use glob to find files matching the pattern            
            clusters = [int(re.search(r"cluster_(\d+).txt", file).group(1)) for file in file_list] # Extract cluster IDs
            for cluster in clusters:

                # Load cropped image (e.g., iba1_rb20_cropped)
                cropped_img_path = Path(clusters_dir_path, args.input_dir, f"{sample}_cluster_{cluster}.nii.gz")
                cropped_img = load_3D_img(cropped_img_path, return_res=False)

                # Load cropped cluster
                cropped_cluster_path = Path(clusters_dir_path, f"clusters_cropped", f"crop_{sample}_native_cluster_{cluster}.nii.gz")
                cropped_cluster_img = load_3D_img(cropped_cluster_path, return_res=False)

                # Load segmentation (e.g., iba1_seg_ilastik_1/sample03_iba1_seg_ilastik_1.nii.gz_cropped)
                seg_img_path = Path(clusters_dir_path, args.seg_dir, f"{sample}_cluster_{cluster}.nii.gz")
                seg_img = load_3D_img(seg_img_path, return_res=False)

                # Binarize the arrays
                cropped_cluster_img = binarize(cropped_cluster_img)
                seg_img = binarize(seg_img)

                # Multiply the binarized arrays
                seg_cluster_mask = cropped_cluster_img * seg_img

                # Calculate and save the mean fluo intensity of voxels within the cluster that were segmented
                mean_intensity = np.mean(cropped_img[seg_cluster_mask > 0])

                # Save mean intensity to .txt
                output_dir_path = Path(clusters_dir_path, f"{args.out_dir}_cropped", "3D_counts", f"crop_{args.out_dir}_{sample}_native_cluster_{cluster}_3dc")
                output = Path(output_dir_path,f"crop_{args.out_dir}_{sample}_native_cluster_{cluster}_mean_IF_in_seg.txt") 
                with open(output, 'w') as f:
                    f.write(f"{mean_intensity}")

                # Save image paths to .txt
                output = Path(output_dir_path,f"crop_{args.out_dir}_{sample}_native_cluster_{cluster}_mean_IF_in_seg_parameters.txt") 
                with open(output, 'w') as f:
                    f.write(f"cropped_img_path: {cropped_img_path} \nseg_img_path: {seg_img_path}")

                print(f'\n    Mean {args.input_dir} intensity in {sample} cluster_{cluster} {args.seg_dir}: {mean_intensity}\n')

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
