#!/usr/bin/env python3

"""
Use ``cstats_summarize_all`` (``csa``) from UNRAVEL to organize all-cluster
cluster-validation data for descriptive Prism plotting.

This is a lightweight, no-statistics counterpart to ``cstats_summary``. It does
not run ``cstats``, does not define valid clusters, and does not filter clusters
by validation-metric differences. Instead, it organizes one validation metric at
a time and exports all clusters for plotting/QC.

Typical use cases:
    - Report cell densities for all clusters.
    - Report cluster-wide mean background-subtracted c-Fos IF for all clusters.
    - Report cluster-wide mean background-subtracted and z-scored c-Fos IF for
      all clusters.

Prereqs:
    - ``cstats_validation`` has already been run for all clusters.
    - Run one metric/output type at a time. For example, run separately for
      ``cell_density``, z-scored ``mean_in_cluster``, and raw
      background-subtracted ``mean_in_cluster``.
    - If sample CSVs have not already been condition-prefixed, provide
      ``--sample_key`` so ``utils_prepend`` can rename them.

What this runs:
    - optionally ``cstats_org_data`` if ``--dirs`` and ``--cluster_val_dirs`` are provided
    - ``cstats_group_data`` unless ``--skip_group_data`` is used
    - ``utils_prepend`` if ``--sample_key`` is provided
    - ``cstats_prism`` unless ``--skip_prism`` is used
    - ``cstats_reshape`` unless ``--skip_reshape`` is used

Inputs:
    - Either existing organized directories containing condition-prefixed CSVs
      from ``cstats_org_data`` / ``utils_prepend``
    - Or raw ``sample??/clusters/<cluster_validation_dir>/<metric>_data.csv``
      outputs from ``cstats_validation`` when ``--dirs`` and ``--cluster_val_dirs``
      are provided.

Outputs:
    - For each organized cluster-validation metric directory:
        - ``_prism/<metric>_summary.csv`` and related QC summaries from ``cstats_prism``
        - ``_reshaped_<value_name>/<value_name>_long.csv``
        - ``_reshaped_<value_name>/<value_name>_wide.csv``
        - ``_reshaped_<value_name>/by_cluster/cluster_<ID>__<value_name>.csv``

Usage after ``cstats_validation``:
----------------------------------
    cstats_summarize_all \
        -g AwS AwP AnS AnP \
        -d /path/to/experiment \
        -cvd 'cluster_mean_IF_AnP_v_AnS_vox_p_tstat1_q0.05*' \
        -me cell_density \
        -sk sample_key.csv \
        -td _all_clusters_cell_density \
        -v

Usage after ``cstats_org_data`` has already been run:
-----------------------------------------------------
    cd _all_clusters_cell_density

    cstats_summarize_all \
        -g AwS AwP AnS AnP \
        -sk ../sample_key.csv \
        -me cell_density \
        -v

Usage for mean IF exports:
--------------------------
    cstats_summarize_all \
        -g AwS AwP AnS AnP \
        -me mean_in_cluster \
        -vn mean_IF_z \
        -sk sample_key.csv \
        -td _all_clusters_mean_IF_z \
        -v
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable

import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


OUTPUT_DIR_NAMES = {
    "3D_brains",
    "valid_clusters_tables_and_legend",
    "_prism",
    "_valid_clusters",
    "_valid_clusters_stats",
    "_valid_clusters_prism",
}

METRIC_CHOICES = [
    "cell_density",
    "label_density",
    "mean_in_cluster",
    "mean_in_seg_in_cluster",
]


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument(
        "-g",
        "--groups",
        help="Group/condition prefixes from CSV filenames, in desired output order for Prism/reshape.",
        nargs="+",
        required=True,
        action=SM,
    )

    org = parser.add_argument_group("Optional organization arguments")
    org.add_argument(
        "-d",
        "--dirs",
        help="Paths to sample?? dirs and/or dirs containing them. If provided with -cvd, cstats_org_data is run first.",
        nargs="*",
        default=None,
        action=SM,
    )
    org.add_argument(
        "-cvd",
        "--cluster_val_dirs",
        help="Glob pattern(s) matching cluster validation output dirs relative to ./sample??/clusters/.",
        nargs="*",
        default=None,
        action=SM,
    )
    org.add_argument(
        "-me",
        "--metric",
        help="Metric output from cstats_validation to aggregate. Default: cell_density",
        default="cell_density",
        choices=METRIC_CHOICES,
        action=SM,
    )
    org.add_argument(
        "-sk",
        "--sample_key",
        help="path/sample_key.csv with dir_name,condition columns for utils_prepend. Safe to provide even if files are already prepended.",
        default=None,
        action=SM,
    )
    org.add_argument(
        "-td",
        "--target_dir",
        help=(
            "Output/input root directory. If -d and -cvd are provided, cstats_org_data writes here. "
            "If -d is omitted, this is treated as an existing organized root to process. "
            "Default with -d/-cvd: _all_clusters_<metric>; otherwise: current directory."
        ),
        default=None,
        action=SM,
    )
    org.add_argument(
        "-vd",
        "--vstats_path",
        help="Optional path/vstats_dir for cstats_org_data to copy p-value, info, and index files.",
        default=None,
        action=SM,
    )
    org.add_argument(
        "-p",
        "--pattern",
        help="Pattern for sample directories passed to cstats_org_data. Default: sample??",
        default="sample??",
        action=SM,
    )

    output = parser.add_argument_group("Optional output arguments")
    output.add_argument(
        "-vn",
        "--value_name",
        help="Metric value name to pass to cstats_reshape. Default: metric name.",
        default=None,
        action=SM,
    )
    output.add_argument(
        "-sn",
        "--support_name",
        help="Support/count name to pass to cstats_reshape. Default inferred from metric.",
        default=None,
        action=SM,
    )

    switches = parser.add_argument_group("Optional switches")
    switches.add_argument("--skip_group_data", help="Skip cstats_group_data.", action="store_true", default=False)
    switches.add_argument("--skip_prism", help="Skip cstats_prism.", action="store_true", default=False)
    switches.add_argument("--skip_reshape", help="Skip cstats_reshape.", action="store_true", default=False)
    switches.add_argument("--dry_run", help="Print commands without running them.", action="store_true", default=False)

    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose", help="Increase verbosity. Default: False", action="store_true", default=False)

    return parser.parse_args()


def run_script(
    script_name: str,
    script_args: Iterable[object],
    cwd: Path | None = None,
    verbose: bool = False,
    dry_run: bool = False,
) -> None:
    """Run a command/script using subprocess while respecting PATH."""
    command = [script_name] + [str(arg) for arg in script_args]
    where = f" in {cwd}" if cwd else ""

    if verbose or dry_run:
        label = "DRY RUN" if dry_run else "Running"
        print(f"\n[cyan]{label}{where}:[/] {' '.join(command)}")

    if dry_run:
        return

    subprocess.run(command, check=True, stdout=None, stderr=None, cwd=str(cwd) if cwd else None)


def infer_support_name(metric: str) -> str:
    """Infer the support/count label used by cstats_reshape outputs."""
    if metric == "cell_density":
        return "cell_count"
    if metric == "label_density":
        return "label_volume"
    if metric == "mean_in_cluster":
        return "cluster_voxel_count"
    if metric == "mean_in_seg_in_cluster":
        return "seg_voxel_count"
    return "support"


def has_matching_group_csv(path: Path, groups: list[str]) -> bool:
    """Return True if path contains at least one CSV starting with one of the group prefixes."""
    if not path.is_dir():
        return False

    for csv_file in path.glob("*.csv"):
        if any(csv_file.name.startswith(f"{group}_") for group in groups):
            return True

    return False


def find_dirs_to_process(root: Path, groups: list[str]) -> list[Path]:
    """Find organized directories containing condition-prefixed metric CSVs."""
    root = root.resolve()

    if has_matching_group_csv(root, groups):
        return [root]

    dirs: list[Path] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        if d.name in OUTPUT_DIR_NAMES:
            continue
        if d.name.startswith("_reshaped"):
            continue
        if has_matching_group_csv(d, groups):
            dirs.append(d)

    return dirs


def warn_if_mixed_metrics(input_dir: Path) -> None:
    """Warn if a directory appears to contain multiple generic-schema metrics."""
    metric_names: set[str] = set()

    for csv_path in sorted(input_dir.glob("*.csv")):
        try:
            df = pd.read_csv(csv_path, nrows=10)
        except Exception:
            continue

        if "metric" not in df.columns:
            continue

        metric_names.update(df["metric"].dropna().astype(str).unique())

    if len(metric_names) > 1:
        print(
            f"[yellow]Warning:[/] {input_dir} appears to contain multiple metrics: "
            f"{sorted(metric_names)}. This script is intended for one metric/output type per folder."
        )


def resolve_sample_key(sample_key: str | None, original_cwd: Path) -> Path | None:
    """Resolve sample_key relative to the directory where the user launched the command."""
    if sample_key is None:
        return None

    sample_key_path = Path(sample_key)
    if not sample_key_path.is_absolute():
        sample_key_path = original_cwd / sample_key_path

    return sample_key_path.resolve()


def get_root(args, original_cwd: Path) -> Path:
    """Choose the root directory used for organization and downstream processing."""
    if args.target_dir:
        return Path(args.target_dir).resolve()

    if args.dirs and args.cluster_val_dirs:
        return (original_cwd / f"_all_clusters_{args.metric}").resolve()

    return original_cwd.resolve()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    original_cwd = Path.cwd()
    root = get_root(args, original_cwd)
    value_name = args.value_name or args.metric
    support_name = args.support_name or infer_support_name(args.metric)
    reshape_outdir = f"_reshaped_{value_name}"

    wants_org_data = bool(args.dirs or args.cluster_val_dirs)
    if wants_org_data and not (args.dirs and args.cluster_val_dirs):
        print("\n[red1]To run cstats_org_data, provide both -d/--dirs and -cvd/--cluster_val_dirs.[/]\n")
        verbose_end_msg()
        return

    if wants_org_data:
        if not args.dry_run:
            root.mkdir(parents=True, exist_ok=True)

        org_data_args: list[object] = [
            "-d",
            *args.dirs,
            "-p",
            args.pattern,
            "-cvd",
            *args.cluster_val_dirs,
            "-me",
            args.metric,
            "-td",
            root,
        ]
        if args.vstats_path:
            org_data_args.extend(["-vd", args.vstats_path])
        if args.verbose:
            org_data_args.append("-v")

        run_script("cstats_org_data", org_data_args, cwd=original_cwd, verbose=args.verbose, dry_run=args.dry_run)

    if not root.exists() and not args.dry_run:
        print(f"\n[red1]Input/output root does not exist:[/] {root}\n")
        verbose_end_msg()
        return

    if not args.skip_group_data:
        group_args = ["-v"] if args.verbose else []
        run_script("cstats_group_data", group_args, cwd=root, verbose=args.verbose, dry_run=args.dry_run)

    sample_key = resolve_sample_key(args.sample_key, original_cwd)
    if sample_key:
        prepend_args: list[object] = ["-sk", sample_key, "-f", "-r"]
        if args.verbose:
            prepend_args.append("-v")
        run_script("utils_prepend", prepend_args, cwd=root, verbose=args.verbose, dry_run=args.dry_run)

    if args.dry_run and not root.exists():
        print("\n[yellow]Dry run stopped before directory discovery because the output root does not exist yet.[/]")
        verbose_end_msg()
        return

    dirs_to_process = find_dirs_to_process(root=root, groups=args.groups)

    if not dirs_to_process:
        print(
            "\n[red1]No organized directories with condition-prefixed CSVs were found.[/]\n"
            f"Root searched: {root}\n"
            f"Expected CSVs starting with one of: {', '.join(args.groups)}_\n"
        )
        verbose_end_msg()
        return

    print("\n[bold]Directories to process:[/]")
    for d in dirs_to_process:
        print(f"    {d}")

    for input_dir in dirs_to_process:
        print(f"\n[bold bright_magenta]Processing all clusters:[/] {input_dir.name}")
        warn_if_mixed_metrics(input_dir)

        if not args.skip_prism:
            prism_args = ["-p", "."]
            if args.verbose:
                prism_args.append("-v")
            run_script("cstats_prism", prism_args, cwd=input_dir, verbose=args.verbose, dry_run=args.dry_run)

        if not args.skip_reshape:
            reshape_args: list[object] = [
                "-g",
                *args.groups,
                "-o",
                reshape_outdir,
                "-vn",
                value_name,
                "-sn",
                support_name,
            ]
            if args.verbose:
                reshape_args.append("-v")
            run_script("cstats_reshape", reshape_args, cwd=input_dir, verbose=args.verbose, dry_run=args.dry_run)

    print("\n[green bold]Done.[/] All-cluster descriptive outputs were generated.")
    print(f"Root: {root}")
    if not args.skip_prism:
        print("Prism outputs: <cluster_validation_dir>/_prism/")
    if not args.skip_reshape:
        print(f"Reshaped outputs: <cluster_validation_dir>/{reshape_outdir}/")

    verbose_end_msg()


if __name__ == "__main__":
    main()
