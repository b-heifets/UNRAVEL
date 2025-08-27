#!/usr/bin/env python3


"""
Use ``utils_agg_files`` (``agg``) from UNRAVEL to aggregate files from sample?? directories to a target directory.

Next commands for voxel-wise stats: 
    - If analyzing whole brains, consider using ``vstats_whole_to_avg`` to average left and right hemispheres.
    - If using side-specific z-scoring, use ``vstats_hemi_to_avg`` to average the images.
    - Prepend condition names with ``utils_prepend``.
    - Check images in FSLeyes and run ``vstats`` to perform voxel-wise stats.    

Next command for regional stats:
    - Use ``rstats_summary`` to summarize the results

Usage:
------
    utils_agg_files -i 'atlas_space/<asterisk>_cfos_rb4_30um_CCF_space_z_LRavg.nii.gz' [-td target_output_dir] [-d list of paths] [-p sample??] [-v]

Usage to prepend sample folder name to the name of files being copied:
----------------------------------------------------------------------
    utils_agg_files -i 'atlas_space/cfos_rb4_30um_CCF_space_z_LRavg.nii.gz' -a [-td target_output_dir] [-d list of paths] [-p sample??] [-v]
"""

import shutil
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path(s) or glob pattern(s) to files relative to sample?? directories', required=True, nargs='*', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-td', '--target_dir', help='path/target_dir name for gathering files. Default: current working dir', default=None, action=SM)
    opts.add_argument('-a', '--add_prefix', help='Add "sample??_" prefix to the output files', action='store_true')

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: If a path is provided starting with a '/', a warning should be printed that the path should be relative (w/o the leading '/').

def aggregate_files_from_sample_dirs(sample_path, pattern, target_dir, add_prefix=False, verbose=False):

    src_paths = match_files(pattern, sample_path)

    for src_path in src_paths:

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

    if str(args.input).startswith('/'):
        print(f"\n    [red1]The input path should be relative (w/o the leading '/'):[/] [bold]{args.input}[/]\n")
        return

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

            aggregate_files_from_sample_dirs(sample_path, args.input, target_dir, args.add_prefix, args.verbose)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()