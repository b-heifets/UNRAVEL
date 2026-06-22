#!/usr/bin/env python3
"""
Audit z-scored vs non-z-scored mean IF cluster results.

This script pairs matching cluster result directories under:
    mean_IF_z/cluster_mean_z_<cluster_set>
    mean_IF_wo_z/cluster_mean_IF_<cluster_set>

For each paired directory, it reads the per-cluster statistics CSVs produced by
`mean_IF_2x2_anova.py` and/or `mean_IF_2group_ttest.py`, extracts the relevant
contrast, and writes a master table showing whether z-scored and raw IF effects
are directionally concordant and whether each metric is significant.

Intended use from the f-gated_t-test_mean_IF directory:
    mean_IF_z_raw_audit.py \
        --root . \
        -o mean_IF_z_raw_audit.csv \
        --summary_out mean_IF_z_raw_audit_summary.csv

Default contrast extraction:
    AwP_v_AwS  -> AwP vs AwS pairwise comparison
    AnP_v_AnS  -> AnP vs AnS pairwise comparison
    AnS_v_AwS  -> AnS vs AwS two-group comparison, or State fallback if needed
    P_v_S      -> Drug main effect: Psilocin vs Saline

Classification:
    robust
        z significant, raw IF significant, same direction

    supported_direction
        z significant, raw IF same direction, raw IF not significant

    discordant_exclude_directional_claim
        z and raw IF opposite directions

    raw_only
        raw IF significant, z not significant, same direction

    concordant_nonsig
        same direction, neither metric significant

    incomplete_or_ambiguous
        missing result, missing direction, or tie/near-zero effect
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


DEFAULT_RESULT_PATTERNS = [
    "mean_IF_2x2_anova_results.csv",
    "mean_IF_2group_ttest_results.csv",
    "mean_IF_*ttest_results.csv",
    "*2group*results.csv",
    "*2x2*results.csv",
    "*anova_results.csv",
]

CONDITION_LABELS = {
    "AwS": "Awake Saline",
    "AwP": "Awake Psilocin",
    "AnS": "Anesthetized Saline",
    "AnP": "Anesthetized Psilocin",
    "Psilocin": "Psilocin",
    "Saline": "Saline",
    "Awake": "Awake",
    "Anesthetized": "Anesthetized",
}


@dataclass
class ContrastSpec:
    contrast_type: str  # pairwise, two_group, drug_main, state_main, unknown
    ref: str
    test: str
    label: str
    source: str


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Audit z-scored vs raw mean IF cluster result direction/significance."
    )
    p.add_argument(
        "--root", default=".",
        help="Root directory containing mean_IF_z and mean_IF_wo_z. Default: current directory."
    )
    p.add_argument(
        "--z_dir", default="mean_IF_z",
        help="Directory containing z-scored cluster result folders. Default: mean_IF_z"
    )
    p.add_argument(
        "--raw_dir", default="mean_IF_wo_z",
        help="Directory containing non-z/raw IF cluster result folders. Default: mean_IF_wo_z"
    )
    p.add_argument(
        "-o", "--out", default="mean_IF_z_raw_audit.csv",
        help="Master audit CSV. Default: mean_IF_z_raw_audit.csv"
    )
    p.add_argument(
        "--summary_out", default="mean_IF_z_raw_audit_summary.csv",
        help="Summary-count CSV. Default: mean_IF_z_raw_audit_summary.csv"
    )
    p.add_argument(
        "--p_cutoff", type=float, default=0.05,
        help="P-value cutoff for significance when boolean reject columns are absent. Default: 0.05"
    )
    p.add_argument(
        "--ttest_sig_col", default="auto",
        choices=["auto", "sig_holm_sidak", "sig_fdr_bh", "sig"],
        help=(
            "Which significance column to prefer for two-group outputs. "
            "auto = sig_holm_sidak if present, otherwise sig_fdr_bh, otherwise sig."
        ),
    )
    p.add_argument(
        "--quiet", action="store_true",
        help="Reduce terminal output."
    )
    return p.parse_args()


def safe_float(x) -> float:
    try:
        if pd.isna(x):
            return np.nan
        return float(x)
    except Exception:
        return np.nan


def p_to_sig(p: float) -> str:
    p = safe_float(p)
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


def sig_to_bool(sig: object) -> Optional[bool]:
    if sig is None or pd.isna(sig):
        return None
    s = str(sig).strip()
    if s == "":
        return None
    if s.lower() in {"n.s.", "ns", "n.s", "not significant", "false"}:
        return False
    if s in {"*", "**", "***", "****"}:
        return True
    return None


def significant_from(row: pd.Series, p_col: Optional[str], sig_col: Optional[str], p_cutoff: float) -> tuple[Optional[bool], float, str]:
    """Return significant?, p value, significance stars."""
    p = np.nan
    sig = ""

    if p_col and p_col in row.index:
        p = safe_float(row[p_col])
        if not pd.isna(p):
            sig = p_to_sig(p)
            return bool(p < p_cutoff), p, sig

    if sig_col and sig_col in row.index:
        sig = str(row[sig_col]) if not pd.isna(row[sig_col]) else ""
        sig_bool = sig_to_bool(sig)
        if sig_bool is not None:
            return sig_bool, p, sig

    return None, p, sig


def strip_metric_prefix(dirname: str) -> Optional[str]:
    for prefix in ["cluster_mean_z_", "cluster_mean_IF_"]:
        if dirname.startswith(prefix):
            return dirname[len(prefix):]
    return None


def cluster_set_sort_key(name: str) -> tuple:
    # Stable human-ish order: contrast, tstat number, q value, full name.
    tstat = re.search(r"tstat(\d+)", name)
    q = re.search(r"q([0-9.]+)", name)
    q_val = safe_float(q.group(1)) if q else np.nan
    return (
        name.split("_vox_")[0],
        int(tstat.group(1)) if tstat else 999,
        q_val if not pd.isna(q_val) else 999,
        name,
    )


def build_dir_map(base: Path, prefix: str) -> dict[str, Path]:
    out = {}
    if not base.exists():
        return out
    for p in base.iterdir():
        if not p.is_dir():
            continue
        key = strip_metric_prefix(p.name)
        if key is None:
            continue
        out[key] = p
    return out


def choose_result_csv(directory: Path, cluster_set: str = "") -> Optional[Path]:
    # For AnS_v_AwS directories, prefer the explicit two-group t-test output
    # over any older/accidental 2x2 ANOVA output that may also be present.
    if "AnS_v_AwS" in cluster_set:
        patterns = [
            "mean_IF_2group_ttest_results.csv",
            "mean_IF_*AnS*AwS*ttest_results.csv",
            "mean_IF_*AwS*AnS*ttest_results.csv",
            "mean_IF_*ttest_results.csv",
            "*2group*results.csv",
            "mean_IF_2x2_anova_results.csv",
            "*anova_results.csv",
        ]
    else:
        patterns = DEFAULT_RESULT_PATTERNS

    for pattern in patterns:
        matches = sorted(
            p for p in directory.glob(pattern)
            if p.is_file()
            and p.name.lower().endswith(".csv")
            and "raw_data" not in p.name.lower()
            and "audit" not in p.name.lower()
            and "summary" not in p.name.lower()
        )
        if matches:
            return matches[0]
    return None


def infer_contrast_spec(cluster_set: str, result_cols: set[str]) -> ContrastSpec:
    """Infer the biologically relevant comparison from the cluster-set name."""
    if "AwP_v_AwS" in cluster_set:
        return ContrastSpec("pairwise", ref="AwS", test="AwP", label="AwP_vs_AwS", source="dirname")
    if "AnP_v_AnS" in cluster_set:
        return ContrastSpec("pairwise", ref="AnS", test="AnP", label="AnP_vs_AnS", source="dirname")
    if "AnS_v_AwS" in cluster_set:
        # Prefer the explicit two-group output. If only a 2x2 output is present,
        # fall back to the State main effect, but mark this in `source`.
        if {"higher_mean", "p"}.issubset(result_cols):
            return ContrastSpec("two_group", ref="AwS", test="AnS", label="AnS_vs_AwS", source="dirname")
        return ContrastSpec("state_main", ref="Awake", test="Anesthetized", label="Anesthetized_vs_Awake", source="fallback_state_main")
    if "P_v_S" in cluster_set:
        return ContrastSpec("drug_main", ref="Saline", test="Psilocin", label="Psilocin_vs_Saline", source="dirname")
    return ContrastSpec("unknown", ref="", test="", label="unknown", source="unknown")


def expected_direction_from_name(cluster_set: str, spec: ContrastSpec) -> str:
    """Infer direction implied by tstat1/tstat2 in the cluster-set name."""
    if spec.contrast_type == "unknown":
        return ""
    if "tstat1" in cluster_set:
        return f"{spec.test}>{spec.ref}"
    if "tstat2" in cluster_set:
        return f"{spec.test}<{spec.ref}"
    return ""


def direction_from_higher(higher: object, ref: str, test: str) -> tuple[str, int]:
    if higher is None or pd.isna(higher):
        return "", 0
    h = str(higher).strip()
    if h == "" or h.lower() == "tie":
        return "tie", 0
    if h == test:
        return f"{test}>{ref}", 1
    if h == ref:
        return f"{test}<{ref}", -1
    # Handle State main effect labels even if ref/test are Awake/Anesthetized.
    if h == CONDITION_LABELS.get(test, ""):
        return f"{test}>{ref}", 1
    if h == CONDITION_LABELS.get(ref, ""):
        return f"{test}<{ref}", -1
    return f"higher={h}", 0


def direction_from_effect(effect: float, ref: str, test: str, atol: float = 1e-12) -> tuple[str, int]:
    effect = safe_float(effect)
    if pd.isna(effect):
        return "", 0
    if np.isclose(effect, 0, atol=atol):
        return "tie", 0
    return (f"{test}>{ref}", 1) if effect > 0 else (f"{test}<{ref}", -1)


def get_mean(row: pd.Series, cond: str) -> float:
    for col in [f"{cond}_mean_IF", f"{cond}_mean", f"{cond}_mean_z"]:
        if col in row.index:
            return safe_float(row[col])
    return np.nan


def extract_pairwise(row: pd.Series, spec: ContrastSpec, p_cutoff: float) -> dict:
    ref, test = spec.ref, spec.test
    prefix = f"{test}_vs_{ref}"

    p_col = f"{prefix}_p_holm_sidak" if f"{prefix}_p_holm_sidak" in row.index else f"{prefix}_p"
    sig_col = f"{prefix}_sig_holm_sidak" if f"{prefix}_sig_holm_sidak" in row.index else None
    higher_col = f"{prefix}_higher_mean"

    p_col = p_col if p_col in row.index else None
    higher = row[higher_col] if higher_col in row.index else None

    # Prefer explicit difference columns when present.
    effect_candidates = [
        f"{test}_minus_{ref}",
        f"{test}_diff_{test}_minus_{ref}",
    ]
    if test == "AwP" and ref == "AwS":
        effect_candidates.insert(0, "awake_diff_AwP_minus_AwS")
    if test == "AnP" and ref == "AnS":
        effect_candidates.insert(0, "anes_diff_AnP_minus_AnS")

    effect = np.nan
    for c in effect_candidates:
        if c in row.index:
            effect = safe_float(row[c])
            break

    if pd.isna(effect):
        mean_ref = get_mean(row, ref)
        mean_test = get_mean(row, test)
        if not pd.isna(mean_ref) and not pd.isna(mean_test):
            effect = mean_test - mean_ref
    else:
        mean_ref = get_mean(row, ref)
        mean_test = get_mean(row, test)

    direction, sign = direction_from_effect(effect, ref, test)
    if sign == 0:
        direction, sign = direction_from_higher(higher, ref, test)

    sig_bool, p, sig = significant_from(row, p_col=p_col, sig_col=sig_col, p_cutoff=p_cutoff)

    return {
        "analysis_type": "pairwise",
        "ref_group": ref,
        "test_group": test,
        "effect": effect,
        "direction": direction,
        "direction_sign": sign,
        "higher_mean": higher if higher is not None and not pd.isna(higher) else "",
        "p": p,
        "sig": sig,
        "significant": sig_bool,
        "p_column_used": p_col or "",
        "sig_column_used": sig_col or "",
        "ref_mean": mean_ref,
        "test_mean": mean_test,
    }


def choose_ttest_sig_cols(df_cols: set[str], ttest_sig_col: str) -> tuple[Optional[str], Optional[str]]:
    if ttest_sig_col == "sig_holm_sidak":
        return "p_holm_sidak", "sig_holm_sidak"
    if ttest_sig_col == "sig_fdr_bh":
        return "p_fdr_bh", "sig_fdr_bh"
    if ttest_sig_col == "sig":
        return "p", "sig"

    # auto
    if "p_holm_sidak" in df_cols or "sig_holm_sidak" in df_cols:
        return "p_holm_sidak", "sig_holm_sidak"
    if "p_fdr_bh" in df_cols or "sig_fdr_bh" in df_cols:
        return "p_fdr_bh", "sig_fdr_bh"
    return "p", "sig"


def extract_two_group(row: pd.Series, spec: ContrastSpec, p_cutoff: float, ttest_sig_col: str) -> dict:
    ref, test = spec.ref, spec.test
    p_col, sig_col = choose_ttest_sig_cols(set(row.index), ttest_sig_col)
    if p_col not in row.index:
        p_col = "p" if "p" in row.index else None
    if sig_col not in row.index:
        sig_col = "sig" if "sig" in row.index else None

    diff_col = f"{test}_minus_{ref}"
    effect = safe_float(row[diff_col]) if diff_col in row.index else np.nan
    if pd.isna(effect):
        mean_ref = get_mean(row, ref)
        mean_test = get_mean(row, test)
        if not pd.isna(mean_ref) and not pd.isna(mean_test):
            effect = mean_test - mean_ref
    else:
        mean_ref = get_mean(row, ref)
        mean_test = get_mean(row, test)

    direction, sign = direction_from_effect(effect, ref, test)
    higher = row["higher_mean"] if "higher_mean" in row.index else ""
    if sign == 0:
        direction, sign = direction_from_higher(higher, ref, test)

    sig_bool, p, sig = significant_from(row, p_col=p_col, sig_col=sig_col, p_cutoff=p_cutoff)

    return {
        "analysis_type": "two_group",
        "ref_group": ref,
        "test_group": test,
        "effect": effect,
        "direction": direction,
        "direction_sign": sign,
        "higher_mean": higher if not pd.isna(higher) else "",
        "p": p,
        "sig": sig,
        "significant": sig_bool,
        "p_column_used": p_col or "",
        "sig_column_used": sig_col or "",
        "ref_mean": mean_ref,
        "test_mean": mean_test,
    }


def extract_drug_main(row: pd.Series, spec: ContrastSpec, p_cutoff: float) -> dict:
    ref, test = spec.ref, spec.test
    p_col = "Drug_p" if "Drug_p" in row.index else None
    sig_col = "Drug_sig" if "Drug_sig" in row.index else None
    higher = row["Drug_higher_mean"] if "Drug_higher_mean" in row.index else ""

    # Estimate main-effect means from the condition means when available.
    saline_vals = [get_mean(row, "AwS"), get_mean(row, "AnS")]
    psilo_vals = [get_mean(row, "AwP"), get_mean(row, "AnP")]
    mean_ref = np.nanmean(saline_vals) if np.any(~pd.isna(saline_vals)) else np.nan
    mean_test = np.nanmean(psilo_vals) if np.any(~pd.isna(psilo_vals)) else np.nan
    effect = mean_test - mean_ref if not pd.isna(mean_ref) and not pd.isna(mean_test) else np.nan

    direction, sign = direction_from_effect(effect, ref, test)
    if sign == 0:
        direction, sign = direction_from_higher(higher, ref, test)

    sig_bool, p, sig = significant_from(row, p_col=p_col, sig_col=sig_col, p_cutoff=p_cutoff)

    return {
        "analysis_type": "drug_main",
        "ref_group": ref,
        "test_group": test,
        "effect": effect,
        "direction": direction,
        "direction_sign": sign,
        "higher_mean": higher if not pd.isna(higher) else "",
        "p": p,
        "sig": sig,
        "significant": sig_bool,
        "p_column_used": p_col or "",
        "sig_column_used": sig_col or "",
        "ref_mean": mean_ref,
        "test_mean": mean_test,
    }


def extract_state_main(row: pd.Series, spec: ContrastSpec, p_cutoff: float) -> dict:
    ref, test = spec.ref, spec.test
    p_col = "State_p" if "State_p" in row.index else None
    sig_col = "State_sig" if "State_sig" in row.index else None
    higher = row["State_higher_mean"] if "State_higher_mean" in row.index else ""

    awake_vals = [get_mean(row, "AwS"), get_mean(row, "AwP")]
    anes_vals = [get_mean(row, "AnS"), get_mean(row, "AnP")]
    mean_ref = np.nanmean(awake_vals) if np.any(~pd.isna(awake_vals)) else np.nan
    mean_test = np.nanmean(anes_vals) if np.any(~pd.isna(anes_vals)) else np.nan
    effect = mean_test - mean_ref if not pd.isna(mean_ref) and not pd.isna(mean_test) else np.nan

    direction, sign = direction_from_effect(effect, ref, test)
    if sign == 0:
        direction, sign = direction_from_higher(higher, ref, test)

    sig_bool, p, sig = significant_from(row, p_col=p_col, sig_col=sig_col, p_cutoff=p_cutoff)

    return {
        "analysis_type": "state_main",
        "ref_group": ref,
        "test_group": test,
        "effect": effect,
        "direction": direction,
        "direction_sign": sign,
        "higher_mean": higher if not pd.isna(higher) else "",
        "p": p,
        "sig": sig,
        "significant": sig_bool,
        "p_column_used": p_col or "",
        "sig_column_used": sig_col or "",
        "ref_mean": mean_ref,
        "test_mean": mean_test,
    }


def extract_metric_row(row: pd.Series, spec: ContrastSpec, p_cutoff: float, ttest_sig_col: str) -> dict:
    if spec.contrast_type == "pairwise":
        return extract_pairwise(row, spec, p_cutoff)
    if spec.contrast_type == "two_group":
        return extract_two_group(row, spec, p_cutoff, ttest_sig_col)
    if spec.contrast_type == "drug_main":
        return extract_drug_main(row, spec, p_cutoff)
    if spec.contrast_type == "state_main":
        return extract_state_main(row, spec, p_cutoff)
    return {
        "analysis_type": "unknown",
        "ref_group": spec.ref,
        "test_group": spec.test,
        "effect": np.nan,
        "direction": "",
        "direction_sign": 0,
        "higher_mean": "",
        "p": np.nan,
        "sig": "",
        "significant": None,
        "p_column_used": "",
        "sig_column_used": "",
        "ref_mean": np.nan,
        "test_mean": np.nan,
    }


def read_results(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "cluster_ID" not in df.columns:
        raise ValueError(f"{path} is missing cluster_ID")
    df = df.copy()
    df["cluster_ID"] = df["cluster_ID"].astype(str)
    return df


def classify(z: dict, raw: dict) -> tuple[str, str, bool]:
    """Return classification, concordance, include_in_main_directional_interpretation."""
    z_sign = int(z.get("direction_sign") or 0)
    raw_sign = int(raw.get("direction_sign") or 0)
    z_sig = z.get("significant")
    raw_sig = raw.get("significant")

    if z_sign == 0 or raw_sign == 0:
        return "incomplete_or_ambiguous", "missing_or_tie", False

    if z_sign != raw_sign:
        return "discordant_exclude_directional_claim", "opposite", False

    # Directionally concordant from here.
    if z_sig is True and raw_sig is True:
        return "robust", "same", True
    if z_sig is True and raw_sig is not True:
        return "supported_direction", "same", True
    if z_sig is not True and raw_sig is True:
        return "raw_only", "same", False
    if z_sig is False and raw_sig is False:
        return "concordant_nonsig", "same", False
    return "concordant_uncertain_significance", "same", False


def add_metric_prefix(metric: str, values: dict) -> dict:
    return {f"{metric}_{k}": v for k, v in values.items()}


def audit_pair(cluster_set: str, z_csv: Path, raw_csv: Path, args: argparse.Namespace) -> pd.DataFrame:
    z_df = read_results(z_csv)
    raw_df = read_results(raw_csv)

    # Infer separately then prefer z unless z is unknown.
    z_spec = infer_contrast_spec(cluster_set, set(z_df.columns))
    raw_spec = infer_contrast_spec(cluster_set, set(raw_df.columns))
    spec = z_spec if z_spec.contrast_type != "unknown" else raw_spec

    expected_direction = expected_direction_from_name(cluster_set, spec)

    z_by_cluster = z_df.set_index("cluster_ID", drop=False)
    raw_by_cluster = raw_df.set_index("cluster_ID", drop=False)
    cluster_ids = sorted(set(z_by_cluster.index) | set(raw_by_cluster.index), key=lambda x: (safe_float(x) if not pd.isna(safe_float(x)) else np.inf, str(x)))

    rows = []
    for cid in cluster_ids:
        base = {
            "cluster_set": cluster_set,
            "cluster_ID": cid,
            "contrast": spec.label,
            "contrast_type": spec.contrast_type,
            "contrast_source": spec.source,
            "expected_direction_from_cluster_name": expected_direction,
            "z_results_csv": str(z_csv),
            "raw_results_csv": str(raw_csv),
        }

        if cid in z_by_cluster.index:
            z_vals = extract_metric_row(z_by_cluster.loc[cid], spec, args.p_cutoff, args.ttest_sig_col)
        else:
            z_vals = extract_metric_row(pd.Series(dtype=object), spec, args.p_cutoff, args.ttest_sig_col)
            z_vals["analysis_type"] = "missing"

        if cid in raw_by_cluster.index:
            raw_vals = extract_metric_row(raw_by_cluster.loc[cid], spec, args.p_cutoff, args.ttest_sig_col)
        else:
            raw_vals = extract_metric_row(pd.Series(dtype=object), spec, args.p_cutoff, args.ttest_sig_col)
            raw_vals["analysis_type"] = "missing"

        validation_class, concordance, include_main = classify(z_vals, raw_vals)

        notes = []
        if z_vals.get("analysis_type") == "missing":
            notes.append("missing_z_cluster")
        if raw_vals.get("analysis_type") == "missing":
            notes.append("missing_raw_cluster")
        if spec.contrast_type == "state_main":
            notes.append("state_main_fallback_used")
        if validation_class == "discordant_exclude_directional_claim":
            notes.append("do_not_claim_true_directional_decrease_or_increase")
        if validation_class == "supported_direction":
            notes.append("z_significant_raw_direction_concordant_but_not_significant")

        out = {
            **base,
            **add_metric_prefix("z", z_vals),
            **add_metric_prefix("raw", raw_vals),
            "direction_concordance": concordance,
            "validation_class": validation_class,
            "include_in_main_directional_interpretation": include_main,
            "notes": ";".join(notes),
        }
        rows.append(out)

    return pd.DataFrame(rows)


def write_summary(audit: pd.DataFrame, summary_out: Path) -> pd.DataFrame:
    if audit.empty:
        summary = pd.DataFrame()
    else:
        summary = (
            audit
            .groupby(["cluster_set", "contrast", "validation_class"], dropna=False)
            .size()
            .reset_index(name="n_clusters")
            .sort_values(["cluster_set", "validation_class"])
        )
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_out, index=False)
    return summary


def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    z_base = root / args.z_dir
    raw_base = root / args.raw_dir

    z_dirs = build_dir_map(z_base, "cluster_mean_z_")
    raw_dirs = build_dir_map(raw_base, "cluster_mean_IF_")

    all_keys = sorted(set(z_dirs) | set(raw_dirs), key=cluster_set_sort_key)
    if not all_keys:
        raise FileNotFoundError(
            f"No cluster result directories found under {z_base} or {raw_base}."
        )

    pair_tables = []
    skipped = []

    for key in all_keys:
        z_dir = z_dirs.get(key)
        raw_dir = raw_dirs.get(key)
        if z_dir is None or raw_dir is None:
            skipped.append((key, "missing_z_dir" if z_dir is None else "missing_raw_dir"))
            continue

        z_csv = choose_result_csv(z_dir, key)
        raw_csv = choose_result_csv(raw_dir, key)
        if z_csv is None or raw_csv is None:
            reason = []
            if z_csv is None:
                reason.append("missing_z_results_csv")
            if raw_csv is None:
                reason.append("missing_raw_results_csv")
            skipped.append((key, ";".join(reason)))
            continue

        if not args.quiet:
            print(f"Auditing {key}")
            print(f"  z:   {z_csv.relative_to(root)}")
            print(f"  raw: {raw_csv.relative_to(root)}")

        pair_tables.append(audit_pair(key, z_csv, raw_csv, args))

    if pair_tables:
        audit = pd.concat(pair_tables, ignore_index=True)
    else:
        audit = pd.DataFrame()

    out = Path(args.out).expanduser()
    if not out.is_absolute():
        out = root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(out, index=False)

    summary_out = Path(args.summary_out).expanduser()
    if not summary_out.is_absolute():
        summary_out = root / summary_out
    summary = write_summary(audit, summary_out)

    if skipped:
        skipped_out = out.with_name(out.stem + "_skipped.csv")
        pd.DataFrame(skipped, columns=["cluster_set", "reason"]).to_csv(skipped_out, index=False)
    else:
        skipped_out = None

    print(f"Saved audit table: {out}")
    print(f"Saved summary table: {summary_out}")
    if skipped_out:
        print(f"Saved skipped-pairs table: {skipped_out}")
    if not summary.empty:
        print("\nSummary:")
        print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
