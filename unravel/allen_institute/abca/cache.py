#!/usr/bin/env python3

"""
Use ``abca_cache`` or ``cache`` from UNRAVEL to download data from the Allen Brain Cell Atlas.

Prereqs:
    - cd to the UNRAVEL root directory
    - pip install -e ".[abca]"

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/getting_started.html

Usage:
------
    abca_cache [-b path/to/base_dir] [-d dirs] [--dl_data] [--dl_metadata] [-f] [-s]

Usage to list directories:
--------------------------
    abca_cache

Usage to list subdirectories:
-----------------------------
    abca_cache [-d dirs]

Usage to download data:
-----------------------
    cache -d dirs -dd -dm
"""

from abc_atlas_access.abc_atlas_cache.abc_project_cache import AbcProjectCache
from abc_atlas_access.abc_atlas_cache.manifest import DataTypeNotInDirectory

from pathlib import Path
from rich import print
from rich.console import Console
from rich.table import Table
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('General arguments')
    opts.add_argument('-b', '--base', help='Path to the root directory. Default: cwd', default=None, action=SM)
    opts.add_argument('-m', '--manifest', help='Path to the manifest file. Default: latest manifest', default=None, action=SM)
    opts.add_argument('-d', '--dirs', 
                      help='Specify directories to list contents or download data/metadata depending on flags. '
                           'Use with -dd to download data, -dm to download metadata.', 
                      default=None, nargs='*', action=SM)

    down = parser.add_argument_group('Download arguments')
    down.add_argument('-df', '--dl_file', help='Specific file(s) to download', default=None, nargs='*', action=SM)
    down.add_argument('-dd', '--dl_data', help='Download data files. Default: False', action='store_true', default=False)
    down.add_argument('-dm', '--dl_metadata', help='Download metadata files. Default: False', action='store_true', default=False)

    additional_opts = parser.add_argument_group('Advanced options')
    additional_opts.add_argument('-f', '--force_download', help='Force download of files. Default: False', action='store_true', default=False)
    additional_opts.add_argument('-s', '--skip_hash', help='Skip hash check. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()

    if args.base is not None:
        download_base = Path(args.base)
    else:
        download_base = Path().cwd()

    abc_cache = AbcProjectCache.from_s3_cache(download_base)

    # List manifests
    print(f'\nCache manifests: {abc_cache.list_manifest_file_names}\n')
    if args.manifest is None:
        abc_cache.load_latest_manifest()
    else:
        abc_cache.load_manifest(args.manifest)
    print(f'\nCurrent manifest: [magenta bold]{abc_cache.current_manifest}\n')

    # Create a rich table
    console = Console()
    table = Table(title="Directory and Metadata Sizes")
    table.add_column("Directory", style="cyan", no_wrap=True)
    table.add_column("Data Size", style="green")
    table.add_column("Metadata", style="purple3")

    for dir in abc_cache.list_directories:
        try:
            data_size = abc_cache.get_directory_data_size(dir)
        except DataTypeNotInDirectory:
            data_size = '    [grey50]-'

        try:
            metadata_size = abc_cache.get_directory_metadata_size(dir)
        except DataTypeNotInDirectory:
            metadata_size = '    [grey50]-'

        table.add_row(dir, data_size, metadata_size)

    # Print the table
    console.print(table)

    # Validate that the specified directories exist
    if args.dirs is not None:
        invalid_dirs = [dir for dir in args.dirs if dir not in abc_cache.list_directories]
        if invalid_dirs:
            print(f"[red]Error: The following directories do not exist in the manifest: {', '.join(invalid_dirs)}[/red]")
            return

        for dir in args.dirs:
            print(f'\nListing files in directory: [cyan]{dir}\n')
            try:
                for file in abc_cache.list_data_files(dir):
                    print(f'    [green]{file}')
            except DataTypeNotInDirectory:
                print(f'    [grey50]No data files available in {dir}[/grey50]')

            try:
                for file in abc_cache.list_metadata_files(dir):
                    print(f'    [purple3]{file}')
            except DataTypeNotInDirectory:
                print(f'    [grey50]No metadata files available in {dir}[/grey50]')

    # Validate that the specified files exist
    if not args.dl_data and not args.dl_metadata and not args.dl_file:
        print("\n    [yellow]No download arguments provided. Exiting.\n")
        return

    # Download the data
    if args.dl_data is not None or args.dl_metadata is not None:
        for dir in args.dirs:
            print(f'\nDownloading files in directory: [cyan]{dir}\n')
            if args.dl_data:
                try:
                    data_file_path_list = abc_cache.get_directory_data(dir, force_download=args.force_download, skip_hash_check=args.skip_hash)
                    print(f'\nDownloaded data files:')
                    for file_path in data_file_path_list:
                        print(f'    [green]{file_path}')
                except DataTypeNotInDirectory:
                    print(f'    [grey50]No data files available for download in {dir}[/grey50]')

            if args.dl_metadata:
                try:
                    metadata_file_path_list = abc_cache.get_directory_metadata(dir, force_download=args.force_download, skip_hash_check=args.skip_hash)
                    print(f'\nDownloaded metadata files:')
                    for file_path in metadata_file_path_list:
                        print(f'    [purple3]{file_path}')
                except DataTypeNotInDirectory:
                    print(f'    [grey50]No metadata files available for download in {dir}[/grey50]')

            if args.dl_file is not None:
                for file in args.dl_file:
                    # Check if the file is a data file or a metadata file
                    if file in abc_cache.list_data_files(dir):
                        data_file_path_list = abc_cache.get_data_path(directory=dir, file_name=file, force_download=args.force_download, skip_hash_check=args.skip_hash)
                    elif file in abc_cache.list_metadata_files(dir):
                        metadata_file_path_list = abc_cache.get_metadata_path(directory=dir, file_name=file, force_download=args.force_download, skip_hash_check=args.skip_hash)
                    else:
                        print(f"\n    [red]Error: File {file} not found in {dir} (neither data nor metadata).\n")

if __name__ == '__main__':
    main()
