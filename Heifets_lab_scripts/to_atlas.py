#!/usr/bin/env python3

import argparse
import numpy as np
import ants
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_img_io import load_3D_img, resolve_path, load_image_metadata_from_txt, save_as_nii
from unravel_img_tools import resample, reorient_for_raw_to_nii_conv, pad_image, reorient_ndarray
from unravel_utils import print_func_name_args_times, print_cmd_and_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Warps native image to atlas space', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-m', '--moving_img', help='INPUT: Path of native image relative to ./sample?? (fixed image)', required=True, action=SM)
    parser.add_argument('-o', '--output', help='Output path/img.nii.gz', default=None, action=SM)
    parser.add_argument('-c', '--chann_idx', help='.czi channel index. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-ort', '--ort_code', help='3 letter orientation code for reorienting (using the letters RLAPSI). Default: ALI', default='ALI', action=SM)
    parser.add_argument('-ln', '--label', help='Fluorescent label name (e.g., cfos). If raw data is tifs, should match tif dir name. Default: ochann)', default="ochann", action=SM)
    # parser.add_argument('-f', '--fixed_img', help='', action=SM)
    parser.add_argument('-i', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor, genericLabel, linear, bSpline [default])', default="bSpline", action=SM)
    parser.add_argument('-a', '--atlas_name', help='Name of atlas (Default: gubra)', default="gubra", action=SM)
    parser.add_argument('--transforms', help="Name of folder w/ transforms from registration. Default: clar_allen_reg", default="clar_allen_reg", action=SM)
    parser.add_argument('-x', '--xy_res', help='Native x/y voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='Native z voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-r', '--reg_res', help='Registration resolution in microns (reg.py). Default: 50', default=50, type=int, action=SM)
    parser.add_argument('-fr', '--fixed_res', help='Resolution of the fixed reference image. Default: 25', default='25',type=int, action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order for resampling the native image. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-dt', '--dtype', help='Desired dtype for full res output (uint8, uint16). Default: moving_img.dtype', action=SM)
    parser.add_argument('-rp', '--reg_o_prefix', help='Registration output prefix. Default: allen_clar_ants', default='allen_clar_ants', action=SM)
    parser.add_argument('-l', '--legacy', help='Mode for backward compatibility (accounts for raw to nii reorienting)', action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = """Run script from the experiment directory w/ sample?? dir(s) or a sample?? dir
Example usage: to_atlas.py -i *.czi -v [-l]

Prereq: ./parameters/metadata.txt (prep_reg.py or metadata.py)

Input examples (path is relative to ./sample??; 1st glob match processed): 
*.czi, autofluo/*.tif series, autofluo, *.tif, *.h5, or *.zarr 

"""
    return parser.parse_args()






@print_func_name_args_times()
def to_atlas(sample_path, img, xy_res, z_res, reg_res, zoom_order, ort_code, interpol, transforms_dir, output, reg_output_prefix, legacy=False):
    """Warps native image to atlas space"""

    # Resample and reorient image
    img = resample(img, xy_res, z_res, reg_res, zoom_order=zoom_order) 

    # Reorient image if legacy mode is True
    if legacy:
        img = reorient_for_raw_to_nii_conv(img)
        save_as_nii(img, Path(sample_path, "img_reorient_for_raw_to_nii_conv.nii.gz"), args.reg_res, args.reg_res, np.uint16)

        # Reorient using orientation code
        # img = reorient_ndarray(img, args.ort_code)
        # save_as_nii(img, Path(sample_path, "img_reorient_for_raw_to_nii_conv_reort.nii.gz"), args.reg_res, args.reg_res, np.uint16)

        

    # Padding the image 
    img = pad_image(img, pad_width=0.15)
    save_as_nii(img, Path(sample_path, "img_res_reort_padded.nii.gz"), args.reg_res, args.reg_res, np.uint16)

    import sys ; sys.exit()


    # Convert the numpy array to an ANTs image
    ants_img = ants.from_numpy(img)

    # Optionally, you might want to specify the spacing, origin, and direction of the image
    # ants_img.set_spacing((1.0, 1.0, 1.0))  # Replace these values with your specific spacing
    # ants_img.set_origin((0, 0, 0))  # Replace these values with your specific origin
    # ants_img.set_direction(np.eye(3))  # Identity matrix for direction; replace if needed

    # Load reference image
    fixed_ants_img = ants.image_read(f'{transforms_dir}/init_allen.nii.gz') # 50 um template from initial transformation to tissue during registration 

    # Directory with transforms from registration
    transforms_dir = Path(transforms_dir).resolve()

    # Combine the deformation fields and transformations
    inverse_warp = f'{transforms_dir}/{reg_output_prefix}1InverseWarp.nii.gz'
    affine_transform = f'{transforms_dir}/{reg_output_prefix}0GenericAffine.mat' 
    combined_transform = ants.compose_transforms(inverse_warp, affine_transform) # clar_allen_reg/clar_allen_comb_def.nii.gz

    # Initial transformation matrix
    initial_transform_matrix = f'{transforms_dir}/init_tform.mat'

    # antsApplyTransforms -d 3 -r /usr/local/miracl/atlases/ara/gubra/gubra_template_25um.nii.gz -i clar_allen_reg/reo_sample13_02x_down_cfos_rb4_chan_ort_cp_org.nii.gz -n Bspline -t [ clar_allen_reg/init_tform.mat, 1 ] clar_allen_reg/clar_allen_comb_def.nii.gz -o /SSD3/test/sample_w_czi2/sample13/reg_final/reo_sample13_02x_down_cfos_rb4_chan_cfos_channel_allen_space.nii.gz
    warped_ants_img = ants.apply_transforms(
        fixed=fixed_ants_img,
        moving=ants_img,
        transformlist=[combined_transform, initial_transform_matrix],
        interpolator=interpol
    )

    # Save warped image
    ants.image_write(warped_ants_img, output)


def main():    

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            output = resolve_path(sample_path, args.output)
            if output.exists():
                print(f"\n\n    {output} already exists. Skipping.\n")
                return

            # Load autofluo image [and xy and z voxel size in microns]
            img_path = resolve_path(sample_path, path_or_pattern=args.moving_img)
            img, xy_res, z_res = load_3D_img(img_path, args.chann_idx, "xyz", return_res=True, xy_res=args.xy_res, z_res=args.z_res)

            # Warp native image to atlas space
            to_atlas(sample_path, img, xy_res, z_res, args.reg_res, args.zoom_order, args.ort_code, args.interpol, args.transforms, args.output, args.reg_o_prefix, legacy=args.legacy)

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
