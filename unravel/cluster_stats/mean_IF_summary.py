#!/usr/bin/env python3

"""
Use ``cstats_mean_IF_summary`` (``cmis``) from UNRAVEL to plot and summarize mean IF intensities.

This script handles two input schemas:

Cluster-only CSVs from ``cstats_mean_IF``:
    sample, cluster_ID, n_voxels, mean_intensity

Cluster-region CSVs from ``cstats_mean_IF -a atlas.nii.gz``:
    sample, cluster_ID, region_ID, n_voxels, mean_intensity

Outputs:
    - cluster_mean_IF_summary/cluster_<cluster_id>.pdf
    - cluster_region_mean_IF_summary/cluster_<cluster_id>_region_<region_id>.pdf
    - Summary CSV with t-test, Tukey, or Dunnett results

Note:
    - The first word of each CSV filename is used as the group name.
      Example: Control_sample01_cFos_z.csv -> group = Control
    - If significant differences are found, a prefix '_' is added to the plot filename.

Usage for cluster-only t-tests:
-------------------------------
    cstats_mean_IF_summary --order Control Treatment --labels Control Treatment -t ttest [-v]

Usage for cluster-region Dunnett tests:
---------------------------------------
    cstats_mean_IF_summary \\
        --order Saline MBDB MDAI RMDMA SMDMA \\
        --labels Saline MBDB MDAI R-MDMA S-MDMA \\
        -t dunnett \\
        -alt greater \\
        [-c 1 2 3] \\
        [-r 101 102 103] \\
        [-v]

Usage with optional region LUT:
-------------------------------
    cstats_mean_IF_summary \\
        --order Saline MBDB MDAI RMDMA SMDMA \\
        --labels Saline MBDB MDAI R-MDMA S-MDMA \\
        -t dunnett \\
        -l CCFv3-2020__regionID_side_IDpath_region_abbr.csv \\
        -v
"""

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import seaborn as sns
import textwrap
from pathlib import Path
from rich import print
from rich.traceback import install
from scipy.stats import ttest_ind, dunnett
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


# Set Arial as the font
mpl.rcParams['font.family'] = 'Arial'


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument(
        '--order',
        nargs='*',
        help='Group order for plotting and stats. Must match first word of CSV filenames.',
        required=True,
        action=SM,
    )
    reqs.add_argument(
        '--labels',
        nargs='*',
        help='Group labels in the same order as --order.',
        required=True,
        action=SM,
    )

    opts = parser.add_argument_group('Optional args')
    opts.add_argument(
        '-c', '--cluster_ids',
        help='List of cluster IDs to process. Default: all clusters.',
        nargs='*',
        type=int,
        action=SM,
    )
    opts.add_argument(
        '-r', '--region_ids',
        help='List of region IDs to process when input CSVs contain region_ID. Default: all regions.',
        nargs='*',
        type=int,
        action=SM,
    )
    opts.add_argument(
        '-t', '--test',
        help='Choose between "tukey", "dunnett", and "ttest". Default: ttest for 2 groups, tukey for >2 groups.',
        default=None,
        choices=['tukey', 'dunnett', 'ttest'],
        action=SM,
    )
    opts.add_argument(
        '-alt', '--alternate',
        help="Alternative for Dunnett's test: {'two-sided', 'less', 'greater'}. Default: two-sided.",
        default='two-sided',
        action=SM,
    )
    opts.add_argument(
        '-y', '--ylabel',
        help='Y-axis label for plots. Default: Mean IF Intensity.',
        default='Mean IF Intensity',
        action=SM,
    )
    opts.add_argument(
        '-l', '--lut',
        help='Optional region LUT CSV path or CSV name in unravel/core/csvs/. Expected columns: Region_ID, Region, Abbr.',
        default=None,
        action=SM,
    )
    opts.add_argument(
        '-sa', '--symbol_alpha',
        help='Opacity of individual data-point symbols. Default: 1.0',
        type=float,
        default=1.0,
        action=SM,
    )
    opts.add_argument(
        '-s', '--skip_plots',
        help='Only write summary CSVs; do not generate PDF plots.',
        action='store_true',
        default=False,
    )

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False.', action='store_true', default=False)

    return parser.parse_args()


