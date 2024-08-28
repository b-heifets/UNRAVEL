#!/usr/bin/env python3

"""
Use ``seg_copy_tifs`` from UNRAVEL to copy a subset of .tif files to a target dir for training ilastik.

Usage to prep for ``seg_brain_mask``:
-------------------------------------
    seg_copy_tifs -i reg_inputs/autofl_50um_tifs -s 0000 0005 0050 -o brain_mask

Usage to prep for ``seg_ilastik`` to segment full resolution immunofluorescence images:
---------------------------------------------------------------------------------------
    seg_copy_tifs -i <raw_tif_dir> -s 0100 0500 1000 -o ilastik_segmentation
"""

import shutil
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_rich_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-o', '--output', help='rel_path/target_dir to copy TIF files to. (e.g., brain_mask or ilastik_segmentation)', required=True, action=SM)
    reqs.add_argument('-s', '--slices', help='List of slice numbers to copy (4 digits each; space separated)', nargs='*', type=str, required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help='reg_inputs/autofl_50um_tifs (from ``reg_prep``) or rel_path to dir w/ raw tifs', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them. Default: use current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def copy_specific_slices(sample_path, source_dir, target_dir, slice_numbers, verbose=False):
    """Copy the specified tif slices from the source directory to the target directory.
    
    Parameters:
    -----------
    sample_path : Path or str
        Path to the sample directory.
    source_dir : Path or str
        Path (relative to sample_path) to the source directory containing the .tif files to copy.
    target_dir : Path or str
        Path to the target directory where the selected slices will be copied.
    slice_numbers : list
        List of slice numbers to copy (4 digits each).
    verbose : bool
        Print verbose output.
    """
    source_path = Path(sample_path) / source_dir
    target_path = Path(sample_path) / target_dir

    tif_files = list(source_path.glob('*.tif'))
    if not tif_files:
        print(f"\n    [red1]No .tif files found in {source_path}\n")
        return
    
    target_path.mkdir(exist_ok=True, parents=True)

    for file_path in Path(source_dir).glob('*.tif'):
        if any(file_path.stem.endswith(f"{slice:04}") for slice in map(int, slice_numbers)):
            dest_file = target_path / f'{Path(sample_path).name}_{file_path.name}'
            shutil.copy(file_path, dest_file)
            if verbose:
                print(f"    Copied {file_path} to {dest_file}")


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

            copy_specific_slices(sample_path, args.input, args.output, args.slices, args.verbose)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()