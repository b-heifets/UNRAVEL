#!/usr/bin/env python3

import argparse
import shutil
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from prep_reg import prep_reg
from spatial_averaging import apply_2D_mean_filter, spatial_average_2D, spatial_average_3D
from to_atlas import to_atlas
from unravel_config import Configuration
from unravel_img_io import load_3D_img
from unravel_img_tools import rolling_ball_subtraction_opencv_parallel
from unravel_utils import print_cmd_and_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Loads immunofluo image, subtracts background, and warps to atlas space', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-td', '--target_dir', help='path/target_dir name for gathering outputs from all samples (use -e w/ all paths)', default=None, action=SM)

    # Required arguments:
    parser.add_argument('-i', '--input', help='path to full res image', required=True, action=SM)
    parser.add_argument('-o', '--output', help='Output file name w/o "sample??_" (added automatically). E.g., ochann_rb4_gubra_space.nii.gz', required=True, action=SM)

    # Optional arguments:
    parser.add_argument('-sa', '--spatial_avg', help='Spatial averaging in 2D or 3D (2 or 3). Default: None', default=None, type=int, action=SM)
    parser.add_argument('-rb', '--rb_radius', help='Radius of rolling ball in pixels (Default: 4)', default=4, type=int, action=SM)
    parser.add_argument('-x', '--xy_res', help='Native x/y voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='Native z voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-c', '--chann_idx', help='.czi channel index. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    parser.add_argument('-fri', '--fixed_reg_in', help='Reference nii header from reg.py. Default: reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz', default="reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz (Default: /usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz)', default='/usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz', action=SM)
    parser.add_argument('-dt', '--dtype', help='Desired dtype for output (e.g., uint8, uint16). Default: uint16', default="uint16", action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order for resampling the raw image. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-inp', '--interpol', help='Type of interpolation (linear, bSpline [default]).', default='bSpline', action=SM)
    parser.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)
    parser.add_argument('-th', '--threads', help='Number of threads for rolling ball subtraction. Default: 8', default=8, type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = """Run script from the experiment directory w/ sample?? dir(s) or a sample?? dir
Example usage: prep_vxw_stats.py -i ochann -rb 4 -x 3.5232 -z 6 -o ochann_rb4_gubra_space.nii.gz -e <list of paths to experiment directories> -v

Prereqs: 
reg.py

Input examples (path is relative to ./sample??; 1st glob match processed): 
*.czi, ochann/*.tif, ochann, *.tif, *.h5, or *.zarr

Example output:
./sample??/atlas_space/sample??_ochann_rb4_gubra_space.nii.gz

next steps: Aggregate outputs and run vxw_stats.py"""
    return parser.parse_args()


def main():
    if args.target_dir is not None:
        # Create the target directory for copying outputs for vxw_stats.py
        target_dir = Path(args.target_dir)
        target_dir.mkdir(exist_ok=True, parents=True)

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            output_name = f"{sample_path.name}_{Path(args.output).name}"
            output = sample_path / "atlas_space" / output_name
            output.parent.mkdir(exist_ok=True, parents=True)
            if output.exists():
                print(f"\n    {output} already exists. Skipping.")
                continue
            
            # Load full res image [and xy and z voxel size in microns], to be resampled [and reoriented], padded, and warped
            img_path = sample_path / args.input
            img = load_3D_img(img_path, args.chann_idx, "xyz")

            # Apply spatial averaging
            if args.spatial_avg == 3:
                img = spatial_average_3D(img, kernel_size=3)
            elif args.spatial_avg == 2:
                img = spatial_average_2D(img, apply_2D_mean_filter, kernel_size=(3, 3))

            # Rolling ball background subtraction
            rb_img = rolling_ball_subtraction_opencv_parallel(img, radius=args.rb_radius, threads=args.threads)  

            # Resample the rb_img to the resolution of registration (and optionally reorient for compatibility with MIRACL)
            rb_img = prep_reg(rb_img, args.xy_res, args.z_res, args.reg_res, args.zoom_order, args.miracl)

            # Warp the image to atlas space
            to_atlas(sample_path, rb_img, args.fixed_reg_in, args.atlas, output, args.interpol, dtype='uint16')

            # Copy the atlas to atlas_space
            atlas_space = sample_path / "atlas_space"
            shutil.copy(args.atlas, atlas_space)
            
            if args.target_dir is not None:
                # Copy output to the target directory
                target_output = target_dir / output.name
                shutil.copy(output, target_output)

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()