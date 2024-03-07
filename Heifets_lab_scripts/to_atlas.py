#!/usr/bin/env python3

import argparse
import ants
import nibabel as nib
import numpy as np
from fsl.data.image import Image
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_img_io import load_3D_img, resolve_path, save_as_nii
from unravel_img_tools import resample, reorient_for_raw_to_nii_conv
from unravel_utils import print_func_name_args_times, print_cmd_and_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Warps native image to atlas space', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-m', '--moving_img', help='INPUT: Path of native image relative to ./sample?? (fixed image)', required=True, action=SM)
    parser.add_argument('-tr', '--target_res', help='Res of image just before warping in micron. Default=50', type=int, default=50, action=SM)


    parser.add_argument('-rf', '--reg_fixed', help='Name of file in transforms dir used as fixed input for registration. Default: clar.nii.gz', default='clar.nii.gz', action=SM)
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



# Function to set the affine header using orientation code using ants image
def set_affine_header(ants_img, ort_code):
    """Set the affine header using orientation code"""
    # Set the affine header using orientation code
    affine = ants.affine_matrix_from_orientation(orientation=ort_code, origin=[0, 0, 0], size=[1, 1, 1], spacing=[1, 1, 1])
    ants_img.set_origin([0, 0, 0])
    ants_img.set_direction(np.eye(3))
    ants_img.set_spacing([1, 1, 1])
    ants_img.set_direction(affine[:3, :3])
    ants_img.set_origin(affine[:3, 3])

def pad_img(ndarray, pad_width=0.15):
    """Pads ndarray by 15% of voxels on all sides"""
    pad_factor = 1 + 2 * pad_width

    pad_width_x = round(((ndarray.shape[0] * pad_factor) - ndarray.shape[0]) / 2)
    pad_width_y = round(((ndarray.shape[1] * pad_factor) - ndarray.shape[1]) / 2)
    pad_width_z = round(((ndarray.shape[2] * pad_factor) - ndarray.shape[2]) / 2)

    return np.pad(ndarray, ((pad_width_x, pad_width_x), (pad_width_y, pad_width_y), (pad_width_z, pad_width_z)), mode='constant')
 

@print_func_name_args_times()
def to_atlas(sample_path, img, xy_res, z_res, reg_res, target_res, zoom_order, fixed_img_for_reg, interpol, transforms_dir, output, reg_output_prefix, legacy=False):
    """Warps native image to atlas space"""

    # # Resample and reorient image
    # img = resample(img, xy_res, z_res, reg_res, zoom_order=zoom_order) 

    # # Reorient image if legacy mode is True
    # if legacy:
    #     img = reorient_for_raw_to_nii_conv(img)
    #     save_as_nii(img, Path(sample_path, "img_reorient_for_raw_to_nii_conv.nii.gz"), reg_res, reg_res, np.uint16)        

    # # Padding the image 
    # img = pad_img(img, pad_width=0.15)
    # save_as_nii(img, Path(sample_path, "pad.nii.gz"), reg_res, reg_res, np.uint16)

    # Create the Nifti1Image
    # target_img = nib.Nifti1Image(img, np.eye(4))
    target_img = nib.load(Path(sample_path, "pad.nii.gz"))
    source_img = nib.load(fixed_img_for_reg) # Source of header info
    new_affine = source_img.affine.copy()

    # Determine scale factors from source affine by examining the length of the vectors
    # This works regardless of the orientation or which axes are flipped
    scale_factors = np.linalg.norm(source_img.affine[:3, :3], axis=0)

    # Adjust scale factors in the new affine matrix according to target resolution
    # We calculate the adjustment factor based on the target resolution divided by the original scale factor
    # Then apply this adjustment maintaining the direction (sign) of the original scale factors
    target_res = target_res / 1000
    for i in range(3):
        adjustment_factor = np.array([target_res, target_res, target_res])[i] / scale_factors[i]
        new_affine[:3, i] = source_img.affine[:3, i] * adjustment_factor



    # Copy relevant header information
    hdr1 = source_img.header
    hdr2 = target_img.header
    fields_to_copy = [
        'xyzt_units', 'descrip', 'qform_code', 'sform_code',
        'qoffset_x', 'qoffset_y', 'qoffset_z', # Assuming 'qoffset_z' is also needed
    ]

    for field in fields_to_copy:
        hdr2[field] = hdr1[field]

    # Conditionally copy entire 'pixdim' if appropriate for your task
    hdr2['pixdim'] = hdr1['pixdim']

     
    #Copy header info from input to output:
    # hdr1 = source_img.header
    # hdr2 = target_img.header
    # # hdr2['extents'] = hdr1['extents']
    # # hdr2['regular'] = hdr1['regular']
    # hdr2['pixdim'][4:] = hdr1['pixdim'][4:]
    # hdr2['xyzt_units'] = hdr1['xyzt_units']
    # # hdr2['descrip'] = hdr1['descrip']
    # hdr2['qform_code'] = hdr1['qform_code']
    # hdr2['sform_code'] = hdr1['sform_code']
    # hdr2['qoffset_x'] = hdr1['qoffset_x']
    # hdr2['qoffset_y'] = hdr1['qoffset_y']

    # Save
    nib.save(target_img, Path(sample_path, "cp.nii.gz"), new_affine)
    nib.Nifti1Image(new_data, img.affine, img.header)
    # save_as_nii(img, Path(sample_path, "pad.nii.gz"), args.reg_res, args.reg_res, np.uint16)




    # set_affine_header(img, ort_code)

    # save_as_nii(img, Path(sample_path, "reort.nii.gz"), args.reg_res, args.reg_res, np.uint16)

    import sys ; sys.exit()


    # Convert the NumPy array to an ANTs image
    img = img.astype('float32')
    ants_img = ants.from_numpy(img)

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
    ants.image_write(warped_ants_img, str(output))


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
            img_path = resolve_path(sample_path, args.moving_img)
            # img, xy_res, z_res = load_3D_img(img_path, args.chann_idx, "xyz", return_res=True, xy_res=args.xy_res, z_res=args.z_res)
            img = None
            xy_res = args.xy_res
            z_res = args.z_res

            fixed_img_for_reg = resolve_path(sample_path, Path(args.transforms, args.reg_fixed))

            # Warp native image to atlas space
            to_atlas(sample_path, img, xy_res, z_res, args.reg_res, args.target_res, args.zoom_order, fixed_img_for_reg, args.interpol, args.transforms, args.output, args.reg_o_prefix, legacy=args.legacy)

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
