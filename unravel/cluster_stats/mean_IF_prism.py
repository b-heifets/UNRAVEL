#!/usr/bin/env python3

"""
Use ``cstats_mean_IF_prism`` (``cmip``) from UNRAVEL to prepare mean IF
intensities for pasting into a GraphPad Prism Column table.

The input can be either:
    - Individual CSVs from ``cstats_mean_IF``
    - One row-wise concatenated CSV containing the same columns

Required input columns:
    condition, sample, cluster_ID, mean_intensity

Cluster-region inputs also contain:
    region_ID

By default, the script copies a single resulting Prism table to the system
clipboard and saves Prism CSVs in a ``prism`` subdirectory. If several cluster
or cluster-region tables are generated, each is saved separately and clipboard
copying is skipped because the clipboard can contain only one Prism table.

Usage for one cluster:
----------------------
    cstats_mean_IF_prism \
        -i '*.csv' \
        -c 1 \
        --order saline mdma meth \
        --labels Saline MDMA Meth

Usage with one concatenated CSV:
--------------------------------
    cstats_mean_IF_prism \
        -i _concat/cluster_mean_IF_MEA_bin.csv \
        -c 1 \
        --order saline mdma meth \
        --labels Saline MDMA Meth

Usage for all clusters (inputs are loaded only once):
----------------------------------------------------
    cstats_mean_IF_prism \
        -i '*.csv' \
        --order saline mdma meth \
        --labels Saline MDMA Meth

Usage for one cluster-region pair:
----------------------------------
    cstats_mean_IF_prism \
        -i '*.csv' \
        -c 1 \
        -r 123 \
        --order saline mdma meth \
        --labels Saline MDMA Meth

Notes:
    - ``--order`` controls both the conditions included and their column order.
    - ``--labels`` optionally changes the Prism column headers.
    - Use ``--no-clipboard`` to disable the default clipboard copy.
    - Use ``--no-save`` to copy one table without saving a CSV.
"""

from pathlib import Path

import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import (
    log_command,
    match_files,
    verbose_end_msg,
    verbose_start_msg,
)


def parse_args():
    parser = RichArgumentParser(
        formatter_class=SuppressMetavar,
        add_help=False,
        docstring=__doc__,
    )

    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument(
        "-i",
        "--input",
        help="Path(s) or glob pattern(s) for cstats_mean_IF CSVs. Default: '*.csv'",
        nargs="*",
        default=["*.csv"],
        action=SM,
    )
    opts.add_argument(
        "-c",
        "--clusters",
        help="Cluster IDs to export. Default: all clusters.",
        nargs="*",
        type=int,
        action=SM,
    )
    opts.add_argument(
        "-r",
        "--regions",
        help="Region IDs to export for cluster-region inputs. Default: all regions.",
        nargs="*",
        type=int,
        action=SM,
    )
    opts.add_argument(
        "--order",
        help="Conditions to include, in Prism column order. Default: input order.",
        nargs="*",
        action=SM,
    )
    opts.add_argument(
        "--labels",
        help="Prism column labels corresponding to --order. Default: condition names.",
        nargs="*",
        action=SM,
    )
    opts.add_argument(
        "-o",
        "--output",
        help=(
            "Output CSV path for one table or output directory for multiple tables. "
            "Default: a prism subdirectory beside the inputs."
        ),
        action=SM,
    )
    opts.add_argument(
        "--no-clipboard",
        help="Do not copy the Prism table to the system clipboard.",
        dest="clipboard",
        action="store_false",
        default=True,
    )
    opts.add_argument(
        "--no-save",
        help="Do not save Prism CSV output. Only valid when one table is generated.",
        action="store_true",
        default=False,
    )

    general = parser.add_argument_group("General arguments")
    general.add_argument(
        "-v",
        "--verbose",
        help="Increase verbosity. Default: False.",
        action="store_true",
        default=False,
    )

    return parser.parse_args()


def _has_values(values):
    """Return True when an optional nargs list contains at least one value."""
    return values is not None and len(values) > 0


def _unique_paths(paths):
    """Remove repeated paths while preserving match_files order."""
    unique = []
    seen = set()

    for path in paths:
        path = Path(path)
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(path)

    return unique


