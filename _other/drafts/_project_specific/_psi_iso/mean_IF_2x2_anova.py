#!/usr/bin/env python3
"""
Run project-specific 2x2 ANOVAs for mean IF cluster data.

This script is intended for the Psi/Iso mean_IF workflow where each input CSV is
one sample, the condition is encoded as the first underscore-delimited field in
its filename, and each CSV contains one row per cluster.

Default design:
    AwS = Awake Saline
    AwP = Awake Psilocin
    AnS = Anesthetized Saline
    AnP = Anesthetized Psilocin

Default condition map:
    condition,Drug,State
    AwS,Saline,Awake
    AwP,Psilocin,Awake
    AnS,Saline,Anesthetized
    AnP,Psilocin,Anesthetized

For each cluster, outputs:
    - group means for AwS/AwP/AnS/AnP
    - awake psilocin effect: AwP - AwS
    - anesthetized psilocin effect: AnP - AnS
    - interaction effect: (AwP - AwS) - (AnP - AnS)
    - Type-II ANOVA p-values for Drug, State, and Drug:State
    - AwP vs AwS and AnP vs AnS t-tests with Holm-Sidak correction
    - higher-mean group for each comparison/effect
    - awake-anchored psilocin-effect persistence classification based on the
      Holm-Sidak-corrected AwP vs AwS and AnP vs AnS comparisons

Example:
    mean_IF_2x2_anova.py \
        --condition_map state_drug_map.csv \
        --out mean_IF_2x2_anova_results.csv

Example condition_map CSV:
    condition,Drug,State
    AwS,Saline,Awake
    AwP,Psilocin,Awake
    AnS,Saline,Anesthetized
    AnP,Psilocin,Anesthetized
"""

import warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from pathlib import Path
from rich import print
from rich.traceback import install
from scipy.stats import ttest_ind
from statsmodels.formula.api import ols
from statsmodels.stats.multitest import multipletests

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, verbose_end_msg, verbose_start_msg


DEFAULT_MAP = pd.DataFrame({
    "condition": ["AwS", "AwP", "AnS", "AnP"],
    "Drug": ["Saline", "Psilocin", "Saline", "Psilocin"],
    "State": ["Awake", "Awake", "Anesthetized", "Anesthetized"],
})

DEFAULT_GROUP_ORDER = ["AwS", "AwP", "AnS", "AnP"]
MIN_N_PER_CELL = 2
EQUAL_VAR = True  # Assume equal variance for t-tests; can be changed to False if needed.

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument("-cm", "--condition_map", help="Optional CSV mapping condition to Drug and State. Default: built-in 2x2 map for AwS/AwP/AnS/AnP", default=None, action=SM)
    opts.add_argument('-i', '--input', help="Path(s) or glob pattern(s) for input CSV files. Default: '*.csv'", default='*.csv', nargs='*', action=SM)
    opts.add_argument("-o", "--out", default="out/mean_IF_2x2_anova_results.csv", help="Output CSV path. Default: out/mean_IF_2x2_anova_results.csv", action=SM)
    opts.add_argument("-r", "--raw_out", default="out/mean_IF_2x2_anova_raw_data.csv", help="Raw long-format output CSV path. Default: out/mean_IF_2x2_anova_raw_data.csv", action=SM)
    opts.add_argument("-vc", "--value_col", default="mean_intensity", help="Dependent-variable column. Default: mean_intensity", action=SM)
    opts.add_argument("-cc", "--cluster_col", default="cluster_ID", help="Cluster ID column. Default: cluster_ID", action=SM)
    opts.add_argument("-sc", "--sample_col", default="sample", help="Sample column. If absent, filename stem is used. Default: sample", action=SM)
    opts.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

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


def read_condition_map(path):
    if path is None:
        return DEFAULT_MAP.copy()
    group_map = pd.read_csv(path)
    required = {"condition", "Drug", "State"}
    missing = required - set(group_map.columns)
    if missing:
        raise ValueError(f"condition_map is missing required columns: {sorted(missing)}")
    return group_map[list(required)].copy()


def infer_condition(filename):
    return Path(filename).name.split("_")[0]


def load_mean_if_data(csv_paths, group_map, value_col, cluster_col, sample_col):
    conditions = set(group_map["condition"].astype(str))

    rows = []
    skipped = []

    for csv in csv_paths:
        condition = infer_condition(csv.name)
        if condition not in conditions:
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
            "No CSVs matched the conditions in the condition map. "
            f"Conditions expected: {sorted(conditions)}"
        )

    data = pd.concat(rows, ignore_index=True)
    data[value_col] = pd.to_numeric(data[value_col], errors="coerce")
    data = data.dropna(subset=[value_col, cluster_col, "condition"])
    data = data.merge(group_map, on="condition", how="left")

    # Treat factors as categorical for statsmodels.
    data["Drug"] = data["Drug"].astype("category")
    data["State"] = data["State"].astype("category")
    data["condition"] = data["condition"].astype("category")

    if skipped:
        print(f"Skipped {len(skipped)} CSV(s) whose first filename field was not in the condition map.")

    return data


def group_mean(cluster_df, condition, value_col):
    vals = cluster_df.loc[cluster_df["condition"].astype(str) == condition, value_col]
    return safe_float(vals.mean())


def group_n(cluster_df, condition, value_col):
    vals = cluster_df.loc[cluster_df["condition"].astype(str) == condition, value_col]
    return int(vals.notna().sum())


def higher_by_mean(means, a, b):
    ma = means.get(a, np.nan)
    mb = means.get(b, np.nan)
    if pd.isna(ma) or pd.isna(mb):
        return ""
    if np.isclose(ma, mb):
        return "tie"
    return a if ma > mb else b


def classify_effect(awake_diff, anes_diff, awake_reject, anes_reject,
                    awake_p_hs, anes_p_hs):
    """Classify awake-anchored persistence using Holm-Sidak comparisons."""
    if pd.isna(awake_p_hs) or pd.isna(anes_p_hs):
        return "incomplete"

    if awake_reject and anes_reject:
        if pd.isna(awake_diff) or pd.isna(anes_diff):
            return "incomplete"
        if np.isclose(awake_diff, 0) or np.isclose(anes_diff, 0):
            return "significant_but_zero_mean_difference_check"
        if np.sign(awake_diff) == np.sign(anes_diff):
            return "preserved"
        return "reversed_under_anesthesia"

    if awake_reject and not anes_reject:
        return "not_preserved_under_anesthesia"
    if not awake_reject and anes_reject:
        return "anesthesia_only_significant"
    return "no_significant_psilocin_effect"


def warn_for_small_cells(cluster_id, ns):
    """Warn when a cluster lacks enough observations for stable inference."""
    small = {condition: n for condition, n in ns.items() if n < MIN_N_PER_CELL}
    if small:
        details = ", ".join(f"{condition} n={n}" for condition, n in small.items())
        warnings.warn(
            f"Cluster {cluster_id}: {details}. At least {MIN_N_PER_CELL} observations "
            "per condition are required; affected ANOVA/post-hoc results will be NaN.",
            RuntimeWarning,
            stacklevel=2,
        )


def run_anova(cluster_df, value_col):
    counts = cluster_df.groupby(["Drug", "State"], observed=True)[value_col].count()
    if len(counts) < 4 or counts.min() < MIN_N_PER_CELL:
        return {"Drug_p": np.nan, "State_p": np.nan, "Drug_State_p": np.nan}

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = ols(f"{value_col} ~ C(Drug) * C(State)", data=cluster_df).fit()
            aov = sm.stats.anova_lm(model, typ=2)
    except Exception as e:
        return {"Drug_p": np.nan, "State_p": np.nan, "Drug_State_p": np.nan, "anova_error": str(e)}

    out = {"Drug_p": np.nan, "State_p": np.nan, "Drug_State_p": np.nan}
    for term, col in [
        ("C(Drug)", "Drug_p"),
        ("C(State)", "State_p"),
        ("C(Drug):C(State)", "Drug_State_p"),
    ]:
        if term in aov.index:
            out[col] = safe_float(aov.loc[term, "PR(>F)"])
    return out


def run_ttest(cluster_df, cond_a, cond_b, value_col, equal_var):
    vals_a = cluster_df.loc[cluster_df["condition"].astype(str) == cond_a, value_col].dropna().to_numpy()
    vals_b = cluster_df.loc[cluster_df["condition"].astype(str) == cond_b, value_col].dropna().to_numpy()
    if len(vals_a) < MIN_N_PER_CELL or len(vals_b) < MIN_N_PER_CELL:
        return np.nan
    try:
        return safe_float(ttest_ind(vals_a, vals_b, equal_var=equal_var, alternative="two-sided").pvalue)
    except Exception:
        return np.nan


def build_results(data, value_col, cluster_col, equal_var):
    rows = []
    for cluster_id in sorted(data[cluster_col].unique()):
        cdf = data[data[cluster_col] == cluster_id].copy()

        means = {cond: group_mean(cdf, cond, value_col) for cond in DEFAULT_GROUP_ORDER}
        ns = {cond: group_n(cdf, cond, value_col) for cond in DEFAULT_GROUP_ORDER}
        warn_for_small_cells(cluster_id, ns)

        awake_diff = means["AwP"] - means["AwS"] if not pd.isna(means["AwP"]) and not pd.isna(means["AwS"]) else np.nan
        anes_diff = means["AnP"] - means["AnS"] if not pd.isna(means["AnP"]) and not pd.isna(means["AnS"]) else np.nan
        interaction_effect = awake_diff - anes_diff if not pd.isna(awake_diff) and not pd.isna(anes_diff) else np.nan
        diff_ratio = abs(anes_diff) / abs(awake_diff) if not pd.isna(awake_diff) and not np.isclose(awake_diff, 0) and not pd.isna(anes_diff) else np.nan

        anova = run_anova(cdf, value_col)
        p_awake = run_ttest(cdf, "AwP", "AwS", value_col, equal_var)
        p_anes = run_ttest(cdf, "AnP", "AnS", value_col, equal_var)

        p_list = [p_awake, p_anes]
        valid_p = [p for p in p_list if not pd.isna(p)]
        p_awake_hs = np.nan
        p_anes_hs = np.nan
        awake_reject = False
        anes_reject = False
        if len(valid_p) == 2:
            reject, p_corr, _, _ = multipletests(p_list, alpha=0.05, method="holm-sidak")
            p_awake_hs, p_anes_hs = [safe_float(x) for x in p_corr]
            awake_reject, anes_reject = [bool(x) for x in reject]

        drug_higher = ""
        state_higher = ""
        psilo_mean = np.nanmean([means["AwP"], means["AnP"]])
        saline_mean = np.nanmean([means["AwS"], means["AnS"]])
        awake_mean = np.nanmean([means["AwS"], means["AwP"]])
        anes_mean = np.nanmean([means["AnS"], means["AnP"]])
        if not pd.isna(psilo_mean) and not pd.isna(saline_mean):
            drug_higher = "Psilocin" if psilo_mean > saline_mean else "Saline" if saline_mean > psilo_mean else "tie"
        if not pd.isna(awake_mean) and not pd.isna(anes_mean):
            state_higher = "Awake" if awake_mean > anes_mean else "Anesthetized" if anes_mean > awake_mean else "tie"

        classification = classify_effect(
            awake_diff=awake_diff,
            anes_diff=anes_diff,
            awake_reject=awake_reject,
            anes_reject=anes_reject,
            awake_p_hs=p_awake_hs,
            anes_p_hs=p_anes_hs,
        )

        row = {
            "cluster_ID": cluster_id,
            "AwS_mean_IF": means["AwS"],
            "AwP_mean_IF": means["AwP"],
            "AnS_mean_IF": means["AnS"],
            "AnP_mean_IF": means["AnP"],
            "AwS_n": ns["AwS"],
            "AwP_n": ns["AwP"],
            "AnS_n": ns["AnS"],
            "AnP_n": ns["AnP"],
            "awake_diff_AwP_minus_AwS": awake_diff,
            "anes_diff_AnP_minus_AnS": anes_diff,
            "interaction_effect_awake_diff_minus_anes_diff": interaction_effect,
            "anes_to_awake_abs_diff_ratio": diff_ratio,
            "Drug_p": anova.get("Drug_p", np.nan),
            "Drug_sig": p_to_sig(anova.get("Drug_p", np.nan)),
            "Drug_higher_mean": drug_higher,
            "State_p": anova.get("State_p", np.nan),
            "State_sig": p_to_sig(anova.get("State_p", np.nan)),
            "State_higher_mean": state_higher,
            "Drug_State_p": anova.get("Drug_State_p", np.nan),
            "Drug_State_sig": p_to_sig(anova.get("Drug_State_p", np.nan)),
            "AwP_vs_AwS_p": p_awake,
            "AwP_vs_AwS_p_holm_sidak": p_awake_hs,
            "AwP_vs_AwS_sig_holm_sidak": p_to_sig(p_awake_hs),
            "AwP_vs_AwS_reject_holm_sidak": awake_reject,
            "AwP_vs_AwS_higher_mean": higher_by_mean(means, "AwP", "AwS"),
            "AnP_vs_AnS_p": p_anes,
            "AnP_vs_AnS_p_holm_sidak": p_anes_hs,
            "AnP_vs_AnS_sig_holm_sidak": p_to_sig(p_anes_hs),
            "AnP_vs_AnS_reject_holm_sidak": anes_reject,
            "AnP_vs_AnS_higher_mean": higher_by_mean(means, "AnP", "AnS"),
            "psilocin_effect_classification": classification,
            "potential_state_confound_note": "baseline_state_shift_check" if anova.get("State_p", np.nan) < 0.05 else "",
        }
        if "anova_error" in anova:
            row["anova_error"] = anova["anova_error"]
        rows.append(row)

    results = pd.DataFrame(rows)
    return results.sort_values("cluster_ID")

def build_concise_results(results):
    """Return a concise table of the main ANOVA and post-hoc results."""
    concise_cols = [
        "cluster_ID",
        "Drug_State_p",
        "Drug_State_sig",
        "AwP_vs_AwS_p_holm_sidak",
        "AwP_vs_AwS_sig_holm_sidak",
        "AwP_vs_AwS_higher_mean",
        "AnP_vs_AnS_p_holm_sidak",
        "AnP_vs_AnS_sig_holm_sidak",
        "AnP_vs_AnS_higher_mean",
        "psilocin_effect_classification",
    ]

    concise = results.loc[:, concise_cols].copy()

    return concise.rename(columns={
        "Drug_State_p": "interaction_p",
        "Drug_State_sig": "interaction_sig",
        "AwP_vs_AwS_p_holm_sidak": "awake_p_HS",
        "AwP_vs_AwS_sig_holm_sidak": "awake_sig",
        "AwP_vs_AwS_higher_mean": "awake_higher_mean",
        "AnP_vs_AnS_p_holm_sidak": "anes_p_HS",
        "AnP_vs_AnS_sig_holm_sidak": "anes_sig",
        "AnP_vs_AnS_higher_mean": "anes_higher_mean",
        "psilocin_effect_classification": "classification",
    })


def print_results_preview(concise_results):
    """Print the concise results table."""
    print(concise_results.to_string(
        index=False,
        float_format=lambda x: f"{x:.4g}",
    ))


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    group_map = read_condition_map(args.condition_map)

    csvs = match_files(args.input)

    data = load_mean_if_data(
        csv_paths=csvs,
        group_map=group_map,
        value_col=args.value_col,
        cluster_col=args.cluster_col,
        sample_col=args.sample_col,
    )

    raw_out = Path(args.raw_out)
    raw_out.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(raw_out, index=False)

    results = build_results(
        data=data,
        value_col=args.value_col,
        cluster_col=args.cluster_col,
        equal_var=EQUAL_VAR,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(out, index=False)

    concise_results = build_concise_results(results)
    concise_out = out.with_name(f"{out.stem}_concise{out.suffix}")
    concise_results.to_csv(concise_out, index=False)

    print(f"\nSaved raw long-format data: {raw_out}")
    print(f"Saved full 2x2 ANOVA summary: {out}")
    print(f"Saved concise 2x2 ANOVA summary: {concise_out}\n")

    print_results_preview(concise_results)
    
    verbose_end_msg()


if __name__ == "__main__":
    main()
