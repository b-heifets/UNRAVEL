#!/usr/bin/env python3
"""
Run project-specific two-group tests for mean intensities from cluster data.

Prereqs:
    - `cstats_mean_IF` to generate mean intensity CSVs for each sample.

Inputs:
    - CSVs in the working directory (one per sample) or specified with -i
    - the condition is encoded as the first underscore-delimited field in the filename
      e.g., AwS_sample01_cluster_mean_intensity.csv -> condition AwS
    - each CSV contains one row per cluster (columns: cluster_ID, mean_intensity, etc.)

For each cluster, outputs:
    - group means, SD, SEM, and n for the two conditions
    - difference: second condition minus first condition
      default: AnS - AwS
    - Student's t-test (equal-variance)
    - higher-mean group
    - Cohen's d and Hedges' g, using condition order:
      positive = second condition > first condition

Usage:
------
    ./mean_IF_2group_ttest.py -c AwS AnS [OPTIONS]
"""

import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install
from scipy.stats import ttest_ind

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, verbose_end_msg, verbose_start_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-c', '--conditions', help='Conditions. Each condition must match first word of CSV filenames (underscore-separated).', required=True, nargs='*', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help="Path(s) or glob pattern(s) for input CSV files. Default: '*.csv'", default='*.csv', nargs='*', action=SM)
    opts.add_argument("-o", "--out", default="out/mean_intensity_2group_ttest_results.csv", help="Output CSV path. Default: out/mean_intensity_2group_ttest_results.csv", action=SM)
    opts.add_argument("-r", "--raw_out", default="out/mean_intensity_2group_ttest_raw_data.csv", help="Raw long-format output CSV path. Default: out/mean_intensity_2group_ttest_raw_data.csv", action=SM)
    opts.add_argument("-vc", "--value_col", default="mean_intensity", help="Dependent-variable column. Default: mean_intensity", action=SM)
    opts.add_argument("-cc", "--cluster_col", default="cluster_ID", help="Cluster ID column. Default: cluster_ID", action=SM)
    opts.add_argument("-sc", "--sample_col", default="sample", help="Sample column. If absent, filename stem is used. Default: sample", action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Verbose output.', action='store_true')

    return parser.parse_args()

def p_to_sig(p):
    if pd.isna(p):
        return ""
    if p < 0.0001:
        return "****"
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "n.s."


def safe_float(x):
    try:
        if pd.isna(x):
            return np.nan
        return float(x)
    except Exception:
        return np.nan


def infer_condition(filename):
    return Path(filename).name.split("_")[0]

def load_mean_intensity_data(csvs, conditions, value_col, cluster_col, sample_col):
    conditions = [str(c) for c in conditions]
    condition_set = set(conditions)

    print(f"Found {len(csvs)} input CSV(s).")

    rows = []
    skipped = []

    for csv in csvs:
        condition = infer_condition(csv.name)
        if condition not in condition_set:
            skipped.append(csv.name)
            continue

        df = pd.read_csv(csv)
        missing_cols = [c for c in [cluster_col, value_col] if c not in df.columns]
        if missing_cols:
            raise ValueError(f"{csv} is missing required columns: {missing_cols}")

        if sample_col not in df.columns:
            df[sample_col] = csv.stem

        keep = df[[sample_col, cluster_col, value_col]].copy()
        keep["condition"] = condition
        keep["source_file"] = csv.name
        rows.append(keep)

    if not rows:
        raise ValueError(
            "No CSVs matched the requested condition prefixes. "
            f"Expected prefixes: {conditions}"
        )

    data = pd.concat(rows, ignore_index=True)
    data[value_col] = pd.to_numeric(data[value_col], errors="coerce")
    data = data.dropna(subset=[value_col, cluster_col, "condition"])
    data["condition"] = pd.Categorical(data["condition"], categories=conditions, ordered=True)

    found_conditions = set(data["condition"].astype(str))
    missing_conditions = [c for c in conditions if c not in found_conditions]
    if missing_conditions:
        raise ValueError(
            "Input CSVs did not include all requested conditions. "
            f"Missing: {missing_conditions}; found: {sorted(found_conditions)}"
        )

    if skipped:
        print(
            f"Skipped {len(skipped)} CSV(s) whose first filename field was not one of "
            f"{conditions}."
        )

    return data


def group_values(cluster_df, condition, value_col):
    return (
        cluster_df.loc[cluster_df["condition"].astype(str) == condition, value_col]
        .dropna()
        .to_numpy()
    )


def summarize_values(vals):
    n = int(len(vals))
    mean = safe_float(np.mean(vals)) if n else np.nan
    sd = safe_float(np.std(vals, ddof=1)) if n >= 2 else np.nan
    sem = safe_float(sd / np.sqrt(n)) if n >= 2 else np.nan
    return mean, sd, sem, n


def higher_by_mean(mean_ref, mean_test, ref_cond, test_cond):
    if pd.isna(mean_ref) or pd.isna(mean_test):
        return ""
    if np.isclose(mean_ref, mean_test):
        return "tie"
    return test_cond if mean_test > mean_ref else ref_cond


def hedges_g(vals_ref, vals_test):
    """
    Standardized mean difference using pooled SD.

    Sign convention:
        positive = test condition mean > reference condition mean
    """
    n_ref = len(vals_ref)
    n_test = len(vals_test)
    if n_ref < 2 or n_test < 2:
        return np.nan, np.nan

    mean_ref = np.mean(vals_ref)
    mean_test = np.mean(vals_test)
    var_ref = np.var(vals_ref, ddof=1)
    var_test = np.var(vals_test, ddof=1)
    df = n_ref + n_test - 2

    if df <= 0:
        return np.nan, np.nan

    pooled_var = ((n_ref - 1) * var_ref + (n_test - 1) * var_test) / df
    if pooled_var <= 0 or np.isclose(pooled_var, 0):
        return np.nan, np.nan

    d = (mean_test - mean_ref) / np.sqrt(pooled_var)

    # Small-sample correction.
    correction = 1 - (3 / (4 * (n_ref + n_test) - 9)) if (n_ref + n_test) > 2 else np.nan
    g = d * correction if not pd.isna(correction) else np.nan
    return safe_float(g)


def run_ttest(vals_ref, vals_test, min_n_per_group=2):
    if len(vals_ref) < min_n_per_group or len(vals_test) < min_n_per_group:
        return np.nan, np.nan

    try:
        res = ttest_ind(
            vals_test,
            vals_ref,
            equal_var=True,
            alternative="two-sided",
            nan_policy="omit",
        )
        return safe_float(res.statistic), safe_float(res.pvalue)
    except Exception:
        return np.nan, np.nan


def build_results(data, conditions, value_col, cluster_col, min_n_per_group=2):
    ref_cond, test_cond = [str(c) for c in conditions]
    diff_col = f"{test_cond}_minus_{ref_cond}"

    rows = []

    for cluster_id in sorted(data[cluster_col].unique()):
        cdf = data[data[cluster_col] == cluster_id].copy()

        vals_ref = group_values(cdf, ref_cond, value_col)
        vals_test = group_values(cdf, test_cond, value_col)

        mean_ref, sd_ref, sem_ref, n_ref = summarize_values(vals_ref)
        mean_test, sd_test, sem_test, n_test = summarize_values(vals_test)

        diff = (
            mean_test - mean_ref
            if not pd.isna(mean_test) and not pd.isna(mean_ref)
            else np.nan
        )

        t_stat, p = run_ttest(
            vals_ref=vals_ref,
            vals_test=vals_test,
            min_n_per_group=min_n_per_group,
        )

        hedges_g_val = hedges_g(vals_ref, vals_test)

        rows.append({
            "cluster_ID": cluster_id,
            f"{ref_cond}_mean_IF": mean_ref,
            f"{test_cond}_mean_IF": mean_test,
            f"{ref_cond}_sd": sd_ref,
            f"{test_cond}_sd": sd_test,
            f"{ref_cond}_sem": sem_ref,
            f"{test_cond}_sem": sem_test,
            f"{ref_cond}_n": n_ref,
            f"{test_cond}_n": n_test,
            diff_col: safe_float(diff),
            "higher_mean": higher_by_mean(mean_ref, mean_test, ref_cond, test_cond),
            "t_stat": t_stat,
            "p": p,
            "sig": p_to_sig(p),
            "hedges_g": hedges_g_val,
            "test": "Student_ttest",
            "effect_direction": (
                f"{test_cond}>{ref_cond}" if not pd.isna(diff) and diff > 0
                else f"{test_cond}<{ref_cond}" if not pd.isna(diff) and diff < 0
                else "tie" if not pd.isna(diff)
                else ""
            ),
        })

    results = pd.DataFrame(rows)

    sort_cols = ["p", "cluster_ID"]
    return results.sort_values(sort_cols, na_position="last")


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    csvs = match_files(args.input)

    # Filter CSVs to only those that match the requested conditions based on filename prefix
    csvs = [
        f for f in csvs
        if any(f.name.startswith(f'{group}_') for group in args.conditions)
    ]

    data = load_mean_intensity_data(
        csvs=csvs,
        conditions=args.conditions,
        value_col=args.value_col,
        cluster_col=args.cluster_col,
        sample_col=args.sample_col,
    )

    raw_out = Path(args.raw_out)
    raw_out.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(raw_out, index=False)

    results = build_results(
        data=data,
        conditions=args.conditions,
        value_col=args.value_col,
        cluster_col=args.cluster_col,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(out, index=False)

    ref_cond, test_cond = args.conditions
    print(f"Saved raw long-format data: {raw_out}")
    print(f"Saved two-group summary: {out}")
    print(f"Comparison: {test_cond} - {ref_cond}")
    print(results.head(20).to_string(index=False))

    verbose_end_msg()


if __name__ == "__main__":
    main()
