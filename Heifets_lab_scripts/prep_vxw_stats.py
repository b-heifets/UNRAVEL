#!/usr/bin/env python3

import argparse
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_img_io import load_3D_img, resolve_path
from unravel_img_tools import rolling_ball_subtraction_opencv_parallel
from unravel_utils import print_cmd_and_times, initialize_progress_bar, get_samples
from to_atlas import to_atlas

def parse_args():
    parser = argparse.ArgumentParser(description='Loads immunofluo image, subracts background, and warps to atlas space', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)

    # Required arguments:
    parser.add_argument('-i', '--input', help='path to full res image', required=True, action=SM)

    # Optional arguments:
    parser.add_argument('-o', '--output', help='Output file name (Default: <sample??>_<label>_rb<4>_<gubra>_space.nii.gz) or path rel to sample??', default=None, action=SM)
    parser.add_argument('-l', '--label', help='Fluorescent label (e.g., cfos). Default: ochann)', default="ochann", action=SM)
    parser.add_argument('-rb', '--rb_radius', help='Radius of rolling ball in pixels (Default: 4)', default=4, type=int, action=SM)
    parser.add_argument('-an', '--atlas_name', help='Name of atlas (Default: gubra)', default="gubra", action=SM)
    parser.add_argument('-x', '--xy_res', help='Native x/y voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='Native z voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-c', '--chann_idx', help='.czi channel index. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz (Default: /usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz)', default='/usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz', action=SM)
    parser.add_argument('-t', '--template', help='path/template.nii.gz (Default: /usr/local/unravel/atlases/gubra/gubra_template_25um.nii.gz)', default='/usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz', action=SM)
    parser.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from reg.py (e.g., transforms). Default: reg_outputs", default="reg_outputs", action=SM)
    parser.add_argument('-dt', '--dtype', help='Desired dtype for output (e.g., uint8, uint16). Default: args.input.dtype', default=None, action=SM)
    parser.add_argument('-ar', '--atlas_res', help='Resolution of atlas in microns. Default=25', type=int, default=25, action=SM)
    parser.add_argument('-rf', '--reg_fixed', help='Name of file in reg_outputs dir used as fixed input for registration. Default: autofl_50um_masked_fixed_reg_input.nii.gz', default='autofl_50um_masked_fixed_reg_input.nii.gz', action=SM)
    parser.add_argument('-ip', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor, genericLabel, linear, bSpline [default])', default="bSpline", action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order for resampling the native image. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-tp', '--tform_prefix', help='Prefix of transforms output from ants.registration. Default: ANTsPy_', default="ANTsPy_", action=SM)
    parser.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)
    parser.add_argument('-th', '--threads', help='Number of threads for rolling ball background subtraction. Default: 8', default=8, type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = """Run script from the experiment directory w/ sample?? dir(s) or a sample?? dir
Example usage: prep_vxw_stats.py -i ochann -rb 4 -x 3.5232 -z 6 [-mi -v]

Prereqs: 
reg.py

Input examples (path is relative to ./sample??; 1st glob match processed): 
*.czi, ochann/*.tif, ochann, *.tif, *.h5, or *.zarr

outputs: .[/sample??]/sample??_ochann_rb4_gubra_space.nii.gz or custom output path

next steps: Aggregate outputs and run vxw_stats.py"""
    return parser.parse_args()

def main():    

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            output = resolve_path(sample_path, args.output) if args.output else resolve_path(sample_path, f"{sample}_{args.label}_rb{args.rb_radius}_{args.atlas_name}_space.nii.gz")
            if output.exists():
                print(f"\n\n    {output} already exists. Skipping.\n")
                continue
            
            # Load full res image [and xy and z voxel size in microns], to be resampled [and reoriented], padded, and warped
            img_path = resolve_path(sample_path, args.input)
            img, xy_res, z_res = load_3D_img(img_path, args.chann_idx, "xyz", return_res=True, xy_res=args.xy_res, z_res=args.z_res)

            # Rolling ball background subtraction
            rb_img = rolling_ball_subtraction_opencv_parallel(img, radius=args.rb_radius, threads=args.threads)  

            # Directory with outputs from registration (e.g., transforms)
            reg_outputs_path = resolve_path(sample_path, args.reg_outputs)
            
            # Warp native image to atlas space
            to_atlas(rb_img, xy_res, z_res, reg_outputs_path, args.atlas_res, args.zoom_order, args.interpol, args.reg_fixed, args.tform_prefix, args.dtype, args.atlas, args.template, output, moving_img=None, miracl=args.miracl)

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()