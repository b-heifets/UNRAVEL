#!/usr/bin/env python3

import argparse
import os
import numpy as np
import ants
from argparse import RawTextHelpFormatter
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from unravel_config import Configuration
from unravel_img_tools import load_3D_img, save_as_tifs, resample_reorient, pad_image, rolling_ball_subtraction_opencv_parallel
from unravel_utils import print_func_name_args_times, print_cmd_and_times, initialize_progress_bar, get_samples

def parse_args():
    parser = argparse.ArgumentParser(description='Loads fluorescence channel(s) and subracts background, resamples, reorients, and saves as NIftI', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process.', nargs='*', default=None, metavar='')
    parser.add_argument('-o', '--output', help='Output file name (Default: sample??_ochann_rb4_gubra_space.nii.gz)', default=None, metavar='')
    parser.add_argument('--channels', help='.czi channel number(s) (e.g., 1 2; Default: 1)', nargs='+', default=1, type=int, metavar='')
    parser.add_argument('--chann_name', help='Name(s) of channels for saving (e.g., tdT cFos). List length should match that for --channels. Default: ochann)', nargs='+', default="ochann", metavar='')
    parser.add_argument('-td', '--tif_dir', help='Name of folder in sample folder or working directory with raw immunofluo tifs. Use as image input if *.czi does not exist. Default: ochann', default="ochann", metavar='')
    parser.add_argument('-ort', '--ort_code', help='3 letter orientation code for reorienting (using the letters RLAPSI). Default: ALI', default='ALI', metavar='')

    parser.add_argument('-rb', '--rb_radius', help='Radius of rolling ball in pixels (Default: 4)', default=4, type=int, metavar='')
    parser.add_argument('-x', '--xy_res', help='x/y voxel size in microns (Default: get via metadata)', default=None, type=float, metavar='')
    parser.add_argument('-z', '--z_res', help='z voxel size in microns (Default: get via metadata)', default=None, type=float, metavar='')
    parser.add_argument('-r', '--res', help='Resample to this resolution in microns (Default: 25)', default=25, type=int, metavar='')
    parser.add_argument('-zo', '--zoom_order', help='Order of spline interpolation. Range: 0-5. (Default: 1))', default=1, type=int, metavar='')
    parser.add_argument('-a', '--atlas_name', help='Name of atlas (Default: gubra)', default="gubra", metavar='')
    parser.add_argument('-t', '--template', help='Average template image. Default: path/gubra_template_25um.nii.gz.', default="/usr/local/unravel/atlases/gubra/gubra_template_25um.nii.gz",  metavar='')
    parser.add_argument('--transforms', help="Name of folder w/ transforms from registration. Default: clar_allen_reg", default="clar_allen_reg", metavar='')
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = "From exp dir run: rb.py; Outputs: .[/sample??]/sample??_ochann_rb4_gubra_space.nii.gz"

    parser.epilog = """
Run rb.py from the experiment directory containing sample?? folders or a sample?? folder.
inputs: first ./*.czi or ./sample??/*.czi match. Otherwise, ./<tif_dir>/*.tif series
outputs: .[/sample??]/sample??_ochann_rb4_gubra_space.nii.g
next steps: check registration quality with check_reg.py and run voxel-wise analysis with glm.py""" ### Need to implement check_reg.py and glm.py
    return parser.parse_args()


@print_func_name_args_times()
def rb_resample_reorient_warp(sample, args):
    """Performs rolling ball bkg sub on full res immunofluo data, resamples, reorients, and warp to atlas space."""

    output = args.output if args.output else Path(sample, f"{sample}_ochann_rb{args.rb_radius}_gubra_space.nii.gz").resolve()
    if output.exists():
        print(f"\n\n    {output} already exists. Skipping.\n")
        return 

    # Iterate through each channel in args.channels
    for i, channel in enumerate(args.channels):

        # Load the fluorescence image
        if glob(f"{sample}/*.czi"): 
            img, xy_res, z_res = load_3D_img(Path(sample).resolve(), channel, "xyz", return_res=True)
        else:
            img, xy_res, z_res = load_3D_img(Path(sample, args.tif_dir).resolve(), "xyz", return_res=True)

        # Get the channel name; if multiple names provided, get the corresponding one
        channel_name = args.chann_name[i] if isinstance(args.chann_name, list) else args.chann_name

        # Check if the output file already exists
        output_path = Path(f"{sample}_{channel_name}_rb{args.rb_radius}_{args.atlas_name}_space.nii.gz")
        if output_path.exists():
            print(f"\n\n    {output_path} already exists. Skipping.\n")
            continue # Skip to next channel

        # Load immunofluo channel(s)              ### This code is also in prep_reg.py (aside from channel & channel_name). Consider only having it in one place. 
        xy_res, z_res = args.xy_res, args.z_res
        czi_files = glob(f"{sample}/*.czi")
        if czi_files:
            czi_path = Path(czi_files[0]).resolve() 
            img = load_czi_channel(czi_path, channel, "xyz")
            if xy_res is None or z_res is None:
                xy_res, z_res = xyz_res_from_czi(czi_path)
        else:
            tif_dir_path = Path(sample, args.tif_dir).resolve()
            img = load_tifs(tif_dir_path)
            if xy_res is None or z_res is None:
                path_to_first_tif = glob(f"{sample}/{args.tif_dir}/*.tif")[0]
                xy_res, z_res = xyz_res_from_tif(path_to_first_tif)
        if img is None:
            print(f"\n    [red]No .czi files found and tif_dir is not specified for {sample}[/]\n")
            return
                
        # Rolling ball background subtraction
        print("Before rolling_ball")

        img_bkg = rolling_ball_subtraction_opencv_parallel(img, 4)




        
        # img_bkg = rolling_ball(img, radius=args.rb_radius, nansafe=True) # returns the estimated background
        print("After rolling ball")

        tif_output_path = Path(os.getcwd()) / 'tif_output'
        save_as_tifs(img_bkg, tif_output_path, "xyz")


        

        print(f'\n{args.ort_code=}\n')
        import sys ; sys.exit()


        rb_img = img - img_bkg

        # Resample and reorient image
        rb_img_res_reort = resample_reorient(rb_img, xy_res, z_res, args.res, zoom_order=args.zoom_order) 

        # Reorient again
        rb_img_res_reort_reort = np.transpose(rb_img_res_reort, (1, 2, 0)) 

        # Padding the image 
        rb_img_res_reort_reort_padded = pad_image(rb_img_res_reort_reort, pad_width=0.15)



        # Reorient yet again
        # rb_img_res_reort_reort_padded_reort = reorient_ndarray(rb_img_res_reort_reort_padded, args.ort_code)

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
        ants.image_write(warped_image, f"{sample}_{channel_name}_rb{args.rb_radius}_{args.atlas_name}_space.nii.gz")


def main():    
    # Ensure args.channels and args.chann_name are always lists
    args.channels = [args.channels] if isinstance(args.channels, int) else args.channels
    args.chann_name = [args.chann_name] if isinstance(args.chann_name, str) else args.chann_name
    if len(args.channels) != len(args.chann_name):
        raise ValueError("\n    [red1]Length of channels and chann_name arguments should be the same.\n")

    samples = get_samples(args.dirs, args.pattern)
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            rb_resample_reorient_warp(sample, args)
            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    from rich.traceback import install
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()