#!/usr/bin/env python3
"""
Run project-specific two-group tests for mean IF cluster data.

This is a simpler companion to the Psi/Iso 2x2 ANOVA script for cases where
only two conditions are present, e.g.:

    AwS = Awake Saline
    AnS = Anesthetized Saline

Input convention:
    - each input CSV is one sample
    - the condition is encoded as the first underscore-delimited field in the filename
      e.g., AwS_sample01_cluster_mean_IF.csv -> condition AwS
    - each CSV contains one row per cluster

For each cluster, outputs:
    - group means, SD, SEM, and n for the two conditions
    - difference: second condition minus first condition
      default: AnS - AwS
    - Welch t-test by default, or equal-variance t-test with --equal_var
    - Holm-Sidak and Benjamini-Hochberg FDR correction across clusters
    - higher-mean group
    - Cohen's d and Hedges' g, using condition order:
      positive = second condition > first condition

Example:
    mean_IF_2group_ttest.py \
        -i 'cluster_mean_IF_AnS_v_AwS_vox_p_tstat1_q0.05_rev_cluster_index_LH/*.csv' \
        -o mean_IF_AnS_vs_AwS_ttest_results.csv

Equivalent explicit conditions:
    mean_IF_2group_ttest.py \
        -i '*.csv' \
        --conditions AwS AnS \
        -o mean_IF_AnS_minus_AwS_ttest_results.csv
"""

import argparse
from pathlib import Path
import glob as globlib

import numpy as np
import pandas as pd
from scipy.stats import ttest_ind
from statsmodels.stats.multitest import multipletests


DEFAULT_CONDITIONS = ["AwS", "AnS"]


def parse_args():
    p = argparse.ArgumentParser(
        description="Project-specific two-group t-tests for mean_IF cluster CSVs."
    )
    p.add_argument(
        "-i", "--input_dir", dest="inputs", nargs="*", default=None,
        help=(
            "Input directory, CSV file, or quoted glob pattern. May be repeated as "
            "multiple values after -i. Default: current directory."
        ),
    )
    p.add_argument(
        "-g", "--glob", default="*.csv",
        help="Input CSV glob used when an input is a directory. Default: *.csv",
    )
    p.add_argument(
        "--conditions", nargs=2, default=DEFAULT_CONDITIONS, metavar=("REF", "TEST"),
        help=(
            "Two condition prefixes to compare. Difference/effect size is TEST - REF. "
            "Default: AwS AnS, so diff = AnS - AwS."
        ),
    )
    p.add_argument(
        "-vcol", "--value_col", default="mean_IF_intensity",
        help="Dependent-variable column. Default: mean_IF_intensity",
    )
    p.add_argument(
        "-ccol", "--cluster_col", default="cluster_ID",
        help="Cluster ID column. Default: cluster_ID",
    )
    p.add_argument(
        "-scol", "--sample_col", default="sample",
        help="Sample column. If absent, filename stem is used. Default: sample",
    )
    p.add_argument(
        "-o", "--out", default="mean_IF_2group_ttest_results.csv",
        help="Output CSV path. Default: mean_IF_2group_ttest_results.csv",
    )
    p.add_argument(
        "--raw_out", default="mean_IF_2group_ttest_raw_data.csv",
        help="Raw long-format output CSV path. Default: mean_IF_2group_ttest_raw_data.csv",
    )
    p.add_argument(
        "--equal_var", action="store_true", default=False,
        help="Use equal-variance t-tests. Default: Welch t-tests.",
    )
    p.add_argument(
        "--min_n_per_group", type=int, default=2,
        help="Minimum n per condition needed for the t-test. Default: 2",
    )
    return p.parse_args()


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


