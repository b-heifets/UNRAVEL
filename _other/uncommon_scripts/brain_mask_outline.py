#!/usr/bin/env python3
import argparse
import numpy as np
import nibabel as nib
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from scipy.ndimage import binary_erosion, binary_dilation

from unravel.core.argparse_utils import SM, SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.utils import get_samples, initialize_progress_bar, print_cmd_and_times

def parse_args():
    parser = argparse.ArgumentParser(description="Create and dilate the outline of a brain mask from a .nii.gz file.", formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='Default mask: reg_inputs/autofl_50um_brain_mask.nii.gz (from brain_mask.py)', default="reg_inputs/autofl_50um_brain_mask.nii.gz", action=SM)
    parser.add_argument("-dil", "--dilation", help="Number of dilation iterations to perform on the outline. Default: 0", default=0, type=int, action=SM)
    parser.add_argument("-o", "--output", help="Default: reg_inputs/autofl_50um_brain_mask_outline.nii.gz", default="reg_inputs/autofl_50um_brain_mask_outline.nii.gz", action=SM)
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    return parser.parse_args()

def create_outline(mask):
    """Create an outline mask by eroding the original mask and subtracting it from the original mask."""
    eroded_mask = binary_erosion(mask)
    outline_mask = mask.astype(np.uint8) - eroded_mask.astype(np.uint8)
    return outline_mask

def dilate_outline(outline_mask, iterations):
    """Dilate the given outline mask by a specified number of iterations."""
    dilated_outline = binary_dilation(outline_mask, iterations=iterations)
    return dilated_outline

def main():

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            if Path(args.input).is_absolute():
                input_path = Path(args.input)
            else:
                input_path = Path(sample_path / args.input)

            # Load the brain mask
            mask_nii = nib.load(input_path)
            mask_img = np.asanyarray(mask_nii.dataobj, dtype=np.bool_).squeeze()
            
            # Create the outline mask
            outline_mask = create_outline(mask_img)
            
            # Dilate the outline mask
            if args.dilation > 0: 
                outline_mask = dilate_outline(outline_mask, args.dilation)
            
            # Save the dilated outline
            outline_nii = nib.Nifti1Image(outline_mask.astype(np.uint8), mask_nii.affine, mask_nii.header)
            output = sample_path / args.output
            nib.save(outline_nii, output)

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()