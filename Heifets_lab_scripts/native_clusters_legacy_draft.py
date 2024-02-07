
import argparse
import concurrent.futures #youtube.com/watch?v=fKl2JW_qrso
import nibabel as nib
import numpy as np
from datetime import datetime
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration 
from unravel_img_io import load_3D_img, load_image_metadata_from_txt, resolve_relative_path, save_as_nii
from unravel_img_tools import cluster_IDs, resample
from unravel_utils import print_cmd_and_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Generated cropped images for each cluster and applies segmentation mask', formatter_class=SuppressMetavar)
    parser.add_argument('--exp_dirs', help='List of dirs containing sample?? folders', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern (sample??) for dirs to process. Else: use cwd', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--index', help='path/rev_cluster_index.nii.gz (e.g., from fdr.sh)', required=True, action=SM) 
    parser.add_argument('-s', '--seg_dir', help='Dir name for segmentation image (e.g., cfos_seg_ilastik_1)', action=SM)
    parser.add_argument('-o', '--output', help='Output folder name (e.g., stats_map_q0.05).', default=None, action=SM)
    parser.add_argument('-cm', '--c_masks', help='Save cluster_masks', action='store_true', default=False)
    parser.add_argument('-a', '--atlas', help='path/img.nii.gz. Default: gubra_ano_split_25um.nii.gz', default="/usr/local/unravel/atlases/gubra/gubra_ano_split_25um.nii.gz", action=SM)
    parser.add_argument('-c', '--clusters', help='Clusters to process: all or 1 3 4. Default: all', nargs='*', default='all', action=SM)
    parser.add_argument('-m', '--metadata', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Run from a sample?? folder.

Example usage:     native_clusters2.py 

Inputs: sample??/clusters/<cluster_index_dir>/native_cluster_index/<rev_cluster_index.nii.gz>

Outputs: <seg_dir>_cropped/, bounding_boxes/, clusters_cropped/, and cluster_volumes/ in sample??/clusters/<cluster_index_dir>/

Next script: cluster_cell_counts.py"""
    return parser.parse_args()

# TODO: If still slow, consider loading image subsets corresponding to clusters. could use resolve_relative_path to allow for relative paths with glob patterns

def bbox_crop_vol(i, sample_path, cluster_index_dir, native_rev_cluster_index_img_cropped, seg_cropped, xy_res, z_res, seg_dir, c_masks=False):
    #Define path/outputs:
    sample = sample_path.name
    output_path = Path(sample_path, "clusters", cluster_index_dir)
    cluster_cropped_output = Path(output_path, "clusters_cropped", f"crop_{sample}_native_cluster_{i}.nii.gz")
    bbox_output = Path(output_path, "bounding_boxes", f"bounding_box_{sample}_cluster_{i}.txt")
    cluster_volumes_output =  Path(output_path, "cluster_volumes", f"{sample}_cluster_{i}_volume_in_cubic_mm.txt")
    seg_in_cluster_cropped_output = Path(output_path, f"{seg_dir}_cropped", "3D_counts", f"crop_{seg_dir}_{sample}_native_cluster_{i}_3dc/crop_{seg_dir}_{sample}_native_cluster_{i}.nii.gz")

    #Get bounding box for slicing/cropping each cluster from index: xmin:xmax,ymin:ymax,zmin:zmax
    print(str(f'  Get cluster_{i} bbox '+datetime.now().strftime("%H:%M:%S")))
    index = np.where(native_rev_cluster_index_img_cropped == i) #1D arrays of indices of elements == i for each axis
    xmin = int(min(index[0]))
    xmax = int(max(index[0])+1)
    ymin = int(min(index[1]))
    ymax = int(max(index[1])+1)
    zmin = int(min(index[2])) 
    zmax = int(max(index[2])+1)
    with open(bbox_output, "w") as file:
        file.write(f"{xmin}:{xmax}, {ymin}:{ymax}, {zmin}:{zmax}")

    #Crop clusters, measure cluster volme, and save as seperate .nii.gz files
    cluster_cropped = native_rev_cluster_index_img_cropped[xmin:xmax, ymin:ymax, zmin:zmax] #crop cluster
    cluster_cropped = cluster_cropped.squeeze()

    # Measure cluster volume and save as .txt file
    print(str(f'  Get cluster_{i} volume (mm^3) '+datetime.now().strftime("%H:%M:%S")))
    # ((xy_res_in_um^2*)*xy_res_in_um)*ID_voxel_count/1000000000
    volume_in_cubic_mm = ((xy_res**2) * z_res) * int(np.count_nonzero(cluster_cropped)) / 1000000000
    with open(cluster_volumes_output, "w") as file:
        file.write(f"{volume_in_cubic_mm}")
    
    # Save cropped cluster mask as .nii.gz file
    if c_masks:
        print(str(f'  Save cluster_{i} cropped cluster mask '+datetime.now().strftime("%H:%M:%S")))
        image = np.where(cluster_cropped > 0, 1, 0).astype(np.uint8)
        image = nib.Nifti1Image(image, np.eye(4))
        nib.save(image, cluster_cropped_output)

    #Crop seg_in_clusters and save as seperate .nii.gz files
    if not seg_in_cluster_cropped_output.exists():
        print(str(f"  Crop cluster_{i} cell segmentation, zero out voxels outside of cluster, & save "+datetime.now().strftime("%H:%M:%S")))
        seg_cluster_cropped = seg_cropped[xmin:xmax, ymin:ymax, zmin:zmax]
        cluster_cropped = np.where(cluster_cropped == i, 1, 0)
        cluster_cropped = cluster_cropped.astype(np.uint8)
        seg_in_cluster_cropped = cluster_cropped * seg_cluster_cropped #zero out segmented cells outside of clusters
        image = np.where(seg_in_cluster_cropped > 0, 1, 0).astype(np.uint8)
        image = nib.Nifti1Image(image, np.eye(4))
        Path(output_path, f"{seg_dir}_cropped", "3D_counts", f"crop_{seg_dir}_{sample}_native_cluster_{i}_3dc").mkdir(parents=True, exist_ok=True)
        nib.save(image, seg_in_cluster_cropped_output)


def main():
    samples = get_samples(args.dirs, args.pattern)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            # Resolve path to sample folder
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            # Get clusters to process
            if args.clusters == "all":
                clusters = cluster_IDs(args.index, min_extent=100, print_IDs=False, print_sizes=False)
            else:
                clusters = [args.clusters]
            
            # Define final output and check if it exists
            output_path = Path(sample_path, "clusters", cluster_index_dir)
            cluster_index_dir = Path(args.index).parent.name
            highest_cluster = np.array(clusters).max
            final_output_path = Path(output_path, f"{args.seg_dir}_cropped", "3D_counts", f"crop_{args.seg_dir}_{sample}_native_cluster_{highest_cluster}_3dc", f"crop_{args.seg_dir}_{sample}_native_cluster_{highest_cluster}.nii.gz")
            if final_output_path.exists():
                print(f"\n\n    {final_output_path.name} already exists. Skipping.\n")
                return
            
            # Load resolutions and dimensions of full res image or scaling and to calculate how much padding to remove
            metadata_path = resolve_relative_path(sample_path, rel_path_or_glob_pattern=args.metad_path)
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(metadata_path)
            if xy_res is None:
                print(f"    [red1]./{sample}/parameters/metadata.txt is missing. Generate w/ metadata.py")
                return
            
            # Load cluster index and convert to ndarray
            ### native_img = warp_to_native(args.moving_img, args.fixed_img, args.transforms, args.reg_o_prefix, args.reg_res, args.fixed_res, args.metadata, args.legacy)

            index_basename = Path(args.index).name
            native_rev_cluster_index_path = Path(output_path, "native_cluster_index", f"native_{index_basename}")
            native_rev_cluster_index_img = load_3D_img(native_rev_cluster_index_path) 
            
            # Define output dirs
            bbox_path = Path(output_path, "bounding_boxes")
            clusters_cropped_path = Path(output_path, "clusters_cropped")
            cluster_volumes_path = Path(output_path, "cluster_volumes")
            seg_cropped_path = Path(output_path, f"{args.seg_dir}_cropped", "3D_counts")

            # Make output dirs
            bbox_path.mkdir(parents=True, exist_ok=True)
            clusters_cropped_path.mkdir(parents=True, exist_ok=True)
            cluster_volumes_path.mkdir(parents=True, exist_ok=True)
            seg_cropped_path.mkdir(parents=True, exist_ok=True)

            # Crop outer space around all clusters ########################
            print(str('  Find bbox of cluster index and trim outer space '+datetime.now().strftime("%H:%M:%S")+'\n'))
            xy_view = np.any(native_rev_cluster_index_img, axis=2) # 2D boolean array similar to max projection of z (True if > 0)
            outer_xmin = int(min(np.where(xy_view)[0])) # 1st of 2 1D arrays of indices of True values
            outer_xmax = int(max(np.where(xy_view)[0])+1)
            outer_ymin = int(min(np.where(xy_view)[1]))
            outer_ymax = int(max(np.where(xy_view)[1])+1)
            yz_view = np.any(native_rev_cluster_index_img, axis=0)
            outer_zmin = int(min(np.where(yz_view)[1]))
            outer_zmax = int(max(np.where(yz_view)[1])+1)
            native_rev_cluster_index_img_cropped = native_rev_cluster_index_img[outer_xmin:outer_xmax, outer_ymin:outer_ymax, outer_zmin:outer_zmax] # Cropped cluster index
            with open(f"bounding_boxes/outer_bounds.txt", "w") as file:
                file.write(f"{outer_xmin}:{outer_xmax}, {outer_ymin}:{outer_ymax}, {outer_zmin}:{outer_zmax}")  
    
            #Load cell segmentation .nii.gz
            print(str('  Loading cell segmentation and trim outer space '+datetime.now().strftime("%H:%M:%S")+'\n'))
            seg_img = load_3D_img(Path(sample_path, args.seg_dir, f"{sample}_{args.seg_dir}.nii.gz"))
            seg_cropped = seg_img[outer_xmin:outer_xmax, outer_ymin:outer_ymax, outer_zmin:outer_zmax] # Cropped cluster index
            seg_cropped = seg_cropped.squeeze() # Removes single-dimensional elements from array 
            
            clusters = list(map(int, clusters)) # Convert to ints
            with concurrent.futures.ProcessPoolExecutor() as executor:
                executor.map(bbox_crop_vol, clusters, [sample_path]*len(clusters), [cluster_index_dir]*len(clusters), [native_rev_cluster_index_img_cropped]*len(clusters), [seg_cropped]*len(clusters), [xy_res]*len(clusters), [z_res]*len(clusters), [args.seg_dir]*len(clusters), [args.c_masks]*len(clusters))
            print(str("  Finished native_clusters_any_immunofluor_rater_abc.py "+datetime.now().strftime("%H:%M:%S")+'\n'))

            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()