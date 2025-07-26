#!/usr/bin/env python3
"""
Use ``io_zarr_compress`` (``zc``) from UNRAVEL to compress or decompress `.zarr` directories to/from `.zarr.tar.gz` archives.

Note:
    - .zarr directories can have several subdirectories and files, which can be slow to transfer or index.
    - Compressing to `.zarr.tar.gz` reduces the size and speeds up transfer.
    - Decompressing restores the original `.zarr` directory structure.
    - Compression uses `tar -I pigz` if `pigz` is installed for fast, parallel gzip compression.
    - If `pigz` is not available, it falls back to standard gzip compression via `tar -czf`.

Usage for recursive compression:
--------------------------------
    zarr_compress [-i '<asterisk>.zarr'] [-m compress] [-l 6] [-f] [-k] [-w 4] [-v]

Usage for recursive decompression:
----------------------------------
    zarr_compress -m decompress [-i '<asterisk>.zarr.tar.gz'] [-w 4] [-v]
"""

import os
import shutil
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import match_files, log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help="Inputs path pattern(s): Defaults: '**/*.zarr' for compress, '**/*.zarr.tar.gz' for decompress.", nargs='*', action=SM)
    opts.add_argument('-m', '--mode', help="'compress' (or 'c') or 'decompress' (or 'd'). Default: compress", choices=['c', 'compress', 'd', 'decompress'], default='compress', action=SM)
    opts.add_argument('-l', '--level', help='Compression level (1-9). Default: 6', type=int, default=6, action=SM)
    opts.add_argument('-f', '--force',  help='Overwrite existing files if present', action="store_true", default=False)
    opts.add_argument('-k', '--keep', help='Keep the original file after processing (.zarr or .zarr.tar.gz, depending on mode). Default: remove after success', action="store_true", default=False)
    opts.add_argument('-w', '--workers', help='Number of parallel workers. Default: auto', type=int, default=None, action=SM)
    opts.add_argument('-v', '--verbose', help='Increase verbosity', action="store_true", default=False)

    return parser.parse_args()


def compress_or_decompress_zarr(zarr_path, mode='compress', compression_level=6, force=False, keep=False):
    """
    Compress or decompress a .zarr directory using gtar and pigz if available.

    Parameters
    ----------
    zarr_path : str or Path
        Path to the .zarr directory (for compression) or .zarr.tar.gz file (for decompression).
    mode : {'compress', 'compress', 'decompress', 'd'}
        Whether to compress or decompress the input.
    compression_level : int
        Compression level (1-9) for pigz. Default is 6.
    force : bool
        If True, overwrite existing output files. Default is False.
    keep : bool
        If True, keep the original .zarr directory or .tar.gz file after processing. Default is False.
    """
    zarr_path = Path(zarr_path)
    pigz_path = shutil.which("pigz")
    tar_cmd = shutil.which("gtar") or "tar"
    env = os.environ.copy()
    env["COPYFILE_DISABLE"] = "1"

    if mode == "compress" or mode == "c":
        if not zarr_path.is_dir() or not zarr_path.suffix == ".zarr":
            print(f"[red]Skipping: Not a valid .zarr directory → {zarr_path}[/red]")
            return

        out_path = zarr_path.with_suffix(".zarr.tar.gz")
        if out_path.exists() and not force:
            print(f"[cyan]Skipping {zarr_path.name} → {out_path.name}: already exists.[/cyan]")
            return

        cmd = [
            tar_cmd,
            "--exclude=.DS_Store", "--exclude=Icon\r", "--exclude=._*",
            "--warning=no-xattr", "--no-xattrs",
            "-cf", str(out_path), zarr_path.name
        ]

        if pigz_path:
            cmd.insert(1, "-I")
            cmd.insert(2, pigz_path)

        print(f"📦 Compressing {zarr_path} → {out_path}")
        subprocess.run(cmd, cwd=zarr_path.parent, check=True, env=env)

        if not keep:
            print(f"🧹 Removing original directory: {zarr_path}")
            shutil.rmtree(zarr_path)

    elif mode == "decompress" or mode == "d":
        if not zarr_path.name.endswith(".zarr.tar.gz"):
            print(f"[red]Skipping: Not a .zarr.tar.gz file → {zarr_path}[/red]")
            return

        out_path = zarr_path.with_name(zarr_path.name.replace(".tar.gz", ""))
        if out_path.exists() and not force:
            print(f"[yellow]Skipping: {out_path} already exists.[/yellow]")
            return

        print(f"🗜️ Decompressing {zarr_path} → {out_path}")
        subprocess.run([tar_cmd, "-xzf", str(zarr_path)], cwd=zarr_path.parent, check=True, env=env)

        if not keep:
            print(f"🧹 Removing original archive: {zarr_path}")
            zarr_path.unlink()

    else:
        raise ValueError(f"Invalid mode: {mode}. Use 'compress', 'c', 'decompress', or 'd'.")

def run_in_parallel(paths, func, max_workers=1, **kwargs):
    """
    Run a function over a list of paths using a ThreadPoolExecutor.

    Parameters
    ----------
    paths : list of Path
        List of input paths to process.
    func : callable
        Function to apply to each path.
    max_workers : int
        Number of threads to use. Default is 1.
    kwargs : dict
        Additional keyword arguments passed to `func`.
    """
    if max_workers == 1:
        for path in paths:
            func(path, **kwargs)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(func, path, **kwargs): path for path in paths}
            for future in as_completed(futures):
                path = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"[red]❌ Error processing {path}: {e}[/red]")


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if not (1 <= args.level <= 9):
        raise ValueError("Compression level must be between 1 and 9.")
    
    mode = args.mode.lower()
    if mode == 'c':
        mode = 'compress'
    elif mode == 'd':
        mode = 'decompress'

    input_patterns = args.input or (['**/*.zarr.tar.gz'] if mode == 'decompress' else ['**/*.zarr'])
    
    input_paths = match_files(input_patterns)

    pigz_exists = shutil.which("pigz") is not None
    cpu_count = os.cpu_count()
    if args.workers is not None:
        workers = args.workers
    elif pigz_exists:
        workers = min(2, cpu_count // 4)
    else:
        workers = min(8, cpu_count)

    run_in_parallel(
        input_paths,
        func=compress_or_decompress_zarr,
        max_workers=workers,
        mode=mode,
        compression_level=args.level,
        force=args.force,
        keep=args.keep,
    )

    verbose_end_msg()


if __name__ == "__main__":
    main()
