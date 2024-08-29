#!/usr/bin/env python3


"""
Use ``utils_agg_files`` from UNRAVEL to aggregate files from sample?? directories to a target directory.

Usage for when sample?? is already in the name of files being copied:
---------------------------------------------------------------------
    utils_agg_files -g 'atlas_space/`*`_cfos_rb4_30um_CCF_space_z_LRavg.nii.gz' [-td target_output_dir] [-d list of paths] [-p sample??] [-v]

Usage to prepend sample?? to the name of files being copied:
------------------------------------------------------------
    utils_agg_files -g 'atlas_space/cfos_rb4_30um_CCF_space_z_LRavg.nii.gz' -a [-td target_output_dir] [-d list of paths] [-p sample??] [-v]
"""

import shutil
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-g', '--glob_pattern', help='Glob pattern to match files within sample?? directories', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-td', '--target_dir', help='path/target_dir name for gathering files. Default: current working dir', default=None, action=SM)
    opts.add_argument('-a', '--add_prefix', help='Add "sample??_" prefix to the output files', action='store_true')

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def aggregate_files_from_sample_dirs(sample_path, glob_pattern, target_dir, add_prefix=False, verbose=False):
    # Use glob to find files matching the pattern
    if len(list(sample_path.glob(glob_pattern))) == 0:
        print(f"\n    [red1]No files found matching the pattern:[/] [bold]{glob_pattern}[/] in {sample_path}\n")
        return

    for src_path in sample_path.glob(glob_pattern):
        
        if add_prefix: 
            target_output = target_dir / f"{sample_path.name}_{src_path.name}"
            if verbose:
                print(f"Copying {src_path.name} as {target_output.name}")
        else:
            target_output = target_dir / src_path.name
            if verbose:
                print(f"Copying {src_path}")

        if src_path.exists():
            shutil.copy(src_path, target_output)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if args.target_dir is None:
        target_dir = Path().cwd()
    else: 
        target_dir = Path(args.target_dir)
        target_dir.mkdir(exist_ok=True, parents=True)

    if args.verbose: 
        print(f'\nCopying files to: {target_dir}\n')

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:

            aggregate_files_from_sample_dirs(sample_path, args.glob_pattern, target_dir, args.add_prefix, args.verbose)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()