#!/usr/bin/env python3

"""
Use ``reg_prep`` (``rp``) from UNRAVEL to load a full resolution autofluo image and resamples to a lower resolution for registration.

Input examples (path is relative to ./sample??; 1st glob match processed): 
    `*`.czi, autofluo/`*`.tif series, autofluo, `*`.tif, or `*`.h5 

Outputs: 
    ./sample??/reg_inputs/autofl_`*`um.nii.gz
    ./sample??/reg_inputs/autofl_`*`um_tifs/`*`.tif series (used for training ilastik for ``seg_brain_mask``)

Note:
    - If -d is not provided, the current directory is used to search for sample?? dirs to process. 
    - If the current dir is a sample?? dir, it will be processed.
    - If -d is provided, the specified dirs and/or dirs containing sample?? dirs will be processed.
    - If -p is not provided, the default pattern for dirs to process is 'sample??'.

Next command: 
    ``seg_copy_tifs`` for ``seg_brain_mask`` or ``reg``

Usage:
------
    reg_prep -i `*`.czi [-md path/metadata.txt] [For .czi: --channel 0] [-o reg_inputs/autofl_50um.nii.gz] [--reg_res 50] [--zoom_order 0] [--miracl] [-d list of paths] [-p sample??] [-v]
"""

import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_3D_img, load_image_metadata_from_txt, resolve_path, save_as_tifs, save_as_nii
from unravel.core.img_tools import resample, reorient_axes
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples, print_func_name_args_times


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Full res autofluo image input path relative (rel_path) to ./sample??', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-md', '--metadata', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    opts.add_argument('-c', '--channel', help='Channel number. Default: 0', default=0, type=int, action=SM)
    opts.add_argument('-o', '--output', help='Output path. Default: reg_inputs/autofl_50um.nii.gz', default="reg_inputs/autofl_50um.nii.gz", action=SM)
    opts.add_argument('-r', '--reg_res', help='Resample input to this res in um for reg. Default: 50', default=50, type=int, action=SM)
    opts.add_argument('-zo', '--zoom_order', help='Order for resampling (scipy.ndimage.zoom). Default: 1', default=1, type=int, action=SM)

    compatability = parser.add_argument_group('Compatability options')
    compatability.add_argument('-mi', '--miracl', help="Include reorientation step to mimic MIRACL's tif to .nii.gz conversion. Default: False", action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@print_func_name_args_times()
def reg_prep(ndarray, xy_res, z_res, reg_res, zoom_order, miracl):
    """Prepare the autofluo image for ``reg`` or mimic preprocessing  for ``vstats_prep``.
    
    Args:
        - ndarray (np.ndarray): full res 3D autofluo image.
        - xy_res (float): x/y resolution in microns of ndarray.
        - z_res (float): z resolution in microns of ndarray.
        - reg_res (int): Resample input to this resolution in microns for ``reg``.
        - zoom_order (int): Order for resampling (scipy.ndimage.zoom).
        - miracl (bool): Include reorientation step to mimic MIRACL's tif to .nii.gz conversion.
        
    Returns:
        - img_resampled (np.ndarray): Resampled image."""

    # Resample autofluo image (for registration)
    img_resampled = resample(ndarray, xy_res, z_res, reg_res, zoom_order=zoom_order)

    # Optionally reorient autofluo image (mimics MIRACL's tif to .nii.gz conversion)
    if miracl: 
        img_resampled = reorient_axes(img_resampled)

    return img_resampled


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

            # Define output
            output = resolve_path(sample_path, args.output, make_parents=True)
            if output.exists():
                print(f"\n\n    {args.output} already exists. Skipping.\n")
                continue
            
            # Define input image path
            img_path = resolve_path(sample_path, args.input)

            # Load resolutions from metadata
            metadata_path = sample_path / args.metadata
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(metadata_path)
            if xy_res is None:
                print("    [red1]./sample??/parameters/metadata.txt is missing. Generate w/ io_metadata")
                import sys ; sys.exit()

            # Load full res autofluo image
            img = load_3D_img(img_path, args.channel, verbose=args.verbose)

            # Prepare the autofluo image for registration
            img_resampled = reg_prep(img, xy_res, z_res, args.reg_res, args.zoom_order, args.miracl)

            # Save the prepped autofluo image as tif series (for ``seg_brain_mask``)
            tif_dir = Path(str(output).replace('.nii.gz', '_tifs'))
            tif_dir.mkdir(parents=True, exist_ok=True)
            save_as_tifs(img_resampled, tif_dir, "xyz")

            # Save the prepped autofl image (for ``reg`` if skipping ``seg_brain_mask`` and for applying the brain mask)
            save_as_nii(img_resampled, output, args.reg_res, args.reg_res, np.uint16)

            progress.update(task_id, advance=1)

    verbose_end_msg()
    

if __name__ == '__main__':
    main()
