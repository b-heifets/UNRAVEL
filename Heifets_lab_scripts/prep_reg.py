#!/usr/bin/env python3

import argparse
import numpy as np
from unravel_config import Configuration 
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from unravel_img_tools import load_3D_img, resample_reorient, save_as_tifs, save_as_nii
from unravel_utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Load channel of ./*.czi (default; assumes 1 .czi in working dir) or ./<tif_dir>/*.tif, resample, reorient, and save as ./niftis/<img>.nii.gz')
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process.', nargs='*', default=None, metavar='')
    parser.add_argument('-t', '--tif_dir', help='Name of folder in sample folder or working directory with raw autofluo tifs. Use as image input if *.czi does not exist. Default: autofl_tifs', default="autofl_tifs", metavar='')
    parser.add_argument('-ri', '--reg_input', help='Output directory for registration input(s). Default: reg_input', default='reg_input', metavar='')
    parser.add_argument('-o', '--output', help='Output file name. Default: autofl_<res>_um.nii.gz', default=None, metavar='')
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 0 for autofluo', default=0, type=int, metavar='')
    parser.add_argument('-x', '--xy_res', help='x/y voxel size in microns. Default: get via metadata', default=None, type=float, metavar='')
    parser.add_argument('-z', '--z_res', help='z voxel size in microns. Default: get via metadata', default=None, type=float, metavar='')
    parser.add_argument('-r', '--res', help='Resample to this resolution in microns. Default: 50', default=50, type=int, metavar='')
    parser.add_argument('-zo', '--zoom_order', help='Order of spline interpolation (scipy.ndimage.zoom). Range: 0-5. Default: 1', default=1, type=int, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = "From experiment dir w/ sample?? folders run: prep_reg.py; Outputs: .[/sample??]/reg_input/autofl_*um.nii.gz and .[/sample??]/reg_input/autofl_*um_tifs/slice_????.tif series"
    return parser.parse_args()


@print_func_name_args_times()
def prep_reg(sample, args):
    """Preps inputs for brain_mask.py and atlas registration (reg.py)"""

    # Skip processing if output exists
    output = args.output if args.output else f"autofl_{args.res}um.nii.gz" # e.g., autofl_50um.nii.gz
    output = Path(sample, args.reg_input, output).resolve() # e.g., ./sample01/reg_input/autofl_50um.nii.gz
    if output.exists():
        print(f"\n\n    {output} already exists. Skipping.\n")
        return # Skip to next sample

    # Load autofluo image
    if glob(f"{sample}/*.czi"): 
        img, xy_res, z_res = load_3D_img(Path(sample).resolve(), args.channel, "xyz")
    else:
        img, xy_res, z_res = load_3D_img(Path(sample, args.tif_dir).resolve(), "xyz")

    # If resolution not extracted from metadata, use args.xy_res and args.z_res
    if xy_res is None or z_res is None:
        xy_res, z_res = args.xy_res, args.z_res
    
    # Resample and reorient image
    img_reoriented = resample_reorient(img, xy_res, z_res, args.res, zoom_order=args.zoom_order)
    img_reoriented = np.transpose(img_reoriented, (2, 1, 0))

    # Save autofl image as tif series (for brain_mask.py)
    tif_dir_out = Path(sample, args.reg_input, str(output).replace('.nii.gz', '_tifs')).resolve() # e.g., ./sample01/reg_input/autofl_50um_tifs
    tif_dir_out.mkdir(parents=True, exist_ok=True)
    save_as_tifs(img_reoriented, tif_dir_out, "xyz")

    # Save autofl image (for reg.py if skipping brain_mask.py and for applying the brain mask)
    save_as_nii(img_reoriented, output, args.res, args.res, args.res, np.uint16)
    return


def main():

    samples = get_samples(args.dirs, args.pattern)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            prep_reg(sample, args)
            progress.update(task_id, advance=1)


if __name__ == '__main__':
    from rich.traceback import install
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()