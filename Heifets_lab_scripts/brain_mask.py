#!/usr/bin/env python3

import argparse
import unravel_utils as unrvl
from pathlib import Path
from rich import print
import subprocess


def parse_args():
    parser = argparse.ArgumentParser(description='Before running brain_mask.py, train ilastik using tifs from ./sample??/niftis/autofl_50um/*.tif (from prep_reg.sh)')
    parser.add_argument('--dir_pattern', help='Pattern for folders in working dir to process (Default: sample??)', default='sample??', metavar='')
    parser.add_argument('--dir_list', help='Folders to process in working dir (e.g., sample01 sample02) (Default: process sample??) ', nargs='+', default=None, metavar='')
    parser.add_argument('-i', '--ilp', help='path/trained_ilastik_project.ilp', default=None, metavar='')
    parser.add_argument('-t', '--tif_dir', help='Name of folder with autofluo tifs', default="autofl_50um_tifs", metavar='')
    return parser.parse_args()


@unrvl.print_func_name_args_status_duration()
def load_img_resample_reorient_save_nii(sample_dir, args=None):

    tif_input_dir = Path(sample_dir, "reg_input", args.tif_dir)

    cmd = [
    'run_ilastik.sh',
    '--headless',
    '--project', args.ilp,
    '--export_source', 'Simple Segmentation',
    '--output_format', 'tif',
    '--output_filename_format', f'reg_input/{args.tif_dir}_seg_ilastik/{{nickname}}.tif',
    tif_input_dir]

    print(f"  {cmd}")
    subprocess.run(cmd)

    print(f"\n  Output: [default bold]reg_input/{args.tif_dir}_seg_ilastik/[/]")

@unrvl.print_cmd_and_times
def main():
    args = parse_args()

    seg_path = Path("reg_input", f"{args.tif_dir}_seg_ilastik")

    unrvl.process_samples_in_dir(load_img_resample_reorient_save_nii, sample_list=args.dir_list, sample_dirs_pattern=args.dir_pattern, output=seg_path, args=args)


if __name__ == '__main__':
    main()