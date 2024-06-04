#!/usr/bin/env python3

import argparse
from pathlib import Path
import shutil

from unravel.core.argparse_utils import SuppressMetavar, SM


def find_and_copy_files(pattern, src_dir, dest_dir):
    src_dir = Path(src_dir)
    dest_dir = Path(dest_dir)
    if not dest_dir.is_absolute():
        dest_dir = src_dir.joinpath(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    for file_path in src_dir.rglob(pattern): # Use rglob for recursive globbing
        if dest_dir not in file_path.parents:
            shutil.copy(str(file_path), dest_dir)
            # print(f"Copied: {file_path} to {dest_dir}")

def main():
    parser = argparse.ArgumentParser(description="Recusively copy files matching a pattern.", formatter_class=SuppressMetavar)
    parser.add_argument("-p", "--pattern", help="The pattern to match files, e.g., '*.txt'", required=True, action=SM)
    parser.add_argument("-s", "--source", help="The source directory to search files in. Default: current working dir", default=".", action=SM)
    parser.add_argument("-d", "--destination", help="The destination directory to copy files to. Default: current working dir", default=".", action=SM)
    args = parser.parse_args()

    find_and_copy_files(args.pattern, args.source, args.destination)

if __name__ == "__main__":
    main()