def significance_label(p_value):
    """Return significance stars from a p-value."""
    if p_value < 0.0001:
        return '****'
    if p_value < 0.001:
        return '***'
    if p_value < 0.01:
        return '**'
    if p_value < 0.05:
        return '*'
    return 'n.s.'


def safe_filename(text):
    """Make text safe for file names."""
    return str(text).replace("/", "-").replace(" ", "_")


def resolve_lut_path(lut):
    """Resolve LUT path from explicit path or unravel/core/csvs/."""
    if lut is None:
        return None

    lut_path = Path(lut)
    if lut_path.exists():
        return lut_path

    core_lut = Path(__file__).parent.parent / 'core' / 'csvs' / lut
    if core_lut.exists():
        return core_lut

    raise FileNotFoundError(f"Could not find LUT CSV: {lut}")


def load_region_lut(lut):
    """Load optional region LUT."""
    lut_path = resolve_lut_path(lut)

    if lut_path is None:
        return None

    df = pd.read_csv(lut_path)

    if "Region_ID" not in df.columns:
        raise KeyError("LUT must contain a Region_ID column.")

    if "Region" not in df.columns and "Name" in df.columns:
        df = df.rename(columns={"Name": "Region"})

    keep_cols = [col for col in ["Region_ID", "Region", "Abbr"] if col in df.columns]
    df = df[keep_cols].drop_duplicates(subset=["Region_ID"])

    return df


def get_region_info(region_id, region_lut=None):
    """Return region name and abbreviation if available."""
    if region_lut is None:
        return None, None

    match = region_lut[region_lut["Region_ID"] == region_id]

    if match.empty:
        return None, None

    row = match.iloc[0]
    region = row["Region"] if "Region" in row.index else None
    abbr = row["Abbr"] if "Abbr" in row.index else None

    return region, abbr


def load_all_data():
    """Load all CSVs once and add group names from filenames."""
    dfs = []

    for filename in os.listdir():
        if filename.endswith(".csv"):
            group_name = filename.split("_")[0]
            df = pd.read_csv(filename)
            df["group"] = group_name
            dfs.append(df)

    if not dfs:
        raise FileNotFoundError("No CSV files found in the working directory.")

    df = pd.concat(dfs, ignore_index=True)

    if "cluster_ID" not in df.columns:
        raise KeyError("Input CSVs must contain cluster_ID.")

    # For backward compatibility
    if "mean_intensity" not in df.columns:
        if "mean_IF_intensity" in df.columns:
            df["mean_intensity"] = df["mean_IF_intensity"]
        else:
            raise KeyError(
                "Input CSVs must contain mean_intensity or mean_IF_intensity."
            )

    return df


def perform_t_tests(df, order):
    """Perform pairwise t-tests between groups."""
    comparisons = []

    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            group1, group2 = order[i], order[j]
            data1 = df[df["group"] == group1]["mean_intensity"]
            data2 = df[df["group"] == group2]["mean_intensity"]

            t_stat, p_value = ttest_ind(data1, data2)

            comparisons.append({
                "group1": group1,
                "group2": group2,
                "statistic": t_stat,
                "p-adj": p_value,
                "reject": p_value < 0.05,
            })

    return pd.DataFrame(comparisons)


def perform_dunnett(df, order, alt):
    """Perform Dunnett's tests comparing each non-control group to the first group in order."""
    control_group = order[0]
    treatment_groups = order[1:]

    control_data = df[df["group"] == control_group]["mean_intensity"].values
    experimental_data = [
        df[df["group"] == group]["mean_intensity"].values
        for group in treatment_groups
    ]

    test_stats = dunnett(*experimental_data, control=control_data, alternative=alt)

    return pd.DataFrame({
        "group1": [control_group] * len(test_stats.pvalue),
        "group2": treatment_groups,
        "statistic": test_stats.statistic,
        "p-adj": test_stats.pvalue,
        "reject": test_stats.pvalue < 0.05,
    })


