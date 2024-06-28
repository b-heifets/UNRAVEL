#!/usr/bin/env python3

"""
Use ``cluster_fdr`` from UNRAVEL to perform FDR correction on a 1 - p value map to define clusters.

Usage
-----
    cluster_fdr -i path/vox_p_tstat1.nii.gz -mas path/mask.nii.gz -q 0.05

Inputs: 
    - p value map (e.g., <asterisk>vox_p_<asterisk>stat<asterisk>.nii.gz from vstats)    

Outputs saved in the output directory:
    - FDR-adjusted p value map
    - Cluster information CSV
    - Reversed cluster index image (output_dir/input_name_rev_cluster_index.nii.gz)
    - min_cluster_size_in_voxels.txt
    - p_value_threshold.txt
    - 1-p_value_threshold.txt

Cluster IDs are reversed in the cluster index image so that the largest cluster is 1, the second largest is 2, etc.

Making directional cluster indices from non-directional p value maps output from ANOVAs: 
    - Provide the average immunostaining intensity images for each group being contrasted (``img_avg``)
    - The --output needs to have <group1>_v_<group2> in the name
    - _v_ will be replaced with _gt_ or _lt_ based on the effect direction 
    - The cluster index will be split accoding to the effect directions
    - ``cluster_fdr`` -i vox_p_fstat1.nii.gz -mas mask.nii.gz -q 0.05 -a1 group1_avg.nii.gz -a2 group2_avg.nii.gz -o stats_info_g1_v_g2 -v

For bilateral data processed with a hemispheric mask, next run ``cluster_mirror_indices`` to mirror the cluster indices to the other hemisphere.

For unilateral data or bilateral data processed with a whole brain mask, the cluster indices are ready for validation with ``cluster_validation``.
"""

