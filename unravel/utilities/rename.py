#!/usr/bin/env python3

"""
Use ``utils_rename`` (``name``) from UNRAVEL to recursively rename files and/or directories by replacing text in filenames.

Usage: 
------
    utils_rename -o old_text -n new_text [-t files or dirs or both] [--recursive] [--dry_run] [-v]
"""

from pathlib import Path
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-o', '--old_text', type=str, help='Text to be replaced in the filenames', action=SM)
    reqs.add_argument('-n', '--new_text', type=str, help='Text to replace with in the filenames', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-t', '--type', help='Specify what to rename: "files", "dirs", or "both" (default: both)', choices=['files', 'dirs', 'both'], default='both', action=SM)
    opts.add_argument('-r', '--recursive', help='Perform the renaming recursively', action='store_true', default=False)
    opts.add_argument('-d', '--dry_run', help='Print old and new names without performing the renaming', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def rename_files(directory, old_text, new_text, recursive=False, rename_type='both', dry_run=False):
    """
    Renames files and/or directories in the specified directory, replacing old_text
    with new_text in the filenames. Can operate recursively and selectively based
    on type.

    Args:
        - directory (Path): the directory to search for files and/or directories
        - old_text (str): the text to be replaced in the filenames
        - new_text (str): the text to replace with in the filenames
        - recursive (bool): whether to perform the renaming recursively
        - rename_type (str): what to rename: "files", "dirs", or "both" (default: both)
        - dry_run (bool): if true, print changes without making them
    """
    if recursive:
        pattern = '**/*'
    else:
        pattern = '*'

    for path in Path(directory).glob(pattern):
        if (rename_type == 'both' or
            (rename_type == 'files' and path.is_file()) or
            (rename_type == 'dirs' and path.is_dir())):
            if old_text in path.name:
                new_name = path.name.replace(old_text, new_text)
                new_path = path.parent / new_name
                if dry_run:
                    print(f"Would rename '{path}' to '{new_path}'")
                else:
                    path.rename(new_path)
                    print(f"Renamed '{path}' to '{new_path}'")


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
    
    rename_files(Path().cwd(), args.old_text, args.new_text, args.recursive, args.type, args.dry_run)

    verbose_end_msg()


if __name__ == '__main__':
    main()