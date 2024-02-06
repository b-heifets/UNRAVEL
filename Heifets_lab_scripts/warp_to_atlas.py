#!/usr/bin/env python3

import argparse
import numpy as np
import ants
from argparse import RawTextHelpFormatter
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from unravel_config import Configuration
from unravel_img_io import load_3D_img, save_as_nii
from unravel_img_tools import resample, reorient_for_raw_to_nii_conv, pad_image, reorient_ndarray2
from unravel_utils import print_func_name_args_times, print_cmd_and_times, initialize_progress_bar, get_samples

def parse_args():
    parser = argparse.ArgumentParser(description='Loads fluorescence channel(s) and subracts background, resamples, reorients, and saves as NIftI', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, metavar='')
    parser.add_argument('-o', '--output', help='Output file name (Default: <sample??>_<ochann>_rb<4>_<gubra>_space.nii.gz)', default=None, metavar='')
    parser.add_argument('-c', '--chann_idx', help='.czi channel index. Default: 1', default=1, type=int, metavar='')
    parser.add_argument('-l', '--label', help='Fluorescent label (e.g., cfos). If raw data is tifs, should match tif dir name. Default: ochann)', default="ochann", metavar='')
    parser.add_argument('-rb', '--rb_radius', help='Radius of rolling ball in pixels (Default: 4)', default=4, type=int, metavar='')
    parser.add_argument('-ort', '--ort_code', help='3 letter orientation code for reorienting (using the letters RLAPSI). Default: ALI', default='ALI', metavar='')
    parser.add_argument('-t', '--template', help='Average template image. Default: path/gubra_template_25um.nii.gz.', default="/usr/local/unravel/atlases/gubra/gubra_template_25um.nii.gz",  metavar='')
    parser.add_argument('-a', '--atlas_name', help='Name of atlas (Default: gubra)', default="gubra", metavar='')
    parser.add_argument('--transforms', help="Name of folder w/ transforms from registration. Default: clar_allen_reg", default="clar_allen_reg", metavar='')
    parser.add_argument('-x', '--xy_res', help='Native x/y voxel size in microns (Default: get via metadata)', default=None, type=float, metavar='')
    parser.add_argument('-z', '--z_res', help='Native z voxel size in microns (Default: get via metadata)', default=None, type=float, metavar='')
    parser.add_argument('-r', '--res', help='Resample input image to this resolution in microns. Default: 50', default=50, type=int, metavar='')
    parser.add_argument('-zo', '--zoom_order', help='Order of spline interpolation. Range: 0-5. (Default: 1))', default=1, type=int, metavar='')
    parser.add_argument('--threads', help='Number of threads for rolling ball background subtraction (Default: 8)', default=8, type=int, metavar='')
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = """
Run prep_vxw_stats.py from the experiment directory containing sample?? folders or a sample?? folder.
inputs: first ./*.czi or ./sample??/*.czi match. Otherwise, ./<label>/*.tif series
outputs: .[/sample??]/sample??_ochann_rb4_gubra_space.nii.gz
next steps: check registration quality with check_reg.py and run vx_stats.py""" ### TODO: Need to implement check_reg.py and vx_stats.py
    return parser.parse_args()


