#!/usr/bin/env python3

import argparse
import os
import numpy as np
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from unravel_img_tools import load_czi_channel, xyz_res_from_czi, load_tifs, xyz_res_from_tif, resample_reorient, save_as_tifs, save_as_nii
from unravel_utils import print_cmd_and_times, print_func_name_args_times, get_progress_bar, get_samples

def parse_args():
    parser = argparse.ArgumentParser(description='Load channel of *.czi (default) or ./<tif_dir>/*.tif, resample, reorient, and save as ./niftis/<img>.nii.gz')
    parser.add_argument('--dirs', help='List of folders to process. If not provided, --pattern used for matching dirs to process. If no matches, the current directory is used.', nargs='*', default=None, metavar='')
    parser.add_argument('-p', '--pattern', help='Pattern for folders in the working dir to process. Default: sample??', default='sample??', metavar='')
    parser.add_argument('-t', '--tif_dir', help='Name of folder in sample folder or working directory with raw autofluo tifs. Use as image input if *.czi does not exist. Default: autofl_tifs', default="autofl_tifs", metavar='')
    parser.add_argument('-i', '--input', help='Optional: path/image.czi or path/tif_dir. If provided, the parent folder acts as the sample folder and other samples are not processed.', metavar='')
    parser.add_argument('-o', '--output', help='Output file name. Default: autofl_<res>_um.nii.gz', default=None, metavar='')
    parser.add_argument('-od', '--out_dir', help='Output directory. Default: reg_input', default='reg_input', metavar='')
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 0 for autofluo', default=0, type=int, metavar='')
    parser.add_argument('-x', '--xy_res', help='x/y voxel size in microns. Default: get via metadata', default=None, type=float, metavar='')
    parser.add_argument('-z', '--z_res', help='z voxel size in microns. Default: get via metadata', default=None, type=float, metavar='')
    parser.add_argument('-r', '--res', help='Resample to this resolution in microns. Default: 50', default=50, type=int, metavar='')
    parser.add_argument('-zo', '--zoom_order', help='Order of spline interpolation (scipy.ndimage.zoom). Range: 0-5. Default: 1', default=1, type=int, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = "From exp dir run: prep_reg.py; Outputs: .[/sample??]/reg_input/autofl_*um.nii.gz and .[/sample??]/reg_input/autofl_*um_tifs/slice_????.tif series"
    return parser.parse_args()

@print_func_name_args_times(arg_index_for_basename=0)
def prep_reg(sample, args):
    """Preps inputs for brain_mask.py and atlas registration (reg.py)"""

    # Check if the output file already exists and skip if it does
    local_output = args.output if args.output else f"autofl_{args.res}um.nii.gz"
    local_out_dir = args.out_dir if args.out_dir else "reg_input"
    output = Path(sample, local_out_dir, local_output).resolve()
    if output.exists():
        print(f"\n\n    {output} already exists. Skipping.\n")
        return # Skip to next sample

    # Load autofluo image
    xy_res, z_res = args.xy_res, args.z_res
    czi_files = glob(f"{sample}/*.czi")
    if czi_files:
        czi_path = Path(czi_files[0]).resolve() 
        img = load_czi_channel(czi_path, args.channel)
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
    
    # Resample and reorient image
    img_reoriented = resample_reorient(img, xy_res, z_res, args.res, zoom_order=args.zoom_order)

    # Save autofl image as tif series (for brain_mask.py)
    tif_dir_out = Path(sample, args.out_dir, str(output).replace('.nii.gz', '_tifs')).resolve() # e.g., ./sample01/reg_input/autofl_50um_tifs
    tif_dir_out.mkdir(parents=True, exist_ok=True)
    save_as_tifs(img_reoriented, tif_dir_out)

    # Save autofl image (for reg.py if skipping brain_mask.py and for applying the brain mask)
    save_as_nii(img_reoriented, output, args.res, args.res, args.res, np.uint16)
    return

def main():
    if args.input:
        sample = Path(args.input).parent.resolve()
        prep_reg(sample, args)
        return

    samples = get_samples(args.dirs, args.pattern)

    progress = get_progress_bar(total_tasks=len(samples))
    task_id = progress.add_task("Processing samples...", total=len(samples))
    
    with Live(progress):
        for sample in samples:
            prep_reg(sample, args)
            progress.update(task_id, advance=1)

if __name__ == '__main__':
    from rich.traceback import install
    install()
    
    args = parse_args()
    print_cmd_and_times.verbose = args.verbose
    print_func_name_args_times.verbose = args.verbose
    
    print_cmd_and_times(main)()
