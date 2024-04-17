#!/usr/bin/env python3

import argparse
import pandas as pd
import subprocess
import numpy as np
import nibabel as nib
from fsl.wrappers import cluster
from fsl.data.image import Image
from pathlib import Path
from rich import print
from rich.traceback import install

from argparse_utils import SM, SuppressMetavar
from unravel_config import Configuration
from unravel_utils import print_cmd_and_times, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(description='Run GLM using FSL randomise.', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/p_value_map.nii.gz', required=True, action=SM)
    parser.add_argument('-mas', '--mask', help='path/mask.nii.gz', required=True, action=SM)
    parser.add_argument('-q', '--q_value', help='Q-value for FDR correction', required=True, type=float, action=SM)
    parser.add_argument('-ms', '--min_size', help='Min cluster size in voxels. Default: 100', default=100, type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity', default=False, action='store_true')
    parser.epilog = """Usage:    fdr.py -mas path/mask.nii.gz -v
    
Inputs: 
    - *vox_p_*stat*.nii.gz from glm.py
"""
    return parser.parse_args()

@print_func_name_args_times()
def fdr_correction(input_path, mask_path, q_value):
    # Define the command as you would use in the terminal
    adjusted_pval_output_path = f"{input_path[:-7]}__FDR-adjusted_p_values__q{q_value}.nii.gz"
    output_thresh = f"{input_path[:-7]}__thresholded_p_values__q{q_value}.nii.gz"

    # Building the fdr command
    fdr_command = [
        'fdr', 
        '-i', input_path, 
        '--oneminusp', 
        '-m', mask_path, 
        '-q', str(q_value),
        '--othresh', output_thresh,
        '-a', adjusted_pval_output_path
    ]

    result = subprocess.run(fdr_command, capture_output=True, text=True)    
    if result.returncode != 0:
        raise Exception(f"Error in FDR correction: {result.stderr}")
    print(result.stdout)
    probability_threshold = result.stdout.strip().split()[-1]
    return adjusted_pval_output_path, float(probability_threshold)

@print_func_name_args_times()
def reverse_clusters(cluster_index_path):
    # Load cluster index image
    cluster_index_nii = nib.load(cluster_index_path)
    cluster_index_img = np.asanyarray(cluster_index_nii.dataobj, dtype=cluster_index_nii.header.get_data_dtype()).squeeze()
    max_cluster_id = int(cluster_index_img.max())
    
    # Prepare output data array
    rev_cluster_index_img = np.zeros_like(cluster_index_img)
    
    # Reassign cluster IDs in reverse order
    for cluster_id in range(1, max_cluster_id + 1):
        rev_cluster_index_img[cluster_index_img == cluster_id] = max_cluster_id - cluster_id + 1
    
    # Save the new cluster index image
    rev_cluster_index_nii = nib.Nifti1Image(rev_cluster_index_img, cluster_index_nii.affine, cluster_index_nii.header)
    nib.save(rev_cluster_index_nii, cluster_index_path.replace("cluster_index.nii.gz", "rev_cluster_index.nii.gz"))


def main():

    cwd = Path().cwd()
    image_name = Path(args.input).name
    fdr_dir_name = f"{image_name[:-7]}_q{args.q_value}"
    fdr_path = cwd / fdr_dir_name

    if Path(fdr_path, f"{fdr_dir_name}_rev_cluster_index.nii.gz").exists():
        print("FDR-adjusted and reversed cluster index images exist, skipping...")
        return
    
    fdr_path.mkdir(exist_ok=True, parents=True)

    # Save the min cluster size to a .txt file
    with open(fdr_path / "min_cluster_size.txt", "w") as f:
        f.write(str(args.min_size))

    # FDR Correction
    try:
        adjusted_pval_output_path, probability_threshold = fdr_correction(args.input, args.mask, args.q_value)
    except Exception as e:
        print(str(e))

    # Save the probability threshold and the 1-P threshold to a .txt file
    with open(fdr_path / "p_value_threshold.txt", "w") as f:
        f.write(str(probability_threshold))
    with open(fdr_path / "1-p_value_threshold.txt", "w") as f:
        f.write(str(1 - probability_threshold))

    # Cluster analysis
    adjusted_pval_nii = nib.load(adjusted_pval_output_path)
    one_minus_p_thresh = 1 - probability_threshold
    data, titles, result = cluster(
        adjusted_pval_nii,
        args.q_value,
        load=True,
        minextent=int(args.min_size),
        oindex=f"{fdr_path}/{fdr_dir_name}_cluster_index.nii.gz"
    )

    df = pd.DataFrame(data, columns=titles)
    print(df)
    df.to_csv(fdr_path / f"{fdr_dir_name}_cluster_info.csv", index=False)

    # Save the cluster index
    for key, value in result.items():
        if isinstance(value, Image):
            nib.save(value, f"{fdr_path}/{fdr_dir_name}_{key}.nii.gz")

    # Reverse cluster ID order in cluster_index
    reverse_clusters(fdr_path / f"{fdr_path}/{fdr_dir_name}_cluster_index.nii.gz")


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()