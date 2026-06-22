#!/usr/bin/env python3

"""
Aggregate and analyze cluster validation data from per-sample cstats_validation outputs.

This wrapper can:
1) optionally collect per-sample hemisphere CSVs into cluster-level directories via cstats_org_data
2) group / label the aggregated data
3) run a downstream stats script (default: local cstats.py if present)
4) consume the resulting valid-cluster outputs to generate indexed maps, 3D brains, tables, Prism files, and legend files

Notes
-----
- This script is only the orchestrator. The actual hypothesis testing logic lives in the downstream stats script.
- By default, this script tries to run a local "cstats.py" sitting beside it. You can override that with --stats-script.
- Any unknown arguments are forwarded to the downstream stats script unchanged. This makes the wrapper compatible with experimental stats scripts without needing to keep editing summary.py.
"""

from __future__ import annotations

import shutil
from fnmatch import fnmatch
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
from rich import print
from rich.traceback import install

from unravel.cluster_stats.org_data import cp
from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, verbose_end_msg, verbose_start_msg, load_config
from unravel.utilities.aggregate_files_recursively import find_and_copy_files


EXCLUDED_TOPLEVEL_DIRS = {
    '3D_brains',
    'valid_clusters_tables_and_legend',
    'stats',
}

TEST_TYPES = ['dunnett', 'anova', 'tukey', 'holm', 't-test']


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument(
        '-c', '--config',
        help='Path to the config.ini file. Default: summary-local cluster_summary.ini',
        default=Path(__file__).parent / 'cluster_summary.ini',
        action=SM,
    )

    orchestration = parser.add_argument_group('Orchestration')
    orchestration.add_argument(
        '--stats-script',
        help='Path or command name for the downstream stats script. Default: local cstats.py if present, else cstats on PATH.',
        default=None,
        action=SM,
    )
    orchestration.add_argument(
        '--skip-stats',
        help='Do not run the downstream stats script; consume existing _valid_clusters_stats outputs only.',
        action='store_true',
        default=False,
    )
    orchestration.add_argument(
        '--target-dirs',
        help='Only run downstream stats/post-processing for subdirectories whose names match these exact names or glob patterns.',
        nargs='*',
        default=None,
        action=SM,
    )

    cstats_org_data = parser.add_argument_group('Optional args for cstats_org_data')
    cstats_org_data.add_argument(
        '-d', '--dirs',
        help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir',
        nargs='*',
        default=None,
        action=SM,
    )
    cstats_org_data.add_argument(
        '-cvd', '--cluster_val_dirs',
        help='Glob pattern matching cluster validation output dirs to copy data from (relative to ./sample??/clusters/; for cstats_org_data)',
        action=SM,
    )
    cstats_org_data.add_argument(
        '-vd', '--vstats_path',
        help='path/vstats_dir (dir vstats was run from) to copy p val, info, and index files (for cstats_org_data)',
        action=SM,
    )

    cstats_org_data.add_argument(
        '-me', '--metric',
        help='Metric name expected by cstats_org_data. Default: infer from density_type in config (cell -> cell_density, label -> label_density).',
        default=None,
        action=SM,
    )

    utils_prepend = parser.add_argument_group('Optional args for utils_prepend')
    utils_prepend.add_argument(
        '-sk', '--sample_key',
        help='path/sample_key.csv w/ directory names and conditions (for utils_prepend)',
        action=SM,
    )

    cstats_opts_comparisons = parser.add_argument_group('Optional args for comparison-style stats')
    cstats_opts_comparisons.add_argument(
        '-comp', '--comparisons',
        help=(
            "List of pairwise comparisons (e.g. saline<MDMA saline,R-MDMA), with the control group first. "
            "Use '<' or '>' for directional tests, or ',' for two-sided. Use 'all' for Tukey tests."
        ),
        nargs='*',
        default=None,
        action=SM,
    )

    cstats_opts_anova = parser.add_argument_group('Optional args for ANOVA-style stats')
    cstats_opts_anova.add_argument(
        '-gm', '--group_map',
        help='CSV file mapping condition names to factor levels (required for ANOVA in the downstream stats script).',
        action=SM,
    )
    cstats_opts_anova.add_argument(
        '-e', '--effect',
        help='Specific effect or interaction to validate from ANOVA (e.g., Drug or Drug:Housing)',
        default=None,
        action=SM,
    )
    cstats_opts_anova.add_argument(
        '-f', '--formula',
        help='ANOVA model formula (e.g., Drug or Drug*Housing). Required if using group_map.',
        required=False,
        action=SM,
    )

    cstats_opts_validation = parser.add_argument_group('Validation criteria and output')
    cstats_opts_validation.add_argument(
        '-vc', '--val_crit',
        help="Validation criteria: 'all' (default), 'any', or a number of comparisons that must be significant for a cluster to be valid.",
        default='all',
        action=SM,
    )

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    args, unknown = parser.parse_known_args()
    return args, unknown


