#!/usr/bin/env python3

import argparse
import numpy as np
from config import Configuration 
from pathlib import Path
from rich import print
from rich.live import Live
from unravel_img_tools import ilastik_segmentation, load_tifs, load_nii, save_as_nii
from unravel_utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Before running brain_mask.py, train ilastik (tissue = label 1) using tifs from ./sample??/reg_input/autofl_*um_tifs/*.tif (from prep_reg.py)')
    parser.add_argument('-p', '--pattern', help='Pattern for folders in the working dir to process. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process. If not provided, --pattern used for matching dirs to process. If no matches, the current directory is used.', nargs='*', default=None, metavar='')
    parser.add_argument('-ri', '--reg_input', help='Output directory (located in ./sample??). Default: reg_input', default='reg_input', metavar='')
    parser.add_argument('-i', '--input', help='autofl.nii.gz input to mask. Default: autofl_<res>_um.nii.gz', default='autofl_50um.nii.gz', metavar='')
    parser.add_argument('-td', '--tif_dir', help='Directory containing tif series for segmentation. Default: autofl_50um_tifs', default="autofl_50um_tifs", metavar='')
    parser.add_argument('-ilp', '--ilastik_prj', help='path/trained_ilastik_project.ilp. label 1 should = tissue. Default: brain_mask.ilp (assumes ilp is in exp dir).', default='brain_mask.ilp', metavar='')
    parser.add_argument('-o', '--output', help='Output file name. Default: autofl_<res>um_masked.nii.gz', default=None, metavar='')
    parser.add_argument('-r', '--res', help='Resolution of autofluo input image in microns. Default: 50', default=50, type=int, metavar='')
    parser.add_argument('-l', '--ilastik_log', help='Show Ilastik log', action='store_true')
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = "From exp dir run: brain_mask.py; Outputs: ./reg_input/autofl_50um_tifs_ilastik_brain_seg/slice_????.tif series, ./reg_input/autofl_50um_brain_mask.nii.gz, and ./reg_input/autofl_50um_masked.nii.gz"
    return parser.parse_args()

@print_func_name_args_times(arg_index_for_basename=0)
def brain_mask(sample, args):
    """Segment brain in autofluo image with Ilastik and apply mask."""

    cwd = Path(".").resolve()

    autofl_masked_output_name = args.output if args.output else f"autofl_{args.res}um_masked.nii.gz"
    autofl_masked_img = Path(sample, args.reg_input, autofl_masked_output_name).resolve() if sample != cwd.name else Path(args.reg_input, autofl_masked_output_name).resolve()

    if autofl_masked_img.exists():
        print(f"\n\n    {autofl_masked_img} already exists. Skipping.\n")
        return

    autofl_tif_directory = Path(sample, args.reg_input, args.tif_dir).resolve() if sample != cwd.name else Path(args.reg_input, args.tif_dir).resolve()
 
    # brain_mask.ilp assumed to be in experiment dir by default
    if args.ilastik_prj == 'brain_mask.ilp': 
        ilastik_project = Path(cwd, args.ilastik_prj).resolve() if sample != cwd.name else Path(cwd.parent, args.ilastik_prj).resolve()
    else:
        ilastik_project = Path(args.ilastik_prj)

    output_dir_name = args.output if args.output else f"{autofl_tif_directory.name}_ilastik_brain_seg"
    seg_output_dir = Path(sample, args.reg_input, output_dir_name).resolve() if sample != cwd.name else Path(args.reg_input, output_dir_name).resolve()

    ilastik_segmentation(str(autofl_tif_directory), str(ilastik_project), str(seg_output_dir), args.ilastik_log)

    # Load brain mask image
    seg_dir = Path(sample, args.reg_input, f"{args.tif_dir}_ilastik_brain_seg").resolve() if sample != cwd.name else Path(args.reg_input, f"{args.tif_dir}_ilastik_brain_seg").resolve()
    seg_img = load_tifs(seg_dir, "xyz")

    # Convert anything voxels to 0 if > 1 (label 1 = tissue; other labels converted to 0)
    brain_mask = np.where(seg_img > 1, 0, seg_img)

    # Save brain mask as nifti
    autofl_name = args.input.replace('.nii.gz', '') if args.input else f"autofl_{args.res}um"
    brain_mask_path = Path(sample, args.reg_input, f"{autofl_name}_brain_mask.nii.gz").resolve() if sample != cwd.name else Path(args.reg_input, f"{autofl_name}_brain_mask.nii.gz").resolve()
    save_as_nii(brain_mask, brain_mask_path, args.res, args.res, args.res, np.uint8)

    # Load autofl image
    autofl_img_path = Path(sample, args.reg_input, f"{autofl_name}.nii.gz").resolve() if sample != cwd.name else Path(args.reg_input, f"{autofl_name}.nii.gz").resolve()
    autofl_img = load_nii(autofl_img_path)

    # Apply brain mask to autofluo image
    autofl_masked = np.where(seg_img == 1, autofl_img, 0)



    print("Before save masked autofl image")

    # Save masked autofl image
    masked_autofl_output = Path(sample, args.reg_input, f"autofl_{args.res}um_masked.nii.gz") if sample != cwd.name else Path(args.reg_input, f"autofl_{args.res}um_masked.nii.gz")
    save_as_nii(autofl_masked, masked_autofl_output, args.res, args.res, args.res, np.uint16)
                
    print(f'\n{masked_autofl_output=}\n')


def main():

    samples = get_samples(args.dirs, args.pattern)
    
    if samples == ['.']:
        wd = Path.cwd()
        samples[0] = wd.name

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            brain_mask(sample, args)
            progress.update(task_id, advance=1)


if __name__ == '__main__':
    from rich.traceback import install
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
