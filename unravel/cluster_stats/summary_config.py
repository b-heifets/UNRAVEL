#!/usr/bin/env python3

"""
Use ``cstats_summary_config`` (``csc``) copy a cluster_summary.ini config file from UNRAVEL to a new location.
    
Usage:
------
    cstats_summary_config -o path/to/output_dir
"""

import shutil
from pathlib import Path
from rich.traceback import install
from rich import print

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.utils import log_command


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-o', '--output', help='Path to save the cluster_summary.ini config file. Default: current working directory', default=None, action=SM)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()

    config_path = Path(__file__).parent.parent / 'cluster_stats' / 'cluster_summary.ini'
   
    # Copy the cluster_summary.ini file to the new location
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path.cwd() / 'cluster_summary.ini'
    shutil.copyfile(config_path, output_path)

    print(f"\n    Copied cluster_summary.ini to {output_path}\n")


if __name__ == '__main__':
    main()