def safe_col_name(text):
    """Make text safe for CSV column names."""
    return (
        str(text)
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace("(", "")
        .replace(")", "")
    )


def write_dunnett_wide_csv(test_df_all, output_folder, output_prefix, order):
    """
    Write a wide-format Dunnett summary CSV.

    One row per cluster or cluster-region pair.
    Columns include group means, n values, treatment-control diffs,
    adjusted p-values, and significance labels.
    """

    control_group = order[0]
    control_col = safe_col_name(control_group)

    id_cols = ["cluster_ID"]
    if "region_ID" in test_df_all.columns:
        id_cols.append("region_ID")

    metadata_cols = [col for col in ["region", "abbr"] if col in test_df_all.columns]

    rows = []

    for keys, df in test_df_all.groupby(id_cols, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)

        row = dict(zip(id_cols, keys))

        for col in metadata_cols:
            values = df[col].dropna().unique()
            row[col] = values[0] if len(values) > 0 else ""

        row["control_group"] = control_group

        # Add n and mean columns for the control group.
        control_rows = df[df["group1"] == control_group]
        if not control_rows.empty:
            row[f"n_{control_col}"] = control_rows["n_group1"].iloc[0]
            row[f"mean_{control_col}"] = control_rows["mean_group1"].iloc[0]
        else:
            row[f"n_{control_col}"] = np.nan
            row[f"mean_{control_col}"] = np.nan

        # Add n and mean columns for each treatment group.
        for group in order[1:]:
            group_col = safe_col_name(group)
            match = df[df["group2"] == group]

            if match.empty:
                row[f"n_{group_col}"] = np.nan
                row[f"mean_{group_col}"] = np.nan
            else:
                match = match.iloc[0]
                row[f"n_{group_col}"] = match["n_group2"]
                row[f"mean_{group_col}"] = match["mean_group2"]

        # Add treatment-control differences.
        for group in order[1:]:
            group_col = safe_col_name(group)
            match = df[df["group2"] == group]

            if match.empty:
                row[f"diff_{group_col}_minus_{control_col}"] = np.nan
            else:
                row[f"diff_{group_col}_minus_{control_col}"] = match["diff_group2_minus_group1"].iloc[0]

        # Add Dunnett-adjusted p-values and significance labels.
        for group in order[1:]:
            group_col = safe_col_name(group)
            match = df[df["group2"] == group]

            if match.empty:
                row[f"p_adj_{control_col}_v_{group_col}"] = np.nan
                row[f"sig_{control_col}_v_{group_col}"] = ""
            else:
                match = match.iloc[0]
                row[f"p_adj_{control_col}_v_{group_col}"] = match["p-adj"]
                row[f"sig_{control_col}_v_{group_col}"] = match["significance"]

        rows.append(row)

    wide_df = pd.DataFrame(rows)

    output_csv = output_folder / f"{output_prefix}_dunnett_wide.csv"
    wide_df.to_csv(output_csv, index=False)

    print(f"Wide Dunnett summary CSV saved to ./{output_csv}\n")

def perform_tukey(df):
    """Perform Tukey's HSD test."""
    test_results = pairwise_tukeyhsd(df["mean_intensity"], df["group"]).summary()
    test_df = pd.DataFrame(test_results.data[1:], columns=test_results.data[0])

    if "meandiff" in test_df.columns:
        test_df = test_df.rename(columns={"meandiff": "mean_diff"})

    if "p-adj" in test_df.columns:
        test_df["p-adj"] = test_df["p-adj"].astype(float)

    if "reject" in test_df.columns:
        test_df["reject"] = test_df["reject"].astype(bool)

    if "statistic" not in test_df.columns:
        test_df["statistic"] = np.nan

    return test_df


