#!/usr/bin/env python3

from pathlib import Path
import nibabel as nib
import numpy as np
import argparse
from concurrent.futures import ThreadPoolExecutor
from rich import print
from rich.traceback import install

from unravel.argparse_utils import SM, SuppressMetavar
from sunburst import sunburst
from unravel.config import Configuration
from unravel.utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Create a cluster index with valid clusters from a given NIfTI image.', formatter_class=SuppressMetavar)
    parser.add_argument('-ci', '--cluster_idx', help='Path to the reverse cluster index NIfTI file.', default=None, action=SM)
    parser.add_argument('-ids', '--valid_cluster_ids', help='Space-separated list of valid cluster IDs.', nargs='+', type=int, default=None, action=SM)
    parser.add_argument('-vcd', '--valid_clusters_dir', help='path/name_of_the_output_directory. Default: valid_clusters', default='_valid_clusters', action=SM)
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz (Default: path/gubra_ano_combined_25um.nii.gz)', default='/usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz', action=SM)
    parser.add_argument('-rgb', '--output_rgb_lut', help='Output sunburst_RGBs.csv if flag provided (for Allen brain atlas coloring)', action='store_true')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Usage:    valid_clusters_index.py -ci path/rev_cluster_index.nii.gz -a path/atlas.nii.gz -ids 1 2 3
    
Outputs: path/valid_clusters/rev_cluster_index_valid_clusters.nii.gz and path/valid_clusters/cluster_*_sunburst.csv"""
    return parser.parse_args()


def generate_sunburst(cluster, img, atlas, xyz_res_in_um, data_type, output_dir):
    """Generate a sunburst plot for a given cluster.
    
    Args:
        - cluster (int): the cluster ID.
        - img (ndarray): the input image ndarray.
        - atlas (ndarray): the atlas ndarray.
        - atlas_res_in_um (tuple): the atlas resolution in microns. For example, (25, 25, 25)
        - data_type (type): the data type of the image.
        - output_dir (Path): the output directory.
    """
    mask = (img == cluster)
    if np.any(mask):
        cluster_image = np.where(mask, cluster, 0).astype(data_type)
        cluster_sunburst_path = output_dir / f'cluster_{cluster}_sunburst.csv'
        sunburst_df = sunburst(cluster_image, atlas, xyz_res_in_um, cluster_sunburst_path)


def main():
    args = parse_args()

    if args.cluster_idx is None: 
        print(f"\n    No cluster index provided. Skipping.")
        return

    if args.valid_cluster_ids is None: 
        print(f"\n    No valid clusters provided. Skipping.")
        return

    output_dir = Path(args.valid_clusters_dir)
    output_dir.mkdir(exist_ok=True, parents=True)
    output_image_path = output_dir / str(Path(args.cluster_idx).name).replace('.nii.gz', f'_{output_dir.name}.nii.gz')
    if output_image_path.exists():
        print(f"\n    {output_image_path.name} already exists. Skipping.")
        return

    nii = nib.load(args.cluster_idx)
    img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()
    max_cluster_id = int(img.max())
    data_type = np.uint16 if max_cluster_id >= 256 else np.uint8
    img = img.astype(data_type)
    
    atlas_nii = nib.load(args.atlas)
    atlas = np.asanyarray(atlas_nii.dataobj, dtype=atlas_nii.header.get_data_dtype()).squeeze()
    atlas_res = atlas_nii.header.get_zooms() # (x, y, z) in mm
    xyz_res_in_um = atlas_res[0] * 1000
    
    # Write valid cluster indices to a file
    with open(output_dir / 'valid_clusters.txt', 'w') as file:
        file.write(' '.join(map(str, args.valid_cluster_ids)))
    
    # Generate the valid cluster index
    valid_cluster_index = np.zeros_like(img, dtype=data_type)
    for cluster in args.valid_cluster_ids:
        valid_cluster_index = np.where(img == cluster, cluster, valid_cluster_index)
    
    # Parallel processing of sunburst plots
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(generate_sunburst, cluster, img, atlas, xyz_res_in_um, data_type, output_dir) for cluster in args.valid_cluster_ids]
        for future in futures:
            future.result()  # Wait for all threads to complete

    print(f'    Saved valid cluster index: {output_image_path}')
    nib.save(nib.Nifti1Image(valid_cluster_index, nii.affine, nii.header), output_image_path)
    
    # Generate the sunburst plot for the valid cluster index
    sunburst_df = sunburst(valid_cluster_index, atlas, xyz_res_in_um, output_dir / 'valid_clusters_sunburst.csv', args.output_rgb_lut)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()