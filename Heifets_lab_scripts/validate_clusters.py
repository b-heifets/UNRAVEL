#!/usr/bin/env python3

import argparse
import numpy as np
from argparse import RawTextHelpFormatter
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from unravel_config import Configuration 
from unravel_img_tools import load_3D_img, resample_reorient, save_as_tifs, save_as_nii, cluster_IDs
from unravel_utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Validate clusters of significant voxels based on full res cell densities measurements', formatter_class=RawTextHelpFormatter)
    parser.add_argument('--exp_dirs', help='List of dirs containing sample?? folders', nargs='*', default=None, metavar='')
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, metavar='')
    # parser.add_argument('-o', '--output', help='Output folder name (e.g., stats_map_q0.05).', default=None, metavar='')
    parser.add_argument('-i', '--index', help='path/rev_cluster_index.nii.gz (e.g., from fdr.sh)', default=None, metavar='') 
    # parser.add_argument('-si', '--seg_img', help='path/segmentation_img.nii.gz relative to sample folder', default=None, metavar='')
    parser.add_argument('--clusters', help='Clusters to process: all or 1 3 4. Default: all', nargs='*', default='all', metavar='')
    # parser.add_argument('-x', '--xy_res', help='x/y voxel size in microns. Default: get via metadata', default=None, type=float, metavar='')
    # parser.add_argument('-z', '--z_res', help='z voxel size in microns. Default: get via metadata', default=None, type=float, metavar='')
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = """
run validate_clusters.py from the experiment summary dir.
other inputs: Transformations from reg.py 
outputs: sample??/clusters/<output_folder>/ and ./cluster_validation_summary/<output_folder>/
next scripts: cluster_validation_summary.py and cluster_montage.py""" 
    return parser.parse_args()

# @print_func_name_args_times()
# def validate_clusters(sample, args):
#     """Validate clusters of significant voxels based on full res cell densities measurements"""

#     # Regional volumes
# sunburst.sh $rev_cluster_index
# mkdir -p cluster_validation_summary $PWD/cluster_validation_summary/$output_dir_name
# rsync -au ${rev_cluster_index%/*}/ $exp_summary_dir/cluster_validation_summary/$output_dir_name/cluster_index


#   # Warp reversed cluster index to native space
#   to_native2.sh $rev_cluster_index $xy_res $z_res clusters/$output_dir_name native_cluster_index

#   # Generate ./bounding_boxes/*.txt, & cropped cluster masks and segmentation images
#   native_clusters_any_immunofluor_rater_abc.sh $s/clusters/$output_dir_name/native_cluster_index/native_"$output_dir_name"_rev_cluster_index.nii.gz $xy_res $z_res "$clusters"

#   # 3D count cells in clusters
#   for c in $(eval echo $clusters); do
#     cluster_cell_counts.py #<cropped_cluster_mask> <cropped_seg_img> # Perhaps add this to native_clusters
#   done

#   # rsync -au $s/clusters/$output_dir_name/ $exp_summary_dir/cluster_validation_summary/$output_dir_name

# ####### Get cell densities in clusters #######
# # cd $exp_summary_dir/cluster_validation_summary/$output_dir_name
# # cluster_densities2_any_immunofluor_rater_abc.sh all all $immuno_label $seg_type

# cd $exp_summary_dir

# printf "\n$inputs\n"



def main():

    exp_summary_dir = Path(".").resolve()

    index, xy_res, z_res = load_3D_img(args.index, desired_axis_order='xyz', return_res=True)

    if args.clusters == "all":
        # clusters_to_process = uniq_intensities.py -i args.cluster_index -m 100 # min cluster size = 100 voxels
        clusters = cluster_IDs(index, min_extent=100, print_IDs=False, print_sizes=False)
        print(clusters)
    
    import sys ; sys.exit()


    # Get samples from args.dirs, args.exp_dirs and args.pattern, args.pattern or cwd
    if args.dirs: 
        samples = [args.dirs]
    elif args.exp_dirs:
        samples = []
        for exp_dir in args.exp_dirs:
            exp_dir = Path(exp_dir).resolve()
            if not exp_dir.is_dir():
                print(f"\n    [red bold]Error: {exp_dir} is not a directory.\n")
                continue 

            sample_dirs = glob(f"{exp_dir}/{args.pattern}/")
            if not samples:
                print(f"\n    [red bold]Error: No sample folders in {exp_dir}.\n")
                continue
            for sample_dir in sample_dirs:
                if Path(sample_dir).is_dir():
                    samples.append(sample_dir)
    elif glob(f"{exp_summary_dir}/{args.pattern}/"):
        samples = [glob(f"{exp_summary_dir}/{args.pattern}/")]
    else:
        samples = [Path.cwd().name]
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            # validate_clusters(sample, args)
            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()