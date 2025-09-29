#!/usr/bin/env python3

"""
Run ``ez_thr.py`` from UNRAVEL to threshold a statistical map (e.g., tstat or zstat) using FSL's easythresh function.

Note:
    - Run this script from the same directory as the input image.

Inputs:
    - path/vox_p_tstat1.nii.gz (1-p value map from ``vstats``)
    - path/mask.nii.gz (optional mask to limit the thresholding)

Outputs:
    - path/vox_p_tstat1_ezThr<z_thresh>/ directory with:
        - vox_p_tstat1_ezThr<z_thresh>_thresh.nii.gz (voxel-wise thresholded image)
        - vox_p_tstat1_ezThr<z_thresh>_rev_cluster_index.nii.gz (reversed cluster index image)
        - vox_p_tstat1_ezThr<z_thresh>_cluster_info.txt (cluster info text file)

This script runs the /usr/local/fsl/bin/easythresh

z thresh = p thresh (two-tailed) 
1.959964 = 0.05 
2.241403 = 0.025 
2.575829 = 0.01 
2.807034 = 0.005 
3.290527 = 0.001 
3.890593 = 0.0001
https://www.gigacalculator.com/calculators/p-value-to-z-score-calculator.php

0.05 for cluster_prob_thresh means <5% chance that resulting clusters are due to chance.
This accounts for spatial resolution, smoothness, etc..., to determine a min size cluster meeting these criteria

FSL's easythresh function estimates smoothness of z-scored image and uses this for GRF-based cluster correction: 
https://www.freesurfer.net/pub/dist/freesurfer/tutorial_packages/OSX/fsl_501/bin/easythresh
https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/Cluster

Usage:
------
    ez_thr.py -i path/vox_p_tstat1.nii.gz [-mask path/mask.nii.gz] [-z 1.959964] [-p 0.05] [-o path/vox_p_tstat1_thr.nii.gz] [-v]

"""

from subprocess import run
import numpy as np
import nibabel as nib
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.img_io import load_nii
from unravel.cluster_stats.fdr import reverse_clusters
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, print_func_name_args_times


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help="path/1-p_value_map.nii.gz (e.g., vox_p_tstat1 from ``vstats``)", required=True, action=SM)
    reqs.add_argument('-mas', '--mask', help='path/mask.nii.gz to limit the thresholding', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-z', '--z_thresh', help='Z-threshold for voxel-wise thresholding (default: 1.959964 for p<0.05, two-tailed)', default=1.959964, type=float, action=SM)
    opts.add_argument('-p', '--cluster_prob_thresh', help='Cluster probability threshold (default: 0.05)', default=0.05, type=float, action=SM)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()

    image_path = Path(args.input).resolve()
    image = image_path.name
    parent = image_path.parent
    results_dir = parent / f"{image[:-7]}_ezThr{args.z_thresh}"

    rev_cluster_index = results_dir / f"{results_dir.name}_rev_cluster_index.nii.gz"

    if not rev_cluster_index.exists():
        print(f"\nConverting p-values to z-value and running easythresh for {args.input}")

        results_dir.mkdir(parents=True, exist_ok=True)

        # Make empty image
        empty = results_dir / "empty.nii.gz"
        run(["fslmaths", str(image_path), "-sub", str(image_path), str(empty)])

        # convert 1-p to z
        minus1 = results_dir / f"{image[:-7]}_minus1.nii.gz"
        minus1_times = results_dir / f"{image[:-7]}_minus1_times-1.nii.gz"
        zstats = results_dir / f"{image[:-7]}_zstats.nii.gz"

        # Convert 1-p file into p:
        run(["fslmaths", str(image_path), "-sub", "1", str(minus1)])
        run(["fslmaths", str(minus1), "-mul", "-1", str(minus1_times)])

        # Convert p to z
        run(["fslmaths", str(minus1_times), "-ptoz", str(zstats)])

        # Run easythresh
        run([
            "easythresh", str(zstats), str(args.mask),
            str(args.z_thresh), str(args.cluster_prob_thresh),
            str(empty), str(image[:-7])
        ])

        # Rename outputs
        (parent / f"cluster_{image[:-7]}.txt").rename(results_dir / f"{results_dir.name}_cluster_info.txt")
        (parent / f"rendered_thresh_{image}").rename(results_dir / f"{results_dir.name}_thresh.nii.gz")
        (parent / f"cluster_mask_{image}").rename(results_dir / f"{results_dir.name}_cluster_index.nii.gz")

        # Cleanup
        for f in [minus1, minus1_times, empty, parent / f"rendered_thresh_{image[:-7]}.png"]:
            f.unlink(missing_ok=True)

        # Reverse cluster IDs
        print(f"\nReversing cluster order for {results_dir.name}\n")
        cluster_index_nii_path = results_dir / f"{results_dir.name}_cluster_index.nii.gz"
        cluster_index_img = nib.load(cluster_index_nii_path)
        data_type = np.uint8 if np.max(cluster_index_img) < 255 else np.uint16
        rev_cluster_index_img = reverse_clusters(cluster_index_img, rev_cluster_index, data_type, cluster_index_nii_path)

    else:
        print(f"\ncluster_mask_{image[:-7]} exists, skipping\n")


if __name__ == '__main__':
    main()