import argparse
import concurrent.futures
import subprocess
import numpy as np
import nibabel as nib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SM, SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/p_value_map.nii.gz', required=True, action=SM)
    parser.add_argument('-mas', '--mask', help='path/mask.nii.gz', required=True, action=SM)
    parser.add_argument('-q', '--q_value', help='Space-separated list of FDR q values', required=True, nargs='*', type=float, action=SM)
    parser.add_argument('-ms', '--min_size', help='Min cluster size in voxels. Default: 100', default=100, type=int, action=SM)
    parser.add_argument('-o', '--output', help='Output directory. Default: input_name_q{args.q_value}"', default=None, action=SM)
    parser.add_argument('-a1', '--avg_img1', help='path/averaged_immunofluo_group1.nii.gz for spliting the cluster index based on effect direction', action=SM)
    parser.add_argument('-a2', '--avg_img2', help='path/averaged_immunofluo_group2.nii.gz for spliting the cluster index based on effect direction', action=SM)
    parser.add_argument('-th', '--threads', help='Number of threads. Default: 10', default=10, type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity', default=False, action='store_true')
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: could add optional args like in ``vstats`` for running the ``cluster_fdr`` command. 

@print_func_name_args_times()
def fdr(input_path, fdr_path, mask_path, q_value):
    """Perform FDR correction on the input p value map using a mask.
    
    Args:
        - input_path (str): the path to the p value map
        - fdr_path (str): the path to the output directory
        - mask_path (str): the path to the mask
        - q_value (float): the q value for FDR correction

    Saves in the fdr_path:
        - FDR-adjusted p value map

    Returns:
        - adjusted_pval_output_path (str): the path to the FDR-adjusted p value map 
        - probability_threshold (float): the probability threshold for the FDR correction
        """

    prefix = str(Path(input_path).name).replace('.nii.gz', '')
    adjusted_pval_output_path = fdr_path / f"{prefix}_q{q_value}_adjusted_p_values.nii.gz"

    fdr_command = [
        'fdr', 
        '-i', str(input_path), 
        '--oneminusp', 
        '-m', str(mask_path), 
        '-q', str(q_value),
        '-a', str(adjusted_pval_output_path)
    ]

    result = subprocess.run(fdr_command, capture_output=True, text=True)    
    if result.returncode != 0:
        raise Exception(f"Error in FDR correction: {result.stderr}")
    print(result.stdout)
    probability_threshold = result.stdout.strip().split()[-1]
    print(f'[default]1-p Threshold is:[/]\n{1-float(probability_threshold)}')

    return adjusted_pval_output_path, float(probability_threshold)

@print_func_name_args_times()
def cluster_index(adj_p_val_img_path, min_size, q_value, output_index):

    print('')
    thres = 1 - float(q_value)

    command = [
        'cluster',
        '-i', adj_p_val_img_path,
        '-t', str(thres),
        '--oindex=' + str(output_index),
        '--minextent=' + str(min_size)
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print("Error:", result.stderr)
    else:
        print("Output:", result.stdout)
    return result.stdout


@print_func_name_args_times()
def reverse_clusters(cluster_index_img, output, data_type, cluster_index_nii):
    """Reverse the cluster IDs in a cluster index image (ndarray). Return the reversed cluster index ndarray."""
    max_cluster_id = int(cluster_index_img.max())
    rev_cluster_index_img = np.zeros_like(cluster_index_img)
    
    # Reassign cluster IDs in reverse order
    for cluster_id in range(1, max_cluster_id + 1):
        rev_cluster_index_img[cluster_index_img == cluster_id] = max_cluster_id - cluster_id + 1

    rev_cluster_index_img = rev_cluster_index_img.astype(data_type)
    rev_cluster_index_nii = nib.Nifti1Image(rev_cluster_index_img, cluster_index_nii.affine, cluster_index_nii.header)
    rev_cluster_index_nii.set_data_dtype(data_type)
    nib.save(rev_cluster_index_nii, output)
    
    return rev_cluster_index_img

@print_func_name_args_times()
def split_clusters_based_on_effect(rev_cluster_index_img, avg_img1, avg_img2, output, max_cluster_id, data_type, cluster_index_nii):
    if avg_img1 and avg_img2: 
        if Path(avg_img1).exists() and Path(avg_img2).exists():
            print("\n    Splitting the rev_cluster_index into 2 parts (group 1 > group 2 and group 1 < group 2)\n")
            avg_img1 = nib.load(avg_img1)
            avg_img2 = nib.load(avg_img2)
            avg_img1_data = np.asanyarray(avg_img1.dataobj, dtype=avg_img1.header.get_data_dtype()).squeeze()
            avg_img2_data = np.asanyarray(avg_img2.dataobj, dtype=avg_img2.header.get_data_dtype()).squeeze()

            # Create a dict w/ mean intensities in each cluster for each group
            cluster_means = {}
            for cluster_id in range(1, max_cluster_id + 1):
                cluster_mask = rev_cluster_index_img == cluster_id
                cluster_means[cluster_id] = {
                    "group1": avg_img1_data[cluster_mask].mean(),
                    "group2": avg_img2_data[cluster_mask].mean()
                }

            # Make two new cluster index images based on the effect directions (group1 > group2, group2 > group1)
            img_g1_gt_g2 = np.zeros_like(rev_cluster_index_img, dtype=data_type)
            img_g1_lt_g2 = np.zeros_like(rev_cluster_index_img, dtype=data_type)
            for cluster_id, means in cluster_means.items():
                if means["group1"] > means["group2"]:
                    img_g1_gt_g2[rev_cluster_index_img == cluster_id] = cluster_id
                else:
                    img_g1_lt_g2[rev_cluster_index_img == cluster_id] = cluster_id

            # Save the new cluster index images
            rev_cluster_index_g1_gt_g2 = nib.Nifti1Image(img_g1_gt_g2, cluster_index_nii.affine, cluster_index_nii.header)
            rev_cluster_index_g1_lt_g2 = nib.Nifti1Image(img_g1_lt_g2, cluster_index_nii.affine, cluster_index_nii.header)
            rev_cluster_index_g1_gt_g2.set_data_dtype(data_type)
            rev_cluster_index_g1_lt_g2.set_data_dtype(data_type)
            nib.save(rev_cluster_index_g1_gt_g2, output.parent / str(output.name).replace('_v_', '_gt_'))
            nib.save(rev_cluster_index_g1_lt_g2, output.parent / str(output.name).replace('_v_', '_lt_'))
        else: 
            print(f"\n [red]The specified average image files do not exist.")
            import sys ; sys.exit()


@print_func_name_args_times()
def process_fdr_and_clusters(input, mask, q, min_size, avg_img1, avg_img2, output=None):
    """Process FDR correction and cluster index generation for a given q value."""
    if output is None:
        fdr_dir_name = f"{Path(input).name[:-7]}_q{q}"
    else:
        fdr_dir_name = f"{output}_q{q}"
    fdr_path = Path(input).parent / fdr_dir_name
    output = Path(fdr_path, f"{fdr_dir_name}_rev_cluster_index.nii.gz")
    if output.exists():
        return "The FDR-corrected reverse cluster index exists, skipping..."
    fdr_path.mkdir(exist_ok=True, parents=True)

    # Perform FDR Correction
    adjusted_pval_output_path, probability_threshold = fdr(input, fdr_path, mask, q)

    # Save the probability threshold and the 1-P threshold to a .txt file
    with open(fdr_path / "p_value_threshold.txt", "w") as f:
        f.write(f"{probability_threshold}\n")
    with open(fdr_path / "1-p_value_threshold.txt", "w") as f:
        f.write(f"{1 - probability_threshold}\n")

    # Save the min cluster size to a .txt file
    with open(fdr_path / "min_cluster_size_in_voxels.txt", "w") as f:
        f.write(f"{min_size}\n")

    # Generate cluster index
    cluster_index_path = f"{fdr_path}/{fdr_dir_name}_cluster_index.nii.gz"
    cluster_info = cluster_index(adjusted_pval_output_path, min_size, q, cluster_index_path)

    # Save the cluster info
    with open(fdr_path / f"{fdr_dir_name}_cluster_info.txt", "w") as f:
        f.write(cluster_info)

    # Load the cluster index and convert to an ndarray
    cluster_index_nii = nib.load(cluster_index_path)
    cluster_index_img = np.asanyarray(cluster_index_nii.dataobj, dtype=np.uint16).squeeze()

    # Lower the data type if the max cluster ID is less than 256 
    max_cluster_id = int(cluster_index_img.max())
    data_type = np.uint16 if max_cluster_id >= 256 else np.uint8
    cluster_index_img = cluster_index_img.astype(data_type)

    # Reverse cluster ID order in cluster_index and save it
    rev_cluster_index_img = reverse_clusters(cluster_index_img, output, data_type, cluster_index_nii)

    # Split the cluster index based on the effect directions
    split_clusters_based_on_effect(rev_cluster_index_img, avg_img1, avg_img2, output, max_cluster_id, data_type, cluster_index_nii)

    # Remove the original cluster index file
    Path(cluster_index_path).unlink()

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Prepare directory paths and outputs
    results = []
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        future_to_q = {
            executor.submit(process_fdr_and_clusters, args.input, args.mask, q, args.min_size, args.avg_img1, args.avg_img2, args.output): q
            for q in args.q_value
        }
        
        for future in concurrent.futures.as_completed(future_to_q):
            q_value = future_to_q[future]
            try:
                result = future.result()
                results.append((q_value, result))
            except Exception as exc:
                print(f'{q_value} generated an exception: {exc}')

    verbose_end_msg()
    

if __name__ == '__main__':
    main()