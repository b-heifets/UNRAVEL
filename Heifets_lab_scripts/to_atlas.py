#!/usr/bin/env python3

import argparse
import numpy as np
import ants
import nibabel as nib
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from scipy.ndimage import zoom

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_img_io import load_3D_img, resolve_path, load_image_metadata_from_txt
from unravel_img_tools import resample, reorient_for_raw_to_nii_conv, pad_image, reorient_ndarray, save_as_nii
from unravel_utils import print_func_name_args_times, print_cmd_and_times, initialize_progress_bar, get_samples




def parse_args():
    parser = argparse.ArgumentParser(description='Warps native image to atlas space', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-m', '--moving_img', help='INPUT: Path of native image relative to ./sample?? (fixed image)', required=True, action=SM)
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 0 for autofluo', default=0, type=int, action=SM)
    parser.add_argument('-o', '--output', help='Output path/img.nii.gz', default=None, action=SM)
    parser.add_argument('-c', '--chann_idx', help='.czi channel index. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-l', '--label', help='Fluorescent label (e.g., cfos). If raw data is tifs, should match tif dir name. Default: ochann)', default="ochann", action=SM)
    parser.add_argument('-ort', '--ort_code', help='3 letter orientation code for reorienting (using the letters RLAPSI). Default: ALI', default='ALI', action=SM)
    # parser.add_argument('-f', '--fixed_img', help='', action=SM)
    parser.add_argument('-i', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor, genericLabel, linear, bSpline [default])', default="bSpline", action=SM)
    parser.add_argument('-a', '--atlas_name', help='Name of atlas (Default: gubra)', default="gubra", action=SM)
    parser.add_argument('--transforms', help="Name of folder w/ transforms from registration. Default: clar_allen_reg", default="clar_allen_reg", action=SM)
    parser.add_argument('-x', '--xy_res', help='Native x/y voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='Native z voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-r', '--reg_res', help='Registration resolution in microns (reg.py). Default: 50', default=50, type=int, action=SM)
    parser.add_argument('-fr', '--fixed_res', help='Resolution of the fixed image. Default: 25', default='25',type=int, action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order for resampling. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-d', '--dtype', help='Desired dtype for full res output (uint8, uint16). Default: moving_img.dtype', action=SM)
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
def resample_reorient_warp(sample_path, xy_res, z_res, reg_res, zoom_order, ort_code, interpol, atlas_name, transforms, output, interpolator, reg_output_prefix, legacy=False):
    """Performs rolling ball bkg sub on full res fluo data, resamples, reorients, and warp to atlas space."""



    """
    # Reorient nifti and add padding
    base=`basename ${inimg}`
    clarname=${base%%.*}
    ifdsntexistrun ${regdir}/${clarname}_ort.nii.gz "Orienting downsampled/reoriented input nifti" \
    c3d ${inimg} -orient ${ort} -pad 15% 15% 0 -interpolation Cubic -type short -o ${regdir}/${clarname}_ort.nii.gz

    # Resample clar.nii.gz to match ${clarname}_ort.nii.gz (NN interpolation)
    # clar.nii.gz = ds_nifti -> 50 um -> bias correct -> pad -> orient -> smooth
    ort_dim=`PrintHeader ${regdir}/${clarname}_ort.nii.gz 2`
    ifdsntexistrun ${regdir}/clar_res_org.nii.gz "Resampling clar.nii.gz to match ${clarname}_ort.nii.gz" \
    ResampleImage 3 ${regdir}/clar.nii.gz ${regdir}/clar_res_org.nii.gz ${ort_dim} 1

    # Create new image w/ header from image 1 and intensities from image 2. Header info = image to physical space transform (origin, spacing, direction cosines).
    ifdsntexistrun ${regdir}/${clarname}_ort_cp_org.nii.gz "Copying header from clar_res_org.nii.gz to ${clarname}_ort.nii.gz " \
    c3d ${regdir}/clar_res_org.nii.gz ${regdir}/${clarname}_ort.nii.gz -copy-transform -type short -o ${regdir}/${clarname}_ort_cp_org.nii.gz

    # -r (reference): init_allen.nii.gz = template initially aligned with 50 um autofluo
    # -t (transform): transformFileName [transformFileName,useInverse]
    # -o [warpedOutputFileName or compositeDisplacementField,<printOutCompositeWarpFile=1>]
    # use antsTransformInfo to view allen_clar_ants0GenericAffine.mat
    ifdsntexistrun ${regdir}/clar_allen_comb_def.nii.gz "Combining deformation fields and transformations" \
    antsApplyTransforms -d 3 -r ${regdir}/init_allen.nii.gz -t ${regdir}/allen_clar_ants1InverseWarp.nii.gz [ ${regdir}/allen_clar_ants0GenericAffine.mat, 1 ] -o [ ${regdir}/clar_allen_comb_def.nii.gz, 1 ]

    ifdsntexistrun ${regdirfinal}/${clarname}_gubra_space.nii.gz "Applying ants deformations" \
    antsApplyTransforms -d 3 -r /usr/local/unravel/atlases/gubra/gubra_template_25um.nii.gz -i ${regdir}/${clarname}_ort_cp_org.nii.gz -n Bspline -t [ ${regdir}/init_tform.mat, 1 ] ${regdir}/clar_allen_comb_def.nii.gz -o ${regdirfinal}/${clarname}_gubra_space.nii.gz

    """
    sample = sample_path.name

    fluo_img_output = Path(sample_path, args.output) if args.output else Path(sample_path, f"{sample}_{args.label}_rb{args.rb_radius}_{args.atlas_name}_space.nii.gz") # <sample??>_<ochann>_rb<4>_<gubra>_space.nii.gz)
    if fluo_img_output.exists():
        print(f"\n\n    {fluo_img_output} already exists. Skipping.\n")
        return
    
    # Load the fluorescence image and optionally get resolutions
    try:
        img_path = sample_path if glob(f"{sample_path}/*.czi") else Path(sample_path, args.label)
        if args.xy_res is None or args.z_res is None:
            img, xy_res, z_res = load_3D_img(img_path, channel=args.chann_idx, desired_axis_order="xyz", return_res=True)
        else:
            img = load_3D_img(img_path, channel=args.chann_idx, desired_axis_order="xyz", return_res=False)
            xy_res, z_res = args.xy_res, args.z_res
        if not isinstance(xy_res, float) or not isinstance(z_res, float):
            raise ValueError(f"Metadata not extractable from {img_path}. Rerun w/ --xy_res and --z_res")
    except (FileNotFoundError, ValueError) as e:
        print(f"\n    [red bold]Error: {e}\n    Skipping {sample}.\n")
        return
    
    # Resample and reorient image
    img = resample(img, xy_res, z_res, reg_res, zoom_order=zoom_order) 

    # Reorient image if legacy mode is True
    if legacy:
        img = reorient_for_raw_to_nii_conv(img)
        save_as_nii(img, Path(sample_path, "img_reorient_for_raw_to_nii_conv.nii.gz"), args.reg_res, args.reg_res, np.uint16)

    # Padding the image 
    img = pad_image(img, pad_width=0.15)
    save_as_nii(img, Path(sample_path, "img_res_reort_reort_reort_padded.nii.gz"), args.reg_res, args.reg_res, np.uint16)

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
    ants.image_write(warped_image, args.output)


def main():    

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            output = resolve_path(sample_path, args.output)
            if output:
                print(f"\n\n    {output.name} already exists. Skipping.\n")
                return

            # Load autofluo image [and xy and z voxel size in microns]
            img_path = resolve_path(sample_path, path_or_pattern=args.input)
            img, xy_res, z_res = load_3D_img(img_path, args.channel, "xyz", return_res=True, xy_res=args.xy_res, z_res=args.z_res)



            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()