def add_group_summary_columns(test_df, df):
    """Add n, means, and mean differences to the stats table."""
    group_stats = (
        df.groupby("group")["mean_intensity"]
        .agg(["count", "mean"])
        .rename(columns={"count": "n", "mean": "mean"})
    )

    rows = []
    for _, row in test_df.iterrows():
        row = row.to_dict()
        group1 = row["group1"]
        group2 = row["group2"]

        row["n_group1"] = int(group_stats.loc[group1, "n"]) if group1 in group_stats.index else np.nan
        row["n_group2"] = int(group_stats.loc[group2, "n"]) if group2 in group_stats.index else np.nan
        row["mean_group1"] = float(group_stats.loc[group1, "mean"]) if group1 in group_stats.index else np.nan
        row["mean_group2"] = float(group_stats.loc[group2, "mean"]) if group2 in group_stats.index else np.nan
        row["diff_group2_minus_group1"] = row["mean_group2"] - row["mean_group1"]

        rows.append(row)

    return pd.DataFrame(rows)


def run_stats(df, order, test_type, alt):
    """Run the selected statistical test."""
    missing_groups = [group for group in order if group not in df["group"].unique()]
    if missing_groups:
        raise ValueError(f"Missing group(s) for this comparison: {missing_groups}")

    if test_type == "tukey":
        test_df = perform_tukey(df)
    elif test_type == "dunnett":
        test_df = perform_dunnett(df, order, alt)
    elif test_type == "ttest":
        test_df = perform_t_tests(df, order)
    else:
        raise ValueError(f"Unknown test type: {test_type}")

    test_df = add_group_summary_columns(test_df, df)
    test_df["significance"] = test_df["p-adj"].apply(significance_label)

    return test_df


def prepare_plot_df(df, order, labels):
    """Apply group order and labels for plotting."""
    df = df.copy()
    df["group"] = df["group"].astype(pd.CategoricalDtype(categories=order, ordered=True))
    df = df.sort_values("group")

    labels_mapping = dict(zip(order, labels))
    df["group_label"] = df["group"].map(labels_mapping)

    return df


def add_significance_bars(ax, significant_comparisons, groups, y_min, y_max):
    """Add significance bars to the plot."""
    data_range = y_max - y_min

    if data_range == 0:
        data_range = abs(y_max) if y_max != 0 else 1

    height_diff = data_range * 0.1
    y_pos = y_max + 0.5 * height_diff

    for _, row in significant_comparisons.iterrows():
        group1, group2 = row["group1"], row["group2"]

        if group1 not in groups or group2 not in groups:
            continue

        x1 = np.where(groups == group1)[0][0]
        x2 = np.where(groups == group2)[0][0]

        ax.plot(
            [x1, x1, x2, x2],
            [y_pos, y_pos + height_diff, y_pos + height_diff, y_pos],
            lw=1.5,
            c="black",
        )

        ax.text(
            (x1 + x2) * 0.5,
            y_pos + 0.8 * height_diff,
            significance_label(row["p-adj"]),
            horizontalalignment="center",
            size="xx-large",
            color="black",
            weight="bold",
        )

        y_pos += 3 * height_diff

    return y_pos, height_diff

def get_pair_df(all_df, cluster_id, region_id=None):
    """Subset data for one cluster or cluster-region pair."""
    df = all_df[all_df["cluster_ID"] == cluster_id].copy()

    if region_id is not None:
        df = df[df["region_ID"] == region_id].copy()

    if df.empty:
        raise ValueError(f"No data found for cluster {cluster_id}, region {region_id}")

    return df

def summarize_pair(
    all_df,
    cluster_id,
    region_id=None,
    order=None,
    labels=None,
    test_type="tukey",
    alt="two-sided",
    region_lut=None,
):
    """Run stats for one cluster or cluster-region pair without plotting."""
    df = get_pair_df(all_df, cluster_id, region_id)
    df = prepare_plot_df(df, order, labels)

    test_df = run_stats(df, order, test_type, alt)

    test_df["cluster_ID"] = cluster_id

    if region_id is not None:
        region_name, region_abbr = get_region_info(region_id, region_lut)
        test_df["region_ID"] = region_id

        if region_name is not None:
            test_df["region"] = region_name
        if region_abbr is not None:
            test_df["abbr"] = region_abbr

    return test_df

