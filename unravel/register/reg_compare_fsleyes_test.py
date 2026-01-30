#!/usr/bin/env python3

"""
Use ``reg_compare_fsleyes`` (``rcmpf``) from UNRAVEL to visualize registration
results in FSLeyes for multiple samples in a single session.

Two usage modes:

1. Aggregated mode (default):
   Run inside a directory containing files named like:
       sample01_autofl_50um_masked_fixed_reg_input.nii.gz
       sample01_atlas_*_in_tissue_space*.nii.gz
   Files are grouped by sample prefix (sample??_).

2. Single-sample mode:
   Run inside a sample directory or inside a reg_outputs* directory.
   Registration outputs are loaded directly from reg_outputs* folders.

Behavior:
    - Loads one autofluo/underlay per sample (if present)
    - Loads all matching atlas overlays per sample
    - Opens one FSLeyes instance with the first sample visible

Usage:
------
    reg_compare_fsleyes [-d dir] [-af autofl_img] [-a atlas ...] [-min min_val] [-max max_val] [-l lut_name] [-al alpha_value] [-p pattern] [-v]
"""

import subprocess
from pathlib import Path

from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-d', '--dir', help='Directory containing aggregated files. Default: working directory', default=None, action=SM)
    opts.add_argument('-af', '--autofl_img', help='Glob for the single autofluo/underlay per sample (within -d). Default: *autofl_50um_masked_fixed_reg_input.nii.gz', default='*autofl_50um_masked_fixed_reg_input.nii.gz', action=SM)
    opts.add_argument('-a', '--atlas', help='One or more globs for warped atlas overlays (within -d). Default: *atlas*_in_tissue_space*.nii.gz', default=['*atlas*_in_tissue_space*.nii.gz'], nargs='*', action=SM)
    opts.add_argument('-min', '--min', help='Minimum intensity value for fsleyes display (grayscale underlay). Default: 0', type=float, default=0.0)
    opts.add_argument('-max', '--max', help='Maximum intensity value for fsleyes display (grayscale underlay). Default: 2000', type=float, default=2000.0)
    opts.add_argument('-l', '--lut', help='FSLeyes label LUT name. Default: ccfv3_2020', default='ccfv3_2020', action=SM)
    opts.add_argument('-al', '--alpha', help='Atlas overlay alpha (0-100). Default: 100', type=float, default=100.0)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-p', '--pattern', help='Pattern for filename prefix. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Consider redundancy with reg_check_fsleyes.py (perhaps deprecate reg_check_fsleyes in favor of this more general tool after testing, including missing features, and maybe simplifying)

def _glob_sorted(dir_path: Path, pattern: str) -> list[Path]:
    return sorted(dir_path.glob(pattern))


def _sample_prefix(path: Path) -> str | None:
    # expects filenames like "sample01_....nii.gz"
    name = path.name
    if name.startswith('sample') and '_' in name:
        pref = name.split('_', 1)[0] + '_'
        if pref.startswith('sample'):
            return pref
    return None


def _add_underlay(cmd: list[str], path: Path, args, visible: bool) -> None:
    cmd.extend([str(path), '-dr', str(args.min), str(args.max)])
    if not visible:
        cmd.append('-d')


def _add_atlas_overlay(cmd: list[str], path: Path, args, visible: bool) -> None:
    cmd.extend([str(path), '-ot', 'label', '-l', str(args.lut), '-o', '-a', str(args.alpha)])
    if not visible:
        cmd.append('-d')

def _strip_aggregated_prefix_glob(pat: str) -> str:
    """If pattern looks like aggregated naming (e.g., '*_foo.nii.gz'), strip '*_' for single-sample mode."""
    return pat.split('_', 1)[1] if pat.startswith('*_') else pat


def _glob_sorted_many(dirs: list[Path], pattern: str) -> list[Path]:
    out: list[Path] = []
    for d in dirs:
        out.extend(sorted(d.glob(pattern)))
    return out