def run_command(cmd: list[str], verbose: bool = False):
    if verbose:
        print(f"[dim]Running:[/] {' '.join(map(str, cmd))}")
    subprocess.run([str(x) for x in cmd], check=True, stdout=None, stderr=None)


def resolve_stats_script(user_value: str | None) -> list[str]:
    """Return a subprocess command prefix for the downstream stats script."""
    if user_value:
        candidate = Path(user_value)
        if candidate.exists():
            if candidate.suffix == '.py':
                return [sys.executable, str(candidate)]
            return [str(candidate)]
        return [user_value]

    local_cstats = Path(__file__).parent / 'cstats.py'
    if local_cstats.exists():
        return [sys.executable, str(local_cstats)]

    return ['cstats']



def matches_any_pattern(name: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return True
    return any(fnmatch(name, pattern) for pattern in patterns)


def find_stats_result(stats_output: Path):
    for tag in TEST_TYPES:
        result = next(stats_output.glob(f'{tag}_results.csv'), None)
        if result is not None:
            return tag, result
    return None, None


def list_validation_tags(stats_output: Path):
    """Return validation tags discovered in _valid_clusters_stats, ordered with the primary test first."""
    primary_tag, _ = find_stats_result(stats_output)
    tags = []
    for txt in sorted(stats_output.glob('valid_cluster_IDs_*.txt')):
        name = txt.name[len('valid_cluster_IDs_'):-4]
        if name:
            tags.append(name)
    tags = list(dict.fromkeys(tags))
    if primary_tag and primary_tag in tags:
        tags = [primary_tag] + [tag for tag in tags if tag != primary_tag]
    return tags


def find_rev_cluster_index(subdir: Path):
    candidates = [
        subdir / f'{subdir.name}_rev_cluster_index.nii.gz',
        subdir / f'{subdir.name}_rev_cluster_index_RH.nii.gz',
        subdir / f'{subdir.name}_rev_cluster_index_LH.nii.gz',
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return next(subdir.glob('*rev_cluster_index*'), None)


def infer_metric(metric_arg, density_type):
    if metric_arg:
        return metric_arg
    dt = str(density_type).strip().lower()
    mapping = {
        'cell': 'cell_density',
        'cells': 'cell_density',
        'label': 'label_density',
        'labels': 'label_density',
    }
    return mapping.get(dt, f'{dt}_density')



@log_command
def main():
    install()
    args, passthrough_args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    subdirs = [d for d in Path.cwd().iterdir() if d.is_dir()]
    if len(subdirs) == 0 and not args.dirs:
        print("\n    [red1]No subdirectories found in the current directory. Provide -d/--dirs so that data from sample??/clusters/ can be aggregated and processed.[/]\n")
        return

    cfg = load_config(args.config)

    if args.dirs and args.cluster_val_dirs and args.vstats_path:
        metric = infer_metric(args.metric, cfg.org_data.density_type)
        org_data_args = [
            'cstats_org_data',
            '-d', *args.dirs,
            '-p', cfg.org_data.pattern,
            '-cvd', args.cluster_val_dirs,
            '-vd', args.vstats_path,
            '-me', metric,
            '-pvt', cfg.org_data.p_val_txt,
        ]
        # Some local/draft versions of cstats_org_data reject a value after -dt.
        # For cell data, omit -dt and rely on the tool's default behavior.
        if str(getattr(cfg.org_data, 'density_type', 'cell')).strip().lower() != 'cell':
            org_data_args += ['-dt', cfg.org_data.density_type]
        if args.verbose:
            org_data_args.append('-v')
        run_command(org_data_args, verbose=args.verbose)

    group_data_cmd = ['cstats_group_data']
    if args.verbose:
        group_data_cmd.append('-v')
    run_command(group_data_cmd, verbose=args.verbose)

    if args.sample_key:
        prepend_cmd = ['utils_prepend', '-sk', args.sample_key, '-f', '-r']
        if args.verbose:
            prepend_cmd.append('-v')
        run_command(prepend_cmd, verbose=args.verbose)

    if not args.skip_stats:
        stats_cmd = resolve_stats_script(args.stats_script)
        stats_args = ['-pvt', cfg.org_data.p_val_txt, '--val_crit', args.val_crit]

        using_anova = bool(args.group_map and args.formula)
        if using_anova:
            stats_args += ['-gm', args.group_map, '-f', args.formula]
            if args.effect:
                stats_args += ['-e', args.effect]
        elif args.comparisons:
            stats_args += ['-comp', *args.comparisons]

        if args.target_dirs:
            stats_args += ['-td', *args.target_dirs]
        elif args.cluster_val_dirs:
            stats_args += ['-td', args.cluster_val_dirs]

        if args.verbose:
            stats_args.append('-v')

        stats_cmd = stats_cmd + stats_args + passthrough_args
        run_command(stats_cmd, verbose=args.verbose)
    elif passthrough_args and args.verbose:
        print('[yellow]Ignoring extra stats arguments because --skip-stats was supplied.[/]')

    postprocess_patterns = args.target_dirs or ([args.cluster_val_dirs] if args.cluster_val_dirs else None)
    candidate_subdirs = [
        d for d in Path.cwd().iterdir()
        if d.is_dir() and d.name not in EXCLUDED_TOPLEVEL_DIRS and matches_any_pattern(d.name, postprocess_patterns)
    ]

    for subdir in candidate_subdirs:
        stats_output = subdir / '_valid_clusters_stats'
        if not stats_output.exists():
            continue

        primary_tag, results_file = find_stats_result(stats_output)
        if results_file is None and not any(stats_output.glob('valid_cluster_IDs_*.txt')):
            print(f"[yellow]No stats outputs found in {stats_output}, skipping...[/]")
            continue

        if args.verbose and primary_tag is not None:
            print(f"[bold cyan]Detected primary test type:[/] {primary_tag} [dim]in {subdir.name}[/]")

        validation_tags = list_validation_tags(stats_output)
        if not validation_tags:
            print(f"[yellow]No valid_cluster_IDs_*.txt files found in {stats_output}, skipping...[/]")
            continue

        rev_cluster_index_path = find_rev_cluster_index(subdir)
        if rev_cluster_index_path is None:
            print(f"    [yellow]No valid cluster index file found in {subdir}. Skipping...[/]")
            continue

        for tag in validation_tags:
            valid_clusters_ids_txt = stats_output / f'valid_cluster_IDs_{tag}.txt'
            if not valid_clusters_ids_txt.exists():
                continue

            valid_cluster_ids = valid_clusters_ids_txt.read_text().split()
            if len(valid_cluster_ids) == 0:
                if args.verbose:
                    print(f"    [yellow]No clusters were valid for {subdir.name} [{tag}]. Skipping...[/]")
                continue

            valid_clusters_dir_name = cfg.index.valid_clusters_dir if tag == primary_tag else f'{cfg.index.valid_clusters_dir}_{tag}'
            valid_clusters_index_dir = subdir / valid_clusters_dir_name

            index_cmd = [
                'cstats_index',
                '-i', rev_cluster_index_path,
                '-ids', *valid_cluster_ids,
                '-vcd', valid_clusters_index_dir,
                '-a', cfg.index.atlas,
                '-scsv', cfg.index.sunburst_csv_path,
                '-in', cfg.index.info_csv_path,
            ]
            if cfg.index.output_rgb_lut:
                index_cmd.append('-rgb')
            if args.verbose:
                index_cmd.append('-v')
            run_command(index_cmd, verbose=args.verbose)

            valid_cluster_index_path = valid_clusters_index_dir / str(rev_cluster_index_path.name).replace(
                '.nii.gz', f'_{valid_clusters_dir_name}.nii.gz'
            )
            brain_cmd = [
                'cstats_brain_model',
                '-i', valid_cluster_index_path,
                '-ax', cfg.brain.axis,
                '-s', cfg.brain.shift,
                '-sa', cfg.brain.split_atlas,
                '-csv', cfg.brain.csv_path,
            ]
            if cfg.brain.mirror:
                brain_cmd.append('-m')
            if args.verbose:
                brain_cmd.append('-v')
            run_command(brain_cmd, verbose=args.verbose)

            if cfg.brain.mirror:
                find_and_copy_files(f'*{valid_clusters_dir_name}_ABA_WB.nii.gz', subdir, Path.cwd() / '3D_brains')
            else:
                find_and_copy_files(f'*{valid_clusters_dir_name}_ABA.nii.gz', subdir, Path.cwd() / '3D_brains')
            find_and_copy_files(f'*{valid_clusters_dir_name}_rgba.txt', subdir, Path.cwd() / '3D_brains')

            table_cmd = [
                'cstats_table',
                '-vcd', valid_clusters_index_dir,
                '-t', cfg.table.top_regions,
                '-pv', cfg.table.percent_vol,
                '-csv', cfg.index.info_csv_path,
                '-rgb', cfg.table.rgbs,
            ]
            if args.verbose:
                table_cmd.append('-v')
            run_command(table_cmd, verbose=args.verbose)

            # cstats_table writes a generic file name like:
            #   <dataset>_valid_clusters_table.xlsx
            # inside the specific valid-clusters output directory.
            # For per-tag outputs we copy that file to the central legend folder
            # and rename it to include the tag, e.g.:
            #   <dataset>_valid_clusters_dunnett_MBDB_any_table.xlsx
            tables_dest = Path.cwd() / 'valid_clusters_tables_and_legend'
            tables_dest.mkdir(parents=True, exist_ok=True)
            table_files = sorted(valid_clusters_index_dir.glob('*valid_clusters_table*.xlsx'))
            if not table_files:
                print(f"\n    [yellow]No table .xlsx found in {valid_clusters_index_dir}. Skipping table aggregation...[/]\n")
            else:
                for table_file in table_files:
                    if tag == primary_tag:
                        dest_name = table_file.name
                    else:
                        dest_name = table_file.name.replace('_valid_clusters_table', f'_{valid_clusters_dir_name}_table')
                    shutil.copy2(table_file, tables_dest / dest_name)

            if Path('valid_clusters_tables_and_legend').exists():
                valid_cluster_ids_sorted_txt = valid_clusters_index_dir / 'valid_cluster_IDs_sorted_by_anatomy.txt'
                if valid_cluster_ids_sorted_txt.exists():
                    valid_cluster_ids_sorted = valid_cluster_ids_sorted_txt.read_text().split()
                else:
                    valid_cluster_ids_sorted = valid_cluster_ids
                if len(valid_cluster_ids_sorted) > 0:
                    prism_cmd = ['cstats_prism', '-ids', *valid_cluster_ids_sorted, '-p', subdir]
                    if args.verbose:
                        prism_cmd.append('-v')
                    run_command(prism_cmd, verbose=args.verbose)
                else:
                    print(f"\n    [yellow]No valid cluster IDs found for {subdir} [{tag}]. Skipping cstats_prism...[/]\n")

    dest_atlas = Path.cwd() / '3D_brains' / Path(cfg.index.atlas).name
    if not dest_atlas.exists() and dest_atlas.parent.exists():
        cp(cfg.index.atlas, dest_atlas)
        atlas_nii = nib.load(dest_atlas)
        atlas_img = np.asanyarray(atlas_nii.dataobj, dtype=atlas_nii.header.get_data_dtype()).squeeze()
        atlas_img[atlas_img > 0] = 1
        atlas_img = atlas_img.astype(np.uint8, copy=False)
        atlas_nii_bin = nib.Nifti1Image(atlas_img, atlas_nii.affine, atlas_nii.header)
        atlas_nii_bin.header.set_data_dtype(np.uint8)
        nib.save(atlas_nii_bin, str(dest_atlas).replace('.nii.gz', '_bin.nii.gz'))

        if Path('valid_clusters_tables_and_legend').exists():
            legend_cmd = ['cstats_legend', '-p', 'valid_clusters_tables_and_legend', '-csv', cfg.index.info_csv_path]
            run_command(legend_cmd, verbose=args.verbose)

    verbose_end_msg()


if __name__ == '__main__':
    main()
