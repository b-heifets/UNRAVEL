#!/usr/bin/env python3

"""
Use ``io_metadata`` from UNRAVEL to save x/y and z voxel sizes in microns as well as image dimensions to a metadata file in each sample directory.

Inputs:
    - .czi, .nii.gz, .h5, or TIF series (path should be relative to ./sample??)

Outputs:
    - ./parameters/metadata.txt (path should be relative to ./sample??)

Note:
    - If -d is not provided, the current directory is used to search for sample?? dirs to process. 
    - If the current dir is a sample?? dir, it will be processed.
    - If -d is provided, the specified dirs and/or dirs containing sample?? dirs will be processed.
    - If -p is not provided, the default pattern for dirs to process is 'sample??'.

Next command:
    - ``reg_prep`` for prepping autofluo images for registration

Usage for when metadata is extractable:
---------------------------------------
    io_metadata -i rel_path/full_res_img [-m parameters/metadata.txt] [-d space-separated list of paths] [-p pattern] [-v]

Usage for when metadata is not extractable:
-------------------------------------------
    io_metadata -i tif_dir -x 3.5232 -z 6 [-m parameters/metadata.txt] [-d space-separated list of paths] [-p pattern] [-v]
"""

from pathlib import Path
import cv2
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, resolve_path, save_metadata_to_file
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples, initialize_progress_bar


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/full_res_img (path relative to ./sample??). Can use glob patterns.', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-m', '--metad_path', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    opts.add_argument('-x', '--xy_res', help='xy resolution in um', type=float, default=None, action=SM)
    opts.add_argument('-z', '--z_res', help='z resolution in um', type=float, default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
   
    return parser.parse_args()


def print_metadata(metadata_path):
    with open(metadata_path, "r") as f:
        contents = f.read()
    print(f'\n{contents}\n')

def get_dims_from_tifs(tifs_path):
    # Get dims quickly from full res tifs (Using a generator without converting to a list to be memory efficient)
    tifs = Path(tifs_path).resolve().glob("*.tif") # Generator
    tif_file = next(tifs, None) # First item in generator
    tif_img = cv2.imread(str(tif_file), cv2.IMREAD_UNCHANGED) # Load first tif
    x_dim, y_dim, z_dim = (tif_img.shape[1], tif_img.shape[0], sum(1 for _ in tifs) + 1) # For z count tifs + 1 (next() uses 1 generator item)
    return x_dim, y_dim, z_dim


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

            # Resolve path to image
            img_path = resolve_path(sample_path, path_or_pattern=args.input)

            # Resolve path to metadata file
            metadata_path = resolve_path(sample_path, path_or_pattern=args.metad_path, make_parents=True)

            if metadata_path.exists():
                print(f'\n\n{metadata_path} exists. Skipping...')
                print_metadata(metadata_path)
            else: 
                # Load image and save metadata to file
                if img_path.exists():
                    if img_path.is_dir and args.xy_res is not None and args.z_res is not None:
                        x_dim, y_dim, z_dim = get_dims_from_tifs(img_path)
                        save_metadata_to_file(args.xy_res, args.z_res, x_dim, y_dim, z_dim, save_metadata=metadata_path)
                    else: 
                        load_3D_img(img_path, desired_axis_order="xyz", xy_res=args.xy_res, z_res=args.z_res, return_metadata=True, save_metadata=metadata_path)
                        print(f'\n\n{metadata_path}:')
                        print_metadata(metadata_path)
                else:
                    print(f"    [red1]No match found for {args.input} in {sample_path}. Skipping...")

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()