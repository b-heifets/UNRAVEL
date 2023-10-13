#!/usr/bin/env python3

import argparse
import numpy as np
from config import Configuration 
from pathlib import Path
from rich import print
from rich.live import Live
from unravel_img_tools import ilastik_segmentation, load_tifs, load_nii, save_as_nii
from unravel_utils import print_cmd_and_times, print_func_name_args_times, get_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Before running brain_mask.py, train ilastik using tifs from ./sample??/reg_input/autofl_*um_tifs/*.tif (from prep_reg.py)')
    parser.add_argument('--dirs', help='List of folders to process. If not provided, --pattern used for matching dirs to process. If no matches, the current directory is used.', nargs='*', default=None, metavar='')
    parser.add_argument('-p', '--pattern', help='Pattern for folders in the working dir to process. Default: sample??', default='sample??', metavar='')
    parser.add_argument('-i', '--input', help='path/autofl.nii.gz input to mask. Default: reg_input/autofl_50um.nii.gz', default='reg_input/autofl_50um.nii.gz', metavar='')
    parser.add_argument('-td', '--tif_dir', help='path/autofl_tif_dir containing tif series for segmentation. Default: reg_input/autofl_50um_tifs', default="reg_input/autofl_50um_tifs", metavar='')
    parser.add_argument('-ilp', '--ilastik_prj', help='path/trained_ilastik_project.ilp. label 1 should = tissue. Default: reg_input/brain_mask.ilp', default='reg_input/brain_mask.ilp', metavar='')
    parser.add_argument('-o', '--output', help='Output file name. Default: autofl_<res>um_masked.nii.gz', default=None, metavar='')
    parser.add_argument('-od', '--out_dir', help='Output directory. Default: reg_input', default='reg_input', metavar='')
    parser.add_argument('-r', '--res', help='Resolution of autofluo input image in microns. Default: 50', default=50, type=int, metavar='')
    parser.add_argument('-l', '--ilastik_log', help='Show Ilastik log', action='store_true')
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = "From exp dir, run brain_mask.py -v; Outputs: ./reg_input/autofl_50um_tifs_ilastik_brain_seg/slice_????.tif series, ./reg_input/autofl_50um_brain_mask.nii.gz, and ./reg_input/autofl_50um_masked.nii.gz"
    return parser.parse_args()


@print_func_name_args_times(arg_index_for_basename=0)
def brain_mask(sample, args):
    """Segment brain in autofluo image with Ilastik and apply mask."""
    
    # Check if the output file already exists and skip if it does
    output = Path(sample, args.out_dir, args.output).resolve()
    if output.exists():
        print(f"\n\n  {output} already exists. Skipping.\n")
        return

    # Segment brain in autofluo image with Ilastik
    if args.tif_dir == "reg_input/autofl_50um_tifs": # default
        autofl_tif_directory = str(Path(sample, args.tif_dir).resolve())
    else:
        autofl_tif_directory = str(Path(args.tif_dir).resolve())
    autofl_tif_directory_base = Path(autofl_tif_directory).name

    if args.ilastik_prj == 'reg_input/brain_mask.ilp': # default
        ilastik_project = str(Path(sample, args.ilastik_prj ).resolve()) 
    else:
        ilastik_project = args.ilastik_prj

    seg_output_dir = str(Path(sample, args.out_dir, f"{autofl_tif_directory_base}_ilastik_brain_seg").resolve())

    ilastik_segmentation(autofl_tif_directory, ilastik_project, seg_output_dir, args.ilastik_log)

    # Load brain mask image
    seg_dir = Path(sample, f"{args.tif_dir}_ilastik_brain_seg").resolve()
    seg_img = load_tifs(seg_dir)

    # Convert anything voxels to 0 if > 1 (label 1 = tissue; other labels converted to 0)
    brain_mask = np.where(seg_img > 1, 0, seg_img)

    # Save brain mask as nifti
    autofl_name = Path(args.input).stem
    brain_mask_path = Path(sample, "reg_input", f"{autofl_name}_brain_mask.nii.gz").resolve()
    save_as_nii(brain_mask, brain_mask_path, args.res, args.res, args.res, np.uint8)

    # Load autofl image
    autofl_img_path = Path(sample, args.input).resolve()
    autofl_img = load_nii(autofl_img_path)
    autofl_img_transpose = np.transpose(autofl_img, (2, 1, 0))

    # Apply brain mask to autofluo image
    autofl_masked = np.where(seg_img == 1, autofl_img_transpose, 0)

    # Save masked autofl image
    masked_autofl_output = Path(sample, "reg_input", f"autofl_{args.res}um_masked.nii.gz")
    save_as_nii(autofl_masked, masked_autofl_output, args.res, args.res, args.res, np.uint16)


def main():
    if args.input:
        sample = Path(args.input).parent.resolve()
        progress(sample, args)
        return

    samples = get_samples(args.dirs, args.pattern)

    progress = get_progress_bar(total_tasks=len(samples))
    task_id = progress.add_task("  [red]Processing samples...", total=len(samples))
    
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