def expand_input_csvs(inputs, glob_pattern):
    """Expand directories, individual CSV files, and quoted glob patterns."""
    if not inputs:
        inputs = ["."]

    csvs = []
    missing_inputs = []

    for item in inputs:
        item = str(item)

        # Allows commands like:
        #   -i 'cluster_mean_IF_dir/*.csv'
        if globlib.has_magic(item):
            matches = [Path(m) for m in globlib.glob(item, recursive=True)]
            csvs.extend([
                m for m in matches
                if m.is_file() and m.name.lower().endswith(".csv")
            ])
            continue

        path = Path(item).expanduser()

        if path.is_dir():
            csvs.extend([
                m for m in path.glob(glob_pattern)
                if m.is_file() and m.name.lower().endswith(".csv")
            ])
        elif path.is_file():
            if path.name.lower().endswith(".csv"):
                csvs.append(path)
        else:
            missing_inputs.append(item)

    # De-duplicate while keeping deterministic order.
    csvs = sorted({str(p): p for p in csvs}.values(), key=lambda p: str(p))

    if not csvs:
        msg = (
            "No input CSVs found. "
            f"inputs={inputs!r}; directory glob={glob_pattern!r}"
        )
        if missing_inputs:
            msg += f"; missing inputs={missing_inputs!r}"
        raise FileNotFoundError(msg)

    return csvs


def load_mean_if_data(inputs, glob_pattern, conditions, value_col, cluster_col, sample_col):
    csvs = expand_input_csvs(inputs, glob_pattern)
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


def cohen_d_and_hedges_g(vals_ref, vals_test):
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
    return safe_float(d), safe_float(g)


def run_ttest(vals_ref, vals_test, equal_var, min_n_per_group):
    if len(vals_ref) < min_n_per_group or len(vals_test) < min_n_per_group:
        return np.nan, np.nan

    try:
        res = ttest_ind(
            vals_test,
            vals_ref,
            equal_var=equal_var,
            alternative="two-sided",
            nan_policy="omit",
        )
        return safe_float(res.statistic), safe_float(res.pvalue)
    except Exception:
        return np.nan, np.nan


def add_multiple_testing_columns(results):
    """Add Holm-Sidak and BH-FDR adjusted p-values across clusters."""
    results = results.copy()

    results["p_holm_sidak"] = np.nan
    results["sig_holm_sidak"] = ""
    results["reject_holm_sidak_0.05"] = False

    results["p_fdr_bh"] = np.nan
    results["sig_fdr_bh"] = ""
    results["reject_fdr_bh_0.05"] = False

    pvals = results["p"].to_numpy(dtype=float)
    valid = ~pd.isna(pvals)

    if valid.sum() > 0:
        reject_hs, p_hs, _, _ = multipletests(pvals[valid], alpha=0.05, method="holm-sidak")
        reject_bh, p_bh, _, _ = multipletests(pvals[valid], alpha=0.05, method="fdr_bh")

        valid_idx = results.index[valid]
        results.loc[valid_idx, "p_holm_sidak"] = p_hs
        results.loc[valid_idx, "reject_holm_sidak_0.05"] = reject_hs
        results.loc[valid_idx, "sig_holm_sidak"] = [p_to_sig(p) for p in p_hs]

        results.loc[valid_idx, "p_fdr_bh"] = p_bh
        results.loc[valid_idx, "reject_fdr_bh_0.05"] = reject_bh
        results.loc[valid_idx, "sig_fdr_bh"] = [p_to_sig(p) for p in p_bh]

    return results


def build_results(data, conditions, value_col, cluster_col, equal_var, min_n_per_group):
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
            equal_var=equal_var,
            min_n_per_group=min_n_per_group,
        )

        cohen_d, hedges_g = cohen_d_and_hedges_g(vals_ref, vals_test)

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
            "cohen_d": cohen_d,
            "hedges_g": hedges_g,
            "test": "Student_ttest" if equal_var else "Welch_ttest",
            "effect_direction": (
                f"{test_cond}>{ref_cond}" if not pd.isna(diff) and diff > 0
                else f"{test_cond}<{ref_cond}" if not pd.isna(diff) and diff < 0
                else "tie" if not pd.isna(diff)
                else ""
            ),
        })

    results = pd.DataFrame(rows)
    results = add_multiple_testing_columns(results)

    sort_cols = ["p", "cluster_ID"]
    return results.sort_values(sort_cols, na_position="last")


def main():
    args = parse_args()

    data = load_mean_if_data(
        inputs=args.inputs,
        glob_pattern=args.glob,
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
        equal_var=args.equal_var,
        min_n_per_group=args.min_n_per_group,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(out, index=False)

    ref_cond, test_cond = args.conditions
    print(f"Saved raw long-format data: {raw_out}")
    print(f"Saved two-group summary: {out}")
    print(f"Comparison: {test_cond} - {ref_cond}")
    print(results.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