def plot_data(
    all_df,
    cluster_id,
    region_id=None,
    order=None,
    labels=None,
    test_type="tukey",
    alt="two-sided",
    ylabel="Mean IF Intensity",
    region_lut=None,
    symbol_alpha=1.0,
):
    """Plot data and return stats for one cluster or cluster-region pair."""
    df = get_pair_df(all_df, cluster_id, region_id)
    df = prepare_plot_df(df, order, labels)
    test_df = run_stats(df, order, test_type, alt)

    predefined_colors = [
        "#2D67C8",  # blue
        "#D32525",  # red
        "#27AF2E",  # green
        "#FFD700",  # gold
        "#FF6347",  # tomato
        "#8A2BE2",  # blueviolet
    ]
    selected_colors = predefined_colors[:len(order)]
    group_colors = dict(zip(order, selected_colors))

    plt.figure(figsize=(4, 4))
    ax = sns.barplot(
        x="group_label",
        y="mean_intensity",
        data=df,
        color="white",
        errorbar=("se"),
        capsize=0.1,
        linewidth=2,
        edgecolor="black",
    )

    sns.stripplot(
        x="group_label",
        y="mean_intensity",
        hue="group",
        data=df,
        palette=group_colors,
        size=8,
        linewidth=1,
        edgecolor="black",
        jitter=0.25,
        alpha=symbol_alpha,
    )

    if ax.legend_:
        ax.legend_.remove()

    ax.set_ylabel(ylabel, weight="bold")
    ax.set_xlabel("")
    ax.set_xticks(np.arange(len(df["group_label"].unique())))
    ax.set_xticklabels(ax.get_xticklabels(), weight="bold")
    ax.tick_params(axis="both", which="major", width=2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_linewidth(2)
    ax.spines["left"].set_linewidth(2)

    y_max = df["mean_intensity"].max()
    y_min = df["mean_intensity"].min()

    significant_comparisons = test_df[test_df["reject"] == True]
    groups = np.array(order)

    y_pos, height_diff = add_significance_bars(
        ax,
        significant_comparisons,
        groups,
        y_min,
        y_max,
    )

    plt.ylim(y_min - 2 * height_diff, y_pos + 2 * height_diff)

    output_folder = Path("cluster_region_mean_IF_summary" if region_id is not None else "cluster_mean_IF_summary")
    output_folder.mkdir(parents=True, exist_ok=True)

    region_name, region_abbr = get_region_info(region_id, region_lut) if region_id is not None else (None, None)

    if region_id is None:
        title = f"Cluster: {cluster_id}"
        file_stem = f"cluster_{cluster_id}"
    else:
        if region_abbr:
            safe_abbr = safe_filename(region_abbr)
            title = f"Cluster: {cluster_id}, Region: {region_id} ({region_abbr})"
            file_stem = f"cluster_{cluster_id}_{safe_abbr}_region_{region_id}"
        else:
            title = f"Cluster: {cluster_id}, Region: {region_id}"
            file_stem = f"cluster_{cluster_id}_region_{region_id}"

    wrapped_title = textwrap.fill(title, 42)
    plt.title(wrapped_title)
    plt.tight_layout()

    file_prefix = "_" if not significant_comparisons.empty else ""
    plt.savefig(output_folder / f"{file_prefix}{file_stem}.pdf")
    plt.close()

    test_df["cluster_ID"] = cluster_id

    if region_id is not None:
        test_df["region_ID"] = region_id
        if region_name is not None:
            test_df["region"] = region_name
        if region_abbr is not None:
            test_df["abbr"] = region_abbr

    return test_df


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if (args.order and not args.labels) or (not args.order and args.labels):
        raise ValueError("Both --order and --labels must be provided together.")

    if len(args.order) != len(args.labels):
        raise ValueError("The number of entries in --order and --labels must match.")

    if len(args.order) < 2:
        raise ValueError("At least two groups are required for comparison.")

    if len(args.order) == 2:
        test_type = "ttest" if args.test is None else args.test
    elif len(args.order) > 2 and args.test is None:
        test_type = "tukey"
    else:
        test_type = args.test
    
    if args.symbol_alpha < 0 or args.symbol_alpha > 1:
        raise ValueError("--symbol_alpha must be between 0 and 1.")

    print(f"\n[bold]CSVs in the working dir to process (the first word defines the groups):\n")
    for filename in os.listdir():
        if filename.endswith(".csv"):
            print(f"    {filename}")
    print()

    all_df = load_all_data()
    has_regions = "region_ID" in all_df.columns

    if args.cluster_ids:
        all_df = all_df[all_df["cluster_ID"].isin(args.cluster_ids)]

    if has_regions and args.region_ids:
        all_df = all_df[all_df["region_ID"].isin(args.region_ids)]

    if all_df.empty:
        raise ValueError("No data left after filtering by cluster_ID and/or region_ID.")

    region_lut = load_region_lut(args.lut) if has_regions else None

    if has_regions:
        pairs_to_process = (
            all_df[["cluster_ID", "region_ID"]]
            .drop_duplicates()
            .sort_values(["cluster_ID", "region_ID"])
        )
    else:
        pairs_to_process = (
            all_df[["cluster_ID"]]
            .drop_duplicates()
            .sort_values("cluster_ID")
        )
        pairs_to_process["region_ID"] = None

    test_df_all = pd.DataFrame()

    for _, pair in pairs_to_process.iterrows():
        cluster_id = int(pair["cluster_ID"])
        region_id = int(pair["region_ID"]) if has_regions else None

        if args.verbose:
            if has_regions:
                print(f"Summarizing cluster {cluster_id}, region {region_id}")
            else:
                print(f"Summarizing cluster {cluster_id}")

        test_df = summarize_pair(
            all_df,
            cluster_id,
            region_id=region_id,
            order=args.order,
            labels=args.labels,
            test_type=test_type,
            alt=args.alternate,
            region_lut=region_lut,
        )

        test_df_all = pd.concat([test_df_all, test_df], ignore_index=True)

    id_cols = ["cluster_ID"] + (["region_ID"] if has_regions else [])
    optional_region_cols = [col for col in ["region", "abbr"] if col in test_df_all.columns]
    stats_cols = [
        "group1",
        "group2",
        "statistic",
        "p-adj",
        "reject",
        "significance",
        "n_group1",
        "n_group2",
        "mean_group1",
        "mean_group2",
        "diff_group2_minus_group1",
    ]

    keep_cols = id_cols + optional_region_cols + [col for col in stats_cols if col in test_df_all.columns]
    test_df_all = test_df_all[keep_cols]

    output_folder = Path("cluster_region_mean_IF_summary" if has_regions else "cluster_mean_IF_summary")
    output_folder.mkdir(parents=True, exist_ok=True)

    output_prefix = "cluster_region_mean_IF_summary" if has_regions else "cluster_mean_IF_summary"
    output_csv = output_folder / f"{output_prefix}_{test_type}.csv"
    test_df_all.to_csv(output_csv, index=False)

    print(f"\n{test_df_all}\n")
    print(f"Summary CSV saved to ./{output_csv}")

    if test_type == "dunnett":
        write_dunnett_wide_csv(
            test_df_all,
            output_folder,
            output_prefix,
            args.order,
        )

    if not args.skip_plots:
        for _, pair in pairs_to_process.iterrows():
            cluster_id = int(pair["cluster_ID"])
            region_id = int(pair["region_ID"]) if has_regions else None

            if args.verbose:
                if has_regions:
                    print(f"Plotting cluster {cluster_id}, region {region_id}")
                else:
                    print(f"Plotting cluster {cluster_id}")

            plot_data(
                all_df,
                cluster_id,
                region_id=region_id,
                order=args.order,
                labels=args.labels,
                test_type=test_type,
                alt=args.alternate,
                ylabel=args.ylabel,
                region_lut=region_lut,
                symbol_alpha=args.symbol_alpha,
            )

    verbose_end_msg()


if __name__ == "__main__":
    main()