@log_command
def main():
    install()
    args = parse_args()

    base = Path(args.dir) if args.dir else Path.cwd()
    if not base.exists():
        print(f'[red]Error:[/red] directory not found: {base}')
        return

    # ---- Mode A: aggregated directory (current behavior) ----
    # Pattern is only used to find candidate prefixes (e.g., sample??_ or sample???_)
    # We do NOT try to validate/construct "allowed prefixes" beyond what exists in filenames.
    prefix_glob = f'{args.pattern}_*'
    pref_files = sorted(base.glob(prefix_glob))
    prefixes = sorted({(_sample_prefix(p) or '') for p in pref_files})
    prefixes = [p for p in prefixes if p]

    # Sanity check: do we have any files here at all?
    has_underlay_here = any(base.glob(args.autofl_img))
    has_atlas_here = any(any(base.glob(pat)) for pat in args.atlas)
    if prefixes and not (has_underlay_here or has_atlas_here):
        prefixes = []

    single_sample_mode = False

    # ---- Mode B: single-sample directory fallback ----
    if not prefixes:
        # Case 1: running inside sampleXX
        if base.name.startswith('sample'):
            sample_dir = base
            search_dirs = sorted([d for d in sample_dir.glob('reg_outputs*') if d.is_dir()])

            if args.verbose:
                print(f'[cyan]Single-sample mode:[/cyan] {sample_dir.name} (searching {len(search_dirs)} dir(s))')

        # Case 2: running inside sampleXX/reg_outputs*
        elif base.name.startswith('reg_outputs') and base.parent.name.startswith('sample'):
            sample_dir = base.parent
            # Search just this reg_outputs folder (most specific)
            search_dirs = [base]

            if args.verbose:
                print(f'[cyan]Single-sample mode:[/cyan] {sample_dir.name} (searching 1 dir)')

        else:
            print(f'[red]Error:[/red] No files matched prefix glob: {prefix_glob}')
            print("[red]Error:[/red] Expected aggregated filenames like sample01_*.nii.gz")
            print("[yellow]Hint:[/yellow] Run inside reg_compare/ OR inside sampleXX/ OR inside sampleXX/reg_outputs*/")
            return

        single_sample_mode = True
        prefixes = [sample_dir.name + '_']  # e.g., sample07_

        if not search_dirs:
            print("[red]Error:[/red] No reg_outputs* directories found for this sample.")
            return
        else:
            print(f'  Search dirs: {", ".join(map(str, search_dirs))}')

        if args.verbose:
            print(f'[cyan]Single-sample mode:[/cyan] {sample_dir.name} (searching {len(search_dirs)} dir(s))')

    # Map: prefix -> autofl (list) and atlases (list)
    autofl_by_prefix: dict[str, list[Path]] = {p: [] for p in prefixes}
    atlas_by_prefix: dict[str, list[Path]] = {p: [] for p in prefixes}

    if not single_sample_mode:
        # ---- Mode A collection (unchanged) ----
        for f in _glob_sorted(base, args.autofl_img):
            pref = _sample_prefix(f)
            if pref in autofl_by_prefix:
                autofl_by_prefix[pref].append(f)

        for pat in args.atlas:
            for f in _glob_sorted(base, pat):
                pref = _sample_prefix(f)
                if pref in atlas_by_prefix:
                    atlas_by_prefix[pref].append(f)

    else:
        # ---- Mode B collection (sample dir) ----
        pref = prefixes[0]

        # Underlay: use the "tail" of aggregated glob if needed
        underlay_pat = _strip_aggregated_prefix_glob(args.autofl_img)
        autofl_hits = _glob_sorted_many(search_dirs, underlay_pat)
        if autofl_hits:
            autofl_by_prefix[pref].append(autofl_hits[0])  # keep ONE underlay
        elif args.verbose:
            print(f'[yellow]Warning:[/yellow] No underlay matched: {underlay_pat}')

        # Atlases: preserve pattern order, but strip "*_" if present
        for pat in args.atlas:
            pat2 = _strip_aggregated_prefix_glob(pat)
            atlas_by_prefix[pref].extend(_glob_sorted_many(search_dirs, pat2))

    # Sanity + warnings
    n_samples_with_any = 0
    for pref in prefixes:
        afl = autofl_by_prefix.get(pref, [])
        atl = atlas_by_prefix.get(pref, [])

        if len(afl) > 1:
            print(
                f'[yellow]Warning:[/yellow] {pref} matched multiple autofl files; using the first:\n  '
                + '\n  '.join(map(str, afl))
            )

        if afl or atl:
            n_samples_with_any += 1

    if n_samples_with_any == 0:
        print('[red]Error:[/red] No matching autofl or atlas files found.')
        print(f'  Autofl pattern: {args.autofl_img}')
        print(f'  Atlas patterns: {" ".join(args.atlas)}')

        if single_sample_mode:
            print(f'  Sample dir: {sample_dir}')
            print('  Search dirs:')
            for d in search_dirs:
                print(f'    - {d}')

            underlay_pat = _strip_aggregated_prefix_glob(args.autofl_img)
            print(f'  Underlay tried (single-sample): {underlay_pat}')

            print('  Atlas tried (single-sample):')
            for pat in args.atlas:
                print(f'    - {_strip_aggregated_prefix_glob(pat)}')
        else:
            print(f'  Search directory: {base}')

        return

    # Build one fsleyes command: first sample visible, rest hidden (-d)
    fsleyes_command: list[str] = ['fsleyes']
    first = True

    for pref in prefixes:
        afl_list = autofl_by_prefix.get(pref, [])
        atl_list = atlas_by_prefix.get(pref, [])

        if not afl_list and not atl_list:
            continue

        visible = first
        if afl_list:
            _add_underlay(fsleyes_command, afl_list[0], args, visible=visible)

        for atlas_path in atl_list:
            _add_atlas_overlay(fsleyes_command, atlas_path, args, visible=visible)

        first = False

    print(f'[green]Launching[/green] one FSLeyes instance with {n_samples_with_any} samples '
          f'(first sample visible; others hidden).')
    subprocess.run(fsleyes_command)


if __name__ == '__main__':
    main()
