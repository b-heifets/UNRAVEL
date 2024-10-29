#!/usr/bin/env python3

"""
Use ``vstats_prep`` from UNRAVEL to load an immunofluo image, subtract its background, and warp it to atlas space.

Prereqs: 
    - ``reg``

Input examples (path is relative to ./sample??; 1st glob match processed): 
    - `*`.czi, ochann/`*`.tif, ochann, `*`.tif, `*`.h5, or `*`.zarr

Output example:
    - ./sample??/atlas_space/sample??_cfos_rb4_30um_CCF_space.nii.gz

Next commands for voxel-wise stats: 
    Preprocess atlas space IF images with ``vstats_z_score`` (recommended for c-Fos-IF) or aggregate them with ``utils_agg_files``.

Usage:
------
    vstats_prep -i `*`.czi -o cfos_rb4_30um_CCF_space.nii.gz [-sa 3] [-rb 4] [--channel 1] [--reg_res 50] [-fri reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz] [-a atlas/atlas_CCFv3_2020_30um.nii.gz] [-dt uint16] [-zo 1] [-inp bSpline] [-md parameters/metadata.txt] [--threads 8] [-mi] [-d list of paths] [-p sample??] [-v]
"""

import shutil
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.image_tools.spatial_averaging import apply_2D_mean_filter, spatial_average_2D, spatial_average_3D
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, load_image_metadata_from_txt
from unravel.core.img_tools import rolling_ball_subtraction_opencv_parallel
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples
from unravel.register.reg_prep import reg_prep
from unravel.warp.to_atlas import to_atlas


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path to full res image', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='Output file name w/o "sample??_" (added automatically). E.g., cfos_rb4_30um_CCF_space.nii.gz', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-sa', '--spatial_avg', help='Spatial averaging in 2D or 3D (2 or 3). Default: None', default=None, type=int, action=SM)
    opts.add_argument('-rb', '--rb_radius', help='Radius of rolling ball in pixels (Default: None)', default=None, type=int, action=SM)
    opts.add_argument('-c', '--channel', help='.czi channel index. Default: 1', default=1, type=int, action=SM)
    opts.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    opts.add_argument('-fri', '--fixed_reg_in', help='Reference nii header from ``reg``. Default: reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz', default="reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    opts.add_argument('-a', '--atlas', help='path/atlas.nii.gz (Default: atlas/atlas_CCFv3_2020_30um.nii.gz)', default='atlas/atlas_CCFv3_2020_30um.nii.gz', action=SM)
    opts.add_argument('-dt', '--dtype', help='Desired dtype for output (e.g., uint8, uint16). Default: uint16', default="uint16", action=SM)
    opts.add_argument('-zo', '--zoom_order', help='SciPy zoom order for resampling the raw image. Default: 1', default=1, type=int, action=SM)
    opts.add_argument('-inp', '--interpol', help='Type of interpolation (linear, bSpline [default]).', default='bSpline', action=SM)
    opts.add_argument('-md', '--metadata', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    opts.add_argument('-th', '--threads', help='Number of threads for rolling ball subtraction. Default: 8', default=8, type=int, action=SM)

    compatability = parser.add_argument_group('Compatability options')
    compatability.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: [default] is not showing in the help message for -inp

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:

            output_name = f"{sample_path.name}_{Path(args.output).name}"
            output = sample_path / "atlas_space" / output_name
            output.parent.mkdir(exist_ok=True, parents=True)
            if output.exists():
                print(f"\n    {output} already exists. Skipping.")
                continue
            
            # Load full res image [and xy and z voxel size in microns], to be resampled [and reoriented], padded, and warped
            img_path = next(sample_path.glob(str(args.input)), None)
            if img_path is None:
                print(f"\n    [red1]No files match the pattern {args.input} in {sample_path}\n")
                continue

            # Load resolutions from metadata
            metadata_path = sample_path / args.metadata
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(metadata_path)
            if xy_res is None:
                print("    [red1]./sample??/parameters/metadata.txt is missing. Generate w/ io_metadata")
                import sys ; sys.exit()

            img = load_3D_img(img_path, args.channel, "xyz", verbose=args.verbose)

            # Apply spatial averaging
            if args.spatial_avg == 3:
                img = spatial_average_3D(img, kernel_size=3)
            elif args.spatial_avg == 2:
                img = spatial_average_2D(img, apply_2D_mean_filter, kernel_size=(3, 3))

            # Rolling ball background subtraction
            if args.rb_radius is not None:
                img = rolling_ball_subtraction_opencv_parallel(img, radius=args.rb_radius, threads=args.threads)  

            # Resample the rb_img to the resolution of registration (and optionally reorient for compatibility with MIRACL)
            img = reg_prep(img, xy_res, z_res, args.reg_res, args.zoom_order, args.miracl)

            # Warp the image to atlas space
            fixed_reg_input = Path(sample_path, args.fixed_reg_in)    
            if not fixed_reg_input.exists():
                fixed_reg_input = sample_path / "reg_outputs" / "autofl_50um_fixed_reg_input.nii.gz"

            to_atlas(sample_path, img, fixed_reg_input, args.atlas, output, args.interpol, dtype='uint16')

            # Copy the atlas to atlas_space
            atlas_space = sample_path / "atlas_space"
            shutil.copy(args.atlas, atlas_space)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()