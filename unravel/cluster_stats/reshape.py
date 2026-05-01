#!/usr/bin/env python3

"""
Use ``cstats_reshape`` (``reshape``) from UNRAVEL to export raw cluster validation data
as wide all-cluster CSVs and per-cluster replicate-layout CSVs.

Prereqs:
    - ``cstats_validation``, ``cstats_org_data``, ``cstats_group_data``, ``utils_prepend``

Input files:
    - `*_data.csv` from ``cstats_validation`` after condition prefixes were prepended
      e.g., saline_cell_density_data.csv, drug_cell_density_data.csv

Outputs:
    - _reshaped/raw_data_long.csv
    - _reshaped/raw_data_wide.csv
    - _reshaped/by_cluster/cluster_<cluster_ID>__<value_name>.csv

Usage:
------
    cstats_reshape -g saline drug1 drug2 -i '*cell_density_data.csv'
    cstats_reshape -g saline MBDB MDAI RMDMA SMDMA --combine entactogens=MBDB+MDAI+RMDMA+SMDMA
"""

import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.cluster_stats.cstats import detect_metric_schema, get_matching_input_csvs, cluster_validation_data_df
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)
    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-g', '--groups', help='Group/condition prefixes from CSV filenames, in desired output order.', nargs='*', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-i', '--input', help="CSV paths or glob patterns. Default: '*_data.csv'", nargs='*', default=['*.csv'], action=SM)
    opts.add_argument('-o', '--outdir', help="Output directory. Default: _resphaped", default="_reshaped", action=SM)
    opts.add_argument("--value_name", help="Name to use for the metric value column. Default: cell_density", default="cell_density", action=SM)
    opts.add_argument("--support_name", help="Name to use for the support/count column. Default: cell_count", default="cell_count", action=SM)
    opts.add_argument("--combine", help="Optional combined per-cluster columns, e.g. drug1+drug2 or ent=drug1+drug2", nargs="*", default=[], action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    current_dir = Path.cwd()

    csv_files = get_matching_input_csvs(current_dir, args.groups)

    if not csv_files:
        print(f"    [red1]No matching input CSVs found for groups: {' '.join(args.groups)}")
        return

    first_df = pd.read_csv(csv_files[0])

    try:
        schema = detect_metric_schema(first_df)
    except ValueError as e:
        print(f"Error: {e}")
        return

    # Check if any files contain hemisphere indicators
    has_hemisphere = any('_LH.csv' in str(file.name) or '_RH.csv' in str(file.name) for file in csv_files)

    # Aggregate the data from all .csv files and pool the data if hemispheres are present
    data_df = cluster_validation_data_df(
        metric_name=schema['metric_name'],
        value_col=schema['value_col'],
        support_col=schema['support_col'],
        support_type=schema['support_type'],
        aggregation_method=schema['aggregation_method'],
        has_hemisphere=has_hemisphere,
        csv_files=csv_files,
        groups=args.groups,
    )
    if data_df.empty:
        print("    [red1]No data rows found after aggregation.")
        return

    data_df = data_df.rename(columns={
        "value": args.value_name,
        "support": args.support_name,
    })

    outdir = Path(args.outdir)
    cluster_outdir = outdir / "by_cluster"
    cluster_outdir.mkdir(parents=True, exist_ok=True)

    outdir = Path(args.outdir)
    cluster_outdir = outdir / "by_cluster"
    cluster_outdir.mkdir(parents=True, exist_ok=True)

    long_path = outdir / f"{args.value_name}_long.csv"
    data_df.to_csv(long_path, index=False)

    # All-clusters wide format:
    # cluster_ID, saline_sample01, saline_sample02, drug_sample01, ...
    wide_df = data_df.copy()
    wide_df["_wide_col"] = wide_df["condition"].astype(str) + "_" + wide_df["sample"].astype(str)

    wide_df = (
        wide_df.pivot_table(
            index="cluster_ID",
            columns="_wide_col",
            values=args.value_name,
            aggfunc="first",
        )
        .reset_index()
        .sort_values("cluster_ID")
    )
    wide_df.columns.name = None

    ordered_cols = ["cluster_ID"]
    for group in args.groups:
        samples = sorted(data_df.loc[data_df["condition"] == group, "sample"].astype(str).unique())
        ordered_cols.extend([f"{group}_{sample}" for sample in samples])

    ordered_cols = [c for c in ordered_cols if c in wide_df.columns]
    remaining_cols = [c for c in wide_df.columns if c not in ordered_cols]
    wide_df = wide_df[ordered_cols + remaining_cols]

    wide_path = outdir / f"{args.value_name}_wide.csv"
    wide_df.to_csv(wide_path, index=False)

    # Optional combined columns for per-cluster CSVs.
    combined_groups = []
    for spec in args.combine:
        if "=" in spec:
            col_name, group_str = spec.split("=", 1)
        else:
            col_name, group_str = spec, spec
        combined_groups.append((col_name, group_str.split("+")))

    # One CSV per cluster with stacked replicates for each group and combined groups if specified, e.g.:
    # saline, drug1, drug2, drug1+drug2
    for cluster_id, cluster_df in data_df.groupby("cluster_ID", sort=True):
        max_len = max(
            [len(cluster_df.loc[cluster_df["condition"] == group]) for group in args.groups] +
            [len(cluster_df.loc[cluster_df["condition"].isin(combo_groups)]) for _, combo_groups in combined_groups] +
            [1]
        )

        cluster_out_df = pd.DataFrame(index=range(max_len))

        for group in args.groups:
            values = (
                cluster_df.loc[cluster_df["condition"] == group]
                .sort_values("sample")[args.value_name]
                .reset_index(drop=True)
            )
            cluster_out_df[group] = values

        for col_name, combo_groups in combined_groups:
            values = (
                cluster_df.loc[cluster_df["condition"].isin(combo_groups)]
                .sort_values(["condition", "sample"])[args.value_name]
                .reset_index(drop=True)
            )
            cluster_out_df[col_name] = values

        safe_cluster_id = "".join(
            ch if ch.isalnum() or ch in "._-" else "_"
            for ch in str(cluster_id)
        )
        cluster_path = cluster_outdir / f"cluster_{safe_cluster_id}__{args.value_name}.csv"
        cluster_out_df.to_csv(cluster_path, index=False)

    if args.verbose:
        print("\n[blue]Aggregated long data:[/]")
        print(data_df)
        print("\n[blue]Wide data:[/]")
        print(wide_df)

    print(f"\n    Long CSV: {long_path}")
    print(f"    Wide CSV: {wide_path}")
    print(f"    Per-cluster CSVs: {cluster_outdir}")

    verbose_end_msg()


if __name__ == '__main__':
    main()