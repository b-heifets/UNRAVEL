#!/usr/bin/env python3

"""
Use ``reg_compare`` (``rcmp``) from UNRAVEL to aggregate registration outputs across many samples
into one directory for side-by-side comparison (e.g., with ``reg_compare_fsleyes`` / ``rcmpf``).

This is a generalized version of reg_check which can:
    - Copy ONE autofluo (or fixed reg input) per sample
    - Copy MULTIPLE atlas outputs per sample from multiple reg_outputs* folders
    - Prepend the sample ID to each copied file
    - Add a suffix to atlas filenames to avoid collisions (default: derived from source folder name)
    - Suffix examples:
    - reg_outputs -> ''
    - reg_outputs_1 -> __1
    - reg_outputs_2 -> __2

Note:
    - Existing files in the target directory are overwritten when recopied
    - Files no longer produced are left untouched.

Usage:
------
    reg_compare [-td <path/target_output_dir>] [-afd <autofl_dir>] [-afn <autofl_name>] [-as folder:file ...] [--suffix_map folder=suffix ...] [-d list of paths] [-p sample??] [-v]

Usage for aggregating registration outputs:
--------------
    rcmp -td reg_compare -ro 'reg_outputs<asterisk>' -afd reg_outputs [-d list of paths] [-p sample??] [-v]
"""

from pathlib import Path

from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples, copy_files


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-td', '--target_dir', help='Path/name of target directory for aggregating outputs. Default: reg_compare', default='reg_compare', action=SM)
    opts.add_argument('-afd', '--autofl_dir', help='Folder (relative to sample dir) containing the single autofluo/fixed-reg-input file. Default: reg_outputs', default='reg_outputs', action=SM)
    opts.add_argument('-afn', '--autofl_name', help='Filename (within --autofl_dir) to copy once per sample. Default: autofl_50um_masked_fixed_reg_input.nii.gz', default='autofl_50um_masked_fixed_reg_input.nii.gz', action=SM)
    opts.add_argument('-ro', '--reg_outputs', help='Space-separated list of reg_outputs folder names or globs (relative to sample dir) to copy atlas files from. Default: reg_outputs', default=['reg_outputs'], nargs='*', action=SM)
    opts.add_argument('-an', '--atlas_name', help='Warped atlas filename (within each reg_outputs dir). Default: atlas_CCFv3_2020_30um_in_tissue_space.nii.gz', default='atlas_CCFv3_2020_30um_in_tissue_space.nii.gz', action=SM)
    opts.add_argument('-sm', '--suffix_map', help="Optional: overrides suffixes based on -ro. Provide as folder=suffix pairs.", nargs='*', default=[], action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Consider redundancy with reg_check.py (perhaps deprecate reg_check in favor of this more general tool after testing, including missing features, and maybe simplifying)

def _parse_suffix_map(items: list[str]) -> dict[str, str]:
    m: dict[str, str] = {}
    for it in items:
        if '=' not in it:
            raise ValueError(f"Invalid --suffix_map entry (expected folder=suffix): {it}")
        folder, suffix = it.split('=', 1)
        folder = folder.strip()
        suffix = suffix.strip()
        if not folder:
            raise ValueError(f"Invalid --suffix_map entry (empty folder): {it}")
        # allow empty suffix intentionally (e.g., reg_outputs=)
        m[folder] = suffix
    return m


def _default_suffix_from_folder(folder: str) -> str:
    # Based on docstring examples:
    #   reg_outputs   -> ''
    #   reg_outputs_1 -> __1
    #   reg_outputs_2 -> __2
    if folder == 'reg_outputs':
        return ''
    if folder.startswith('reg_outputs_'):
        return '__' + folder.replace('reg_outputs_', '', 1)
    # Fallback: stable + collision-resistant
    return '__' + folder


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    target_dir = Path(args.target_dir)
    target_dir.mkdir(exist_ok=True, parents=True)

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    # Build suffix map (overrides) + derive defaults
    try:
        suffix_overrides = _parse_suffix_map(args.suffix_map)
    except Exception as e:
        print(f'[red]Error:[/red] {e}')
        return

    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:
            sample_id = sample_path.name

            # Expand reg_outputs globs per sample
            reg_output_paths = match_files(args.reg_outputs, base_path=sample_path)
            reg_outputs_dirs = [p.name for p in reg_output_paths if p.is_dir()]

            # 1) Copy the single autofl/fixed-reg-input file
            autofl_copied = False

            # First: try --autofl_dir explicitly
            primary_source = sample_path / args.autofl_dir
            src_file = primary_source / args.autofl_name
            if src_file.exists():
                copy_files(primary_source, target_dir, args.autofl_name, sample_path, args.verbose)
                autofl_copied = True
            else:
                # Fallback: search reg_outputs folders (in order)
                for folder in reg_outputs_dirs:
                    fallback_source = sample_path / folder
                    fallback_file = fallback_source / args.autofl_name
                    if fallback_file.exists():
                        if args.verbose:
                            print(
                                f'[yellow]Autofl fallback:[/yellow] '
                                f'using {fallback_file} instead of {src_file}'
                            )
                        copy_files(fallback_source, target_dir, args.autofl_name, sample_path, args.verbose)
                        autofl_copied = True
                        break

            if not autofl_copied and args.verbose:
                print(
                    f'[yellow]Autofl not found:[/yellow] '
                    f'{args.autofl_name} not found in {args.autofl_dir} or any reg_outputs folders'
                )

            # 2) Copy atlas outputs from each reg_outputs* folder, with suffix to avoid collisions
            for folder in reg_outputs_dirs:
                source_path = sample_path / folder
                atlas_path = source_path / args.atlas_name

                if not atlas_path.exists():
                    if args.verbose:
                        print(f'[yellow]Missing:[/yellow] {atlas_path}')
                    continue

                suffix = suffix_overrides.get(folder, _default_suffix_from_folder(folder))

                # Build destination name:
                #   <sample>_<atlas_basename><suffix>.nii.gz
                # If atlas_name ends with .nii.gz, insert suffix before .nii.gz; otherwise before final suffix.
                atlas_name = Path(args.atlas_name).name

                if atlas_name.endswith('.nii.gz'):
                    stem = atlas_name[:-7]
                    ext = '.nii.gz'
                else:
                    p = Path(atlas_name)
                    stem = p.stem
                    ext = p.suffix

                dest_name = f'{sample_id}_{stem}{suffix}{ext}'
                dest_path = target_dir / dest_name

                # Copy (explicit destination name to avoid collisions)
                dest_path.write_bytes(atlas_path.read_bytes())

                if args.verbose:
                    print(f'[green]Copied:[/green] {atlas_path} -> {dest_path}')

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()