@print_func_name_args_times()
def warp_to_atlas_space(sample_path, ndarray, orientation_code):
    """Warps downsampled/reoriented ndarray to atlas space"""

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

    # Padding the image 
    ndarray_padded = pad_image(ndarray, pad_width=0.15)
    # save_as_nii(rb_img_res_reort_reort_padded, Path(sample_path, "rb_img_res_reort_reort_padded.nii.gz"), args.res, args.res, np.uint16)

    img_padded_reoriented = reorient_ndarray2(ndarray_padded, orientation_code)
    save_as_nii(img_padded_reoriented, Path(sample_path, "img_padded_reoriented.nii.gz"), args.res, args.res, np.uint16)

    import sys ; sys.exit()
    

    # Convert the ndarray to 'float32' if it's not already 'float32' or 'float64'
    if ndarray_padded.dtype != np.float32 and ndarray_padded.dtype != np.float64:
        ndarray_padded = ndarray_padded.astype(np.float32)

    img_padded = ants.from_numpy(ndarray_padded)

    img_padded_reoriented = ants.reorient_image2(img_padded, orientation='RAS') # antspy.readthedocs.io/en/latest/_modules/ants/registration/reorient_image.html#
    ants.image_write(img_padded_reoriented, str(Path(sample_path, "img_padded_reoriented.nii.gz")))

    import sys ; sys.exit()





    # Reorient yet again
    rb_img_res_reort_reort_padded_reort = reorient_ndarray(rb_img_res_reort_reort_padded, args.ort_code)
    save_as_nii(rb_img_res_reort_reort_padded_reort, Path(sample_path, "rb_img_res_reort_reort_padded_reort.nii.gz"), args.res, args.res, np.uint16)

    import sys ; sys.exit()

    # Directory with transforms from registration
    cwd = Path(".").resolve()
    transforms_dir = Path(sample, args.transforms).resolve() if sample != cwd.name else Path(args.transforms).resolve()

    # Read in transforms
    initial_transform_matrix = ants.read_transform(f'{transforms_dir}/init_tform.mat', precision=1)  # assuming 1 denotes float precision 
    inverse_warp = ants.read_transform(f'{transforms_dir}/allen_clar_ants1InverseWarp.nii.gz')
    affine_transform = ants.read_transform(f'{transforms_dir}/allen_clar_ants0GenericAffine.mat', precision=1)  # assuming 1 denotes float precision

    print(f'\n{initial_transform_matrix=}\n')
    print(f'\n{inverse_warp=}\n')
    print(f'\n{affine_transform=}\n')
    import sys ; sys.exit()

    # Combine the deformation fields and transformations
    combined_transform = ants.compose_transforms(inverse_warp, affine_transform) # clar_allen_reg/clar_allen_comb_def.nii.gz

    # Read in reference image
    reference_image = ants.image_read(f'{transforms_dir}/init_allen.nii.gz') # 50 um template from initial transformation to tissue during registration 

    # antsApplyTransforms -d 3 -r /usr/local/miracl/atlases/ara/gubra/gubra_template_25um.nii.gz -i clar_allen_reg/reo_sample13_02x_down_cfos_rb4_chan_ort_cp_org.nii.gz -n Bspline -t [ clar_allen_reg/init_tform.mat, 1 ] clar_allen_reg/clar_allen_comb_def.nii.gz -o /SSD3/test/sample_w_czi2/sample13/reg_final/reo_sample13_02x_down_cfos_rb4_chan_cfos_channel_allen_space.nii.gz
    warped_image = ants.apply_transforms(fixed=reference_image, moving=rb_img_res_reort_reort_padded_reort, transformlist=[combined_transform, initial_transform_matrix], interpolator='bSpline')

    # Save warped image
    ants.image_write(warped_image, f"{sample}_{args.label}_rb{args.rb_radius}_{args.atlas_name}_space.nii.gz")


def main():    

    samples = get_samples(args.dirs, args.pattern)

    if samples == ['.']:
        samples[0] = Path.cwd().name

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            cwd = Path(".").resolve()

            sample_path = Path(sample).resolve() if sample != cwd.name else Path().resolve()

            # Load full resolution image
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
                print(f"\n    [red bold]Error: {e}\n    Skipping {sample_path.name}.\n")
                return

            # Resample and reorient image
            img_res = resample(img, xy_res, z_res, args.res, zoom_order=args.zoom_order) 
            img_res_reort = reorient_for_raw_to_nii_conv(img_res)
            
            # Warp to atlas space
            warp_to_atlas_space(sample_path, img_res_reort, args.ort_code)

            # fluo_img_output = Path(sample_path, args.output) if args.output else Path(sample_path, f"{sample_path.name}_{args.label}_rb{args.rb_radius}_{args.atlas_name}_space.nii.gz") # <sample??>_<ochann>_rb<4>_<gubra>_space.nii.gz)
            # if fluo_img_output.exists():
            #     print(f"\n\n    {fluo_img_output} already exists. Skipping.\n")
            #     return
            

            

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()