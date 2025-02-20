#!/usr/bin/env python3

"""
Use ``process_samples`` (``psa``) from UNRAVEL to run a command on all samples or directories containing samples.

Notes:
    - {sample_path} and {sample} placeholders can be used in the command to refer to the sample directory path and name, respectively.
    - Likewise, {sp} and {s} can be used as shorthand for {sample_path} and {sample}, respectively.

Usage:
------
    process_samples -c "command" [-o rel_path/output] [-d list of paths] [-p sample??] [-v]
"""

import subprocess
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples, print_func_name_args_times


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-c', '--command', help='Command to run on all samples or directories containing samples.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Relative file or directory path. Skip sample if it already exists in the sample directory.', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@print_func_name_args_times()
def process_samples(command, output, dirs, pattern, verbose):
    """
    For each sample directory found by ``get_samples``, run the user-specified command.
    If ``-o/--output`` is provided and already exists in the sample directory, skip processing.
    """

    sample_paths = get_samples(dirs, pattern, verbose)

    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:

            print(f"\nProcessing sample: [bold cyan]{sample_path.name}\n")

            # If user provided an --output path (relative to sample), skip if it already exists
            if output:
                out_path = sample_path / output
                if out_path.exists():
                    print(f"\n    [dim]{out_path}[/] already exists. [bold cyan]Skipping.[/]\n")
                    progress.update(task_id, advance=1)
                    continue

            # Replace {sample} placeholder in the command if present
            cmd = command.replace('{sample_path}', str(sample_path))
            cmd = command.replace('{sp}', str(sample_path))
            cmd = cmd.replace('{sample}', str(sample_path.name))
            cmd = cmd.replace('{s}', str(sample_path.name))

            if verbose:
                print(f"\n[bold magenta]Running command:[/]\n    [bright_black]{cmd}[/]\n")

            # Run the command in a shell
            try:
                subprocess.run(
                    cmd, 
                    shell=True, 
                    check=True, 
                    cwd=sample_path  # Set working directory to sample_path
                )
            except subprocess.CalledProcessError as e:
                print(f"[red]Command failed on sample {sample_path}[/]\n{e}")
            
            progress.update(task_id, advance=1)

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    process_samples(args.command, args.output, args.dirs, args.pattern, args.verbose)


    verbose_end_msg()
    

if __name__ == '__main__':
    main()