def _coerce_integer_column(df, column):
    """Convert a required label column to integers without silently rounding."""
    numeric = pd.to_numeric(df[column], errors="raise")

    if numeric.isna().any():
        raise ValueError(f"Column {column!r} contains missing values.")

    if not (numeric % 1 == 0).all():
        raise ValueError(f"Column {column!r} must contain integer IDs.")

    df[column] = numeric.astype(int)


def load_mean_if_csvs(input_patterns, verbose=False):
    """Load individual or concatenated cstats_mean_IF CSVs exactly once."""
    paths = _unique_paths(match_files(input_patterns))
    paths = [path for path in paths if path.suffix.lower() == ".csv"]

    if not paths:
        raise FileNotFoundError("No input CSV files were found.")

    required = {"condition", "sample", "cluster_ID", "mean_intensity"}
    dfs = []

    for path in paths:
        df = pd.read_csv(path)

        # Support older tabular_concat outputs that wrote the pandas index.
        unnamed_cols = [
            col for col in df.columns
            if str(col).startswith("Unnamed:")
        ]
        if unnamed_cols:
            df = df.drop(columns=unnamed_cols)

        missing = sorted(required.difference(df.columns))
        if missing:
            raise KeyError(
                f"Input CSV {path} is missing required column(s): {missing}"
            )

        df["_source_csv"] = str(path)
        dfs.append(df)

    data = pd.concat(dfs, ignore_index=True)

    for column in ["condition", "sample"]:
        if data[column].isna().any():
            raise ValueError(f"Column {column!r} contains missing values.")

        data[column] = data[column].astype(str).str.strip()

        if data[column].eq("").any():
            raise ValueError(f"Column {column!r} contains empty values.")

    _coerce_integer_column(data, "cluster_ID")

    has_regions = "region_ID" in data.columns
    if has_regions:
        _coerce_integer_column(data, "region_ID")

    data["mean_intensity"] = pd.to_numeric(
        data["mean_intensity"],
        errors="raise",
    )

    if data["mean_intensity"].isna().any():
        raise ValueError("Column 'mean_intensity' contains missing values.")

    measurement_keys = ["condition", "sample", "cluster_ID"]
    if has_regions:
        measurement_keys.append("region_ID")

    duplicated = data.duplicated(
        subset=measurement_keys,
        keep=False,
    )
    if duplicated.any():
        examples = data.loc[
            duplicated,
            measurement_keys + ["_source_csv"],
        ].head(10)

        raise ValueError(
            "Duplicate measurements were found. This commonly occurs when both "
            "individual CSVs and their concatenated CSV are included.\n\n"
            f"{examples.to_string(index=False)}"
        )

    if verbose:
        print(
            f"\nLoaded {len(data):,} measurements "
            f"from {len(paths):,} CSV file(s)."
        )
        print(f"Clusters: {data['cluster_ID'].nunique():,}")

        if has_regions:
            print(f"Regions: {data['region_ID'].nunique():,}")

    return data, paths, has_regions


def resolve_conditions(
    data,
    requested_order=None,
    requested_labels=None,
):
    """Resolve condition selection, ordering, and Prism display labels."""
    available = list(pd.unique(data["condition"]))

    if _has_values(requested_order):
        order = list(requested_order)
    else:
        order = available

    if len(order) != len(set(order)):
        raise ValueError(
            f"--order contains repeated conditions: {order}"
        )

    missing = [
        condition for condition in order
        if condition not in available
    ]
    if missing:
        raise ValueError(
            f"Condition(s) in --order were not found: {missing}. "
            f"Available conditions: {available}"
        )

    if _has_values(requested_labels):
        labels = list(requested_labels)

        if len(labels) != len(order):
            raise ValueError(
                f"--labels has {len(labels)} value(s), but --order resolves to "
                f"{len(order)} condition(s)."
            )
    else:
        labels = order.copy()

    if len(labels) != len(set(labels)):
        raise ValueError(
            f"--labels contains repeated Prism column labels: {labels}"
        )

    return order, labels


def filter_ids(
    data,
    clusters=None,
    regions=None,
    has_regions=False,
):
    """Filter requested clusters and regions with explicit missing-ID checks."""
    selected = data.copy()

    if _has_values(clusters):
        available_clusters = set(
            selected["cluster_ID"].unique()
        )
        missing_clusters = [
            cluster for cluster in clusters
            if cluster not in available_clusters
        ]

        if missing_clusters:
            raise ValueError(
                f"Cluster ID(s) not found: {missing_clusters}"
            )

        selected = selected[
            selected["cluster_ID"].isin(clusters)
        ].copy()

    if _has_values(regions):
        if not has_regions:
            raise ValueError(
                "--regions requires cluster-region CSV input "
                "containing region_ID."
            )

        available_regions = set(
            selected["region_ID"].unique()
        )
        missing_regions = [
            region for region in regions
            if region not in available_regions
        ]

        if missing_regions:
            raise ValueError(
                "Region ID(s) not found after cluster filtering: "
                f"{missing_regions}"
            )

        selected = selected[
            selected["region_ID"].isin(regions)
        ].copy()

    if selected.empty:
        raise ValueError(
            "No measurements remain after filtering."
        )

    return selected


def long_to_prism(
    df,
    column,
    value,
    order=None,
    labels=None,
    sort_by=None,
    row=None,
):
    """
    Convert long-format data into a Prism-ready wide DataFrame.

    Parameters
    ----------
    df : pandas.DataFrame
        Long-format input data.
    column : str
        Column whose values become the Prism data-set columns.
    value : str
        Column containing the numeric measurements.
    order : list of str, optional
        Values from ``column`` to include, in output-column order. If omitted,
        preserve their first-occurrence order.
    labels : list of str, optional
        Replacement output-column names corresponding to ``order``.
    sort_by : str or list of str, optional
        Column(s) used to order observations before reshaping.
    row : str, optional
        Explicit row identifier for paired or repeated-measures data. If
        omitted, independently stack observations within each output column,
        which is appropriate for unpaired Prism Column tables.

    Returns
    -------
    pandas.DataFrame
        A wide table ready to save or copy to Prism. For paired data, the row
        identifier is retained as the first column.
    """
    if df.empty:
        raise ValueError(
            "Cannot prepare a Prism table from an empty DataFrame."
        )

    if sort_by is None:
        sort_columns = []
    elif isinstance(sort_by, str):
        sort_columns = [sort_by]
    else:
        sort_columns = list(sort_by)

    required = [column, value, *sort_columns]
    if row is not None:
        required.append(row)

    missing_columns = [
        name for name in required
        if name not in df.columns
    ]
    if missing_columns:
        raise KeyError(
            "Missing column(s) required for Prism output: "
            f"{missing_columns}"
        )

    prism_long = df.copy()

    if prism_long[column].isna().any():
        raise ValueError(
            f"Column {column!r} contains missing values."
        )

    prism_long[value] = pd.to_numeric(
        prism_long[value],
        errors="raise",
    )
    if prism_long[value].isna().any():
        raise ValueError(
            f"Column {value!r} contains missing values."
        )

    available = list(pd.unique(prism_long[column]))
    output_order = (
        list(order)
        if order is not None
        else available
    )

    if not output_order:
        raise ValueError(
            "No output columns were selected for the Prism table."
        )

    if len(output_order) != len(set(output_order)):
        raise ValueError(
            "Prism column order contains repeated values: "
            f"{output_order}"
        )

    missing_values = [
        name for name in output_order
        if name not in available
    ]
    if missing_values:
        raise ValueError(
            f"Requested Prism column value(s) were not found: "
            f"{missing_values}. Available values: {available}"
        )

    output_labels = (
        list(labels)
        if labels is not None
        else output_order.copy()
    )

    if len(output_labels) != len(output_order):
        raise ValueError(
            f"Received {len(output_labels)} Prism label(s) for "
            f"{len(output_order)} output column(s)."
        )

    if len(output_labels) != len(set(output_labels)):
        raise ValueError(
            f"Prism column labels contain duplicates: {output_labels}"
        )

    prism_long = prism_long[
        prism_long[column].isin(output_order)
    ].copy()

    prism_long[column] = pd.Categorical(
        prism_long[column],
        categories=output_order,
        ordered=True,
    )

    if row is None:
        # For unpaired data, observations in different conditions are not
        # aligned by sample ID. Sort within each condition, then create an
        # independent sequential row number for each Prism column.
        prism_long = prism_long.sort_values(
            [column, *sort_columns]
        )

        prism_long["_prism_row"] = prism_long.groupby(
            column,
            observed=True,
        ).cumcount()

        row_column = "_prism_row"
        row_order = None

    else:
        if prism_long[row].isna().any():
            raise ValueError(
                f"Paired row column {row!r} contains missing values."
            )

        duplicates = prism_long.duplicated(
            subset=[row, column],
            keep=False,
        )
        if duplicates.any():
            examples = prism_long.loc[
                duplicates,
                [row, column, value],
            ].head(10)

            raise ValueError(
                "Paired Prism data must contain no more than one measurement "
                f"per {row!r} and {column!r} combination.\n\n"
                f"{examples.to_string(index=False)}"
            )

        if sort_columns:
            prism_long = prism_long.sort_values(
                [*sort_columns, row]
            )

        row_column = row
        row_order = list(
            pd.unique(prism_long[row])
        )

    prism_df = prism_long.pivot(
        index=row_column,
        columns=column,
        values=value,
    ).reindex(columns=output_order)

    if row_order is not None:
        prism_df = prism_df.reindex(row_order)

    prism_df.columns = output_labels
    prism_df.columns.name = None
    prism_df.index.name = None

    if row is None:
        return prism_df.reset_index(drop=True)

    prism_df = prism_df.reset_index()
    prism_df = prism_df.rename(
        columns={prism_df.columns[0]: row}
    )

    return prism_df


def prepare_cstats_prism_table(
    pair_df,
    order,
    labels,
):
    """Prepare one cstats mean-IF table and its condition summary."""
    prism_df = long_to_prism(
        pair_df,
        column="condition",
        value="mean_intensity",
        order=order,
        labels=labels,
        sort_by="sample",
        row=None,
    )

    summary_df = pair_df[
        pair_df["condition"].isin(order)
    ].copy()

    summary_df["condition"] = pd.Categorical(
        summary_df["condition"],
        categories=order,
        ordered=True,
    )

    summary = (
        summary_df
        .groupby(
            "condition",
            observed=True,
        )["mean_intensity"]
        .agg(
            n="size",
            mean="mean",
        )
        .reindex(order)
        .reset_index()
    )

    summary["condition"] = labels

    return prism_df, summary


def _pair_groups(data, has_regions):
    """Yield identifiers and data for each output table in numeric order."""
    if has_regions:
        grouped = data.groupby(
            ["cluster_ID", "region_ID"],
            sort=True,
        )

        for (cluster_id, region_id), pair_df in grouped:
            yield int(cluster_id), int(region_id), pair_df

    else:
        grouped = data.groupby(
            "cluster_ID",
            sort=True,
        )

        for cluster_id, pair_df in grouped:
            yield int(cluster_id), None, pair_df


def _table_filename(cluster_id, region_id=None):
    """Return a concise filename consistent with cstats summary outputs."""
    if region_id is None:
        return f"cluster_{cluster_id}.csv"

    return f"cluster_{cluster_id}_region_{region_id}.csv"


def _default_output_dir(paths):
    """Place default output beside same-directory inputs, otherwise in cwd."""
    parents = {
        str(path.resolve().parent)
        for path in paths
    }

    if len(parents) == 1:
        return paths[0].parent / "prism"

    return Path("prism")


def save_prism_tables(
    results,
    output,
    input_paths,
):
    """Save one explicitly named CSV or a directory of Prism CSVs."""
    if (
        output is not None
        and Path(output).suffix.lower() == ".csv"
    ):
        if len(results) != 1:
            raise ValueError(
                "A .csv --output path can only be used when one table "
                "is generated. Provide an output directory when "
                "exporting multiple tables."
            )

        output_path = Path(output)
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        results[0]["table"].to_csv(
            output_path,
            index=False,
        )
        results[0]["output_path"] = output_path

        return output_path.parent

    output_dir = (
        Path(output)
        if output is not None
        else _default_output_dir(input_paths)
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for result in results:
        output_path = output_dir / _table_filename(
            result["cluster_ID"],
            result["region_ID"],
        )

        result["table"].to_csv(
            output_path,
            index=False,
        )
        result["output_path"] = output_path

    return output_dir


def _voxel_count(pair_df):
    """Return a stable voxel count when one is available."""
    if "n_voxels" not in pair_df.columns:
        return None

    counts = (
        pd.to_numeric(
            pair_df["n_voxels"],
            errors="coerce",
        )
        .dropna()
        .unique()
    )

    if len(counts) == 1:
        return int(counts[0])

    return None


def print_one_result(result):
    """Print one Prism table and its group sizes and means."""
    title = f"Cluster {result['cluster_ID']}"

    if result["region_ID"] is not None:
        title += f", region {result['region_ID']}"

    print(f"\n[bold]{title}[/bold]")

    if result["n_voxels"] is not None:
        print(f"Voxels: {result['n_voxels']:,}")

    print("\n[bold]Prism table[/bold]")
    print(
        result["table"].to_string(
            index=False,
            float_format=lambda x: f"{x:.6f}",
        )
    )

    print("\n[bold]Column means[/bold]")
    print(
        result["summary"].to_string(
            index=False,
            float_format=lambda x: f"{x:.6f}",
        )
    )


def print_multi_result_summary(
    results,
    verbose=False,
):
    """Print compact n and mean output for a multi-table export."""
    rows = []

    for result in results:
        if verbose:
            print_one_result(result)

        for _, summary_row in result["summary"].iterrows():
            row = {
                "cluster_ID": result["cluster_ID"],
                "condition": summary_row["condition"],
                "n": int(summary_row["n"]),
                "mean": float(summary_row["mean"]),
            }

            if result["region_ID"] is not None:
                row["region_ID"] = result["region_ID"]

            rows.append(row)

    summary_df = pd.DataFrame(rows)

    id_cols = ["cluster_ID"]
    if "region_ID" in summary_df.columns:
        id_cols.append("region_ID")

    summary_df = summary_df[
        id_cols + ["condition", "n", "mean"]
    ]

    print("\n[bold]Column means[/bold]")
    print(
        summary_df.to_string(
            index=False,
            float_format=lambda x: f"{x:.6f}",
        )
    )


def copy_table_to_clipboard(prism_df):
    """Copy headers and values as tab-separated text for Prism."""
    try:
        prism_df.to_clipboard(
            index=False,
            excel=True,
        )
    except Exception as exc:
        raise RuntimeError(
            "Could not copy the Prism table to the system clipboard. "
            "On Linux, confirm that xclip, xsel, or wl-clipboard is "
            "installed and that a graphical session is available. "
            "Use --no-clipboard to skip copying."
        ) from exc


def prepare_all_tables(
    data,
    order,
    labels,
    has_regions,
):
    """Prepare all selected tables after loading the inputs once."""
    results = []

    for cluster_id, region_id, pair_df in _pair_groups(
        data,
        has_regions,
    ):
        prism_df, summary = prepare_cstats_prism_table(
            pair_df,
            order,
            labels,
        )

        results.append({
            "cluster_ID": cluster_id,
            "region_ID": region_id,
            "n_voxels": _voxel_count(pair_df),
            "table": prism_df,
            "summary": summary,
        })

    return results


@log_command
def main():
    install()
    args = parse_args()

    Configuration.verbose = args.verbose
    verbose_start_msg()

    data, input_paths, has_regions = load_mean_if_csvs(
        args.input,
        verbose=args.verbose,
    )

    data = filter_ids(
        data,
        clusters=args.clusters,
        regions=args.regions,
        has_regions=has_regions,
    )

    order, labels = resolve_conditions(
        data,
        requested_order=args.order,
        requested_labels=args.labels,
    )

    # --order also acts as an explicit condition selection.
    data = data[
        data["condition"].isin(order)
    ].copy()

    results = prepare_all_tables(
        data,
        order=order,
        labels=labels,
        has_regions=has_regions,
    )

    if len(results) == 1:
        print_one_result(results[0])
    else:
        print_multi_result_summary(
            results,
            verbose=args.verbose,
        )

    if args.no_save:
        if len(results) != 1:
            raise ValueError(
                "--no-save cannot be used when multiple tables are generated, "
                "because only one table can be copied to the clipboard."
            )
    else:
        output_dir = save_prism_tables(
            results,
            output=args.output,
            input_paths=input_paths,
        )

        if len(results) == 1:
            print(
                f"\nPrism CSV saved to "
                f"{results[0]['output_path']}"
            )
        else:
            print(
                f"\n{len(results):,} Prism CSVs "
                f"saved to {output_dir}/"
            )

    if args.clipboard:
        if len(results) == 1:
            copy_table_to_clipboard(
                results[0]["table"]
            )

            rows, columns = results[0]["table"].shape

            print(
                f"Copied {rows:,} rows x {columns:,} columns "
                "to the clipboard."
            )
        else:
            print(
                "[yellow]Clipboard copy skipped because multiple Prism tables "
                "were generated. Use -c (and -r for cluster-region data) to "
                "select one table for copying.[/yellow]"
            )

    verbose_end_msg()


if __name__ == "__main__":
    main()