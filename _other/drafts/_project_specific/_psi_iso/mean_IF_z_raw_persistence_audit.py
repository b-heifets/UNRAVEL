#!/usr/bin/env python3
"""
Audit z-scored vs non-z-scored mean IF cluster results by biologically relevant contrast.

This script pairs matching cluster result directories under:
    mean_IF_z/cluster_mean_z_<cluster_set>
    mean_IF_wo_z/cluster_mean_IF_<cluster_set>

For each paired directory, it reads the per-cluster statistics CSVs produced by
`mean_IF_2x2_anova.py` and/or `mean_IF_2group_ttest.py`, extracts the relevant
contrast(s), and writes a master table showing whether z-scored and raw IF
effects are directionally concordant and whether each metric is significant.

Key behavior for this Psi/Iso f-gated workflow:
    AwP_v_AwS       -> AwP vs AwS pairwise comparison
    AnP_v_AnS       -> AnP vs AnS pairwise comparison
    AnS_v_AwS       -> AnS vs AwS two-group comparison, or State fallback
    P_v_S_overlap   -> AwP vs AwS AND AnP vs AnS pairwise comparisons
    P_v_S_conj      -> AwP vs AwS AND AnP vs AnS pairwise comparisons
    P_v_S otherwise -> AwP vs AwS AND AnP vs AnS pairwise comparisons by default

Why P_v_S is pairwise by default:
    In this workflow, P_v_S overlap/conjunction cluster sets represent shared
    state-specific effects, not just a collapsed Drug main effect. Therefore the
    audit should evaluate the Awake and Anesthetized psilocin-vs-saline effects
    separately, using the Holm-Sidak pairwise columns from the 2x2 ANOVA output.

Intended use from the f-gated_t-test_mean_IF directory:
    mean_IF_z_raw_contrast_audit.py \
        --root . \
        --ttest_sig_col sig \
        -o mean_IF_z_raw_contrast_audit.csv \
        --summary_out mean_IF_z_raw_contrast_audit_summary.csv \
        --persistence_out mean_IF_z_raw_persistence_audit.csv

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


@dataclass(frozen=True)
class ContrastSpec:
    contrast_type: str  # pairwise, two_group, drug_main, state_main, unknown
    ref: str
    test: str
    label: str
    source: str


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Audit z-scored vs raw mean IF cluster result direction/significance by contrast."
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
        "-o", "--out", default="mean_IF_z_raw_contrast_audit.csv",
        help="Master audit CSV. Default: mean_IF_z_raw_contrast_audit.csv"
    )
    p.add_argument(
        "--summary_out", default="mean_IF_z_raw_contrast_audit_summary.csv",
        help="Summary-count CSV. Default: mean_IF_z_raw_contrast_audit_summary.csv"
    )
    p.add_argument(
        "--persistence_out", default="mean_IF_z_raw_persistence_audit.csv",
        help=(
            "Optional awake-anchored aggregate CSV for P_v_S overlap/conjunction sets. "
            "Default: mean_IF_z_raw_persistence_audit.csv. Use '' to disable."
        ),
    )
    p.add_argument(
        "--shared_out", default=None,
        help=(
            "Deprecated alias for --persistence_out. If provided, writes the same "
            "awake-anchored persistence table to this path."
        ),
    )
    p.add_argument(
        "--p_cutoff", type=float, default=0.05,
        help="P-value cutoff for significance when boolean reject columns are absent. Default: 0.05"
    )
    p.add_argument(
        "--ttest_sig_col", default="sig",
        choices=["auto", "sig_holm_sidak", "sig_fdr_bh", "sig"],
        help=(
            "Which significance column to prefer for two-group outputs. "
            "Default: sig, i.e. raw/uncorrected t-test p significance. "
            "auto = sig_holm_sidak if present, otherwise sig_fdr_bh, otherwise sig."
        ),
    )
    p.add_argument(
        "--p_v_s_mode", default="state_pairwise",
        choices=["state_pairwise", "drug_main"],
        help=(
            "How to interpret P_v_S directories. Default: state_pairwise, which outputs "
            "AwP_vs_AwS and AnP_vs_AnS rows. drug_main uses Drug_p/Drug_sig instead."
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


def significant_from(
    row: pd.Series,
    p_col: Optional[str],
    sig_col: Optional[str],
    p_cutoff: float,
    prefer_sig_col: bool = False,
) -> tuple[Optional[bool], float, str]:
    """Return significant?, p value, significance stars.

    If prefer_sig_col is True, significance is taken from sig_col first and p is
    read only for reporting. This is useful when the user explicitly wants a
    specific significance-star column to control classification.
    """
    p = np.nan
    sig = ""

    if p_col and p_col in row.index:
        p = safe_float(row[p_col])

    if prefer_sig_col and sig_col and sig_col in row.index:
        sig = str(row[sig_col]) if not pd.isna(row[sig_col]) else ""
        sig_bool = sig_to_bool(sig)
        if sig_bool is not None:
            return sig_bool, p, sig

    if p_col and p_col in row.index and not pd.isna(p):
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
    tstat = re.search(r"tstat(\d+)", name)
    q = re.search(r"q([0-9.]+)", name)
    q_val = safe_float(q.group(1)) if q else np.nan
    return (
        name.split("_vox_")[0],
        int(tstat.group(1)) if tstat else 999,
        q_val if not pd.isna(q_val) else 999,
        name,
    )


def build_dir_map(base: Path) -> dict[str, Path]:
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


def cluster_source_type(cluster_set: str) -> str:
    s = cluster_set.lower()
    if "conj" in s:
        return "conjunction"
    if "overlap" in s:
        return "overlap"
    if "awp_v_aws" in s or "anp_v_ans" in s:
        return "state_specific_drug_effect"
    if "ans_v_aws" in s:
        return "state_or_baseline_effect"
    if "p_v_s" in s:
        return "psilocin_vs_saline_shared_or_main_effect"
    return "unknown"


def infer_contrast_specs(cluster_set: str, result_cols: set[str], p_v_s_mode: str) -> list[ContrastSpec]:
    """Infer the biologically relevant comparison(s) from the cluster-set name."""
    if "AwP_v_AwS" in cluster_set:
        return [ContrastSpec("pairwise", ref="AwS", test="AwP", label="AwP_vs_AwS", source="dirname")]
    if "AnP_v_AnS" in cluster_set:
        return [ContrastSpec("pairwise", ref="AnS", test="AnP", label="AnP_vs_AnS", source="dirname")]
    if "AnS_v_AwS" in cluster_set:
        if {"higher_mean", "p"}.issubset(result_cols):
            return [ContrastSpec("two_group", ref="AwS", test="AnS", label="AnS_vs_AwS", source="dirname")]
        return [ContrastSpec("state_main", ref="Awake", test="Anesthetized", label="Anesthetized_vs_Awake", source="fallback_state_main")]
    if "P_v_S" in cluster_set:
        if p_v_s_mode == "drug_main":
            return [ContrastSpec("drug_main", ref="Saline", test="Psilocin", label="Psilocin_vs_Saline", source="dirname_drug_main")]
        # P_v_S overlap/conjunction sets are shared state-specific psilocin effects,
        # so audit both state-specific pairwise contrasts separately.
        return [
            ContrastSpec("pairwise", ref="AwS", test="AwP", label="AwP_vs_AwS", source="dirname_p_v_s_state_pairwise"),
            ContrastSpec("pairwise", ref="AnS", test="AnP", label="AnP_vs_AnS", source="dirname_p_v_s_state_pairwise"),
        ]
    return [ContrastSpec("unknown", ref="", test="", label="unknown", source="unknown")]


def expected_direction_from_name(cluster_set: str, spec: ContrastSpec) -> tuple[str, int]:
    """Infer direction implied by tstat1/tstat2 in the cluster-set name."""
    if spec.contrast_type == "unknown":
        return "", 0
    if "tstat1" in cluster_set:
        return f"{spec.test}>{spec.ref}", 1
    if "tstat2" in cluster_set:
        return f"{spec.test}<{spec.ref}", -1
    return "", 0


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
    if h == CONDITION_LABELS.get(test, ""):
        return f"{test}>{ref}", 1
    if h == CONDITION_LABELS.get(ref, ""):
        return f"{test}<{ref}", -1
    # For drug/state main effects, higher can be Psilocin/Saline/Awake/Anesthetized.
    if test == "Psilocin" and h == "Psilocin":
        return f"{test}>{ref}", 1
    if ref == "Saline" and h == "Saline":
        return f"{test}<{ref}", -1
    if test == "Anesthetized" and h == "Anesthetized":
        return f"{test}>{ref}", 1
    if ref == "Awake" and h == "Awake":
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

    # For 2x2 outputs, use Holm-Sidak pairwise columns when present.
    p_col = f"{prefix}_p_holm_sidak" if f"{prefix}_p_holm_sidak" in row.index else f"{prefix}_p"
    sig_col = f"{prefix}_sig_holm_sidak" if f"{prefix}_sig_holm_sidak" in row.index else None
    higher_col = f"{prefix}_higher_mean"

    p_col = p_col if p_col in row.index else None
    higher = row[higher_col] if higher_col in row.index else None

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

    mean_ref = get_mean(row, ref)
    mean_test = get_mean(row, test)
    if pd.isna(effect) and not pd.isna(mean_ref) and not pd.isna(mean_test):
        effect = mean_test - mean_ref

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


def choose_ttest_sig_cols(df_cols: set[str], ttest_sig_col: str) -> tuple[Optional[str], Optional[str], bool]:
    if ttest_sig_col == "sig_holm_sidak":
        return "p_holm_sidak", "sig_holm_sidak", True
    if ttest_sig_col == "sig_fdr_bh":
        return "p_fdr_bh", "sig_fdr_bh", True
    if ttest_sig_col == "sig":
        return "p", "sig", True

    # auto
    if "p_holm_sidak" in df_cols or "sig_holm_sidak" in df_cols:
        return "p_holm_sidak", "sig_holm_sidak", True
    if "p_fdr_bh" in df_cols or "sig_fdr_bh" in df_cols:
        return "p_fdr_bh", "sig_fdr_bh", True
    return "p", "sig", True


def extract_two_group(row: pd.Series, spec: ContrastSpec, p_cutoff: float, ttest_sig_col: str) -> dict:
    ref, test = spec.ref, spec.test
    p_col, sig_col, prefer_sig_col = choose_ttest_sig_cols(set(row.index), ttest_sig_col)
    if p_col not in row.index:
        p_col = "p" if "p" in row.index else None
    if sig_col not in row.index:
        sig_col = "sig" if "sig" in row.index else None

    diff_col = f"{test}_minus_{ref}"
    effect = safe_float(row[diff_col]) if diff_col in row.index else np.nan
    mean_ref = get_mean(row, ref)
    mean_test = get_mean(row, test)
    if pd.isna(effect) and not pd.isna(mean_ref) and not pd.isna(mean_test):
        effect = mean_test - mean_ref

    direction, sign = direction_from_effect(effect, ref, test)
    higher = row["higher_mean"] if "higher_mean" in row.index else ""
    if sign == 0:
        direction, sign = direction_from_higher(higher, ref, test)

    sig_bool, p, sig = significant_from(
        row, p_col=p_col, sig_col=sig_col, p_cutoff=p_cutoff, prefer_sig_col=prefer_sig_col
    )

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

    # Infer from the z table first, but results should be equivalent for raw.
    specs = infer_contrast_specs(cluster_set, set(z_df.columns), args.p_v_s_mode)
    if len(specs) == 1 and specs[0].contrast_type == "unknown":
        specs = infer_contrast_specs(cluster_set, set(raw_df.columns), args.p_v_s_mode)

    z_by_cluster = z_df.set_index("cluster_ID", drop=False)
    raw_by_cluster = raw_df.set_index("cluster_ID", drop=False)
    cluster_ids = sorted(
        set(z_by_cluster.index) | set(raw_by_cluster.index),
        key=lambda x: (safe_float(x) if not pd.isna(safe_float(x)) else np.inf, str(x)),
    )

    rows = []
    for spec in specs:
        expected_direction, expected_sign = expected_direction_from_name(cluster_set, spec)
        for cid in cluster_ids:
            base = {
                "cluster_set": cluster_set,
                "cluster_source_type": cluster_source_type(cluster_set),
                "cluster_ID": cid,
                "contrast": spec.label,
                "contrast_type": spec.contrast_type,
                "contrast_source": spec.source,
                "expected_direction_from_cluster_name": expected_direction,
                "expected_direction_sign": expected_sign,
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

            z_matches_expected = (
                bool(expected_sign and z_vals.get("direction_sign") == expected_sign)
                if z_vals.get("direction_sign") not in [None, 0]
                else False
            )
            raw_matches_expected = (
                bool(expected_sign and raw_vals.get("direction_sign") == expected_sign)
                if raw_vals.get("direction_sign") not in [None, 0]
                else False
            )

            notes = []
            if z_vals.get("analysis_type") == "missing":
                notes.append("missing_z_cluster")
            if raw_vals.get("analysis_type") == "missing":
                notes.append("missing_raw_cluster")
            if spec.contrast_type == "state_main":
                notes.append("state_main_fallback_used")
            if spec.source == "dirname_p_v_s_state_pairwise":
                notes.append("p_v_s_audited_as_state_specific_pairwise_effect")
            if validation_class == "discordant_exclude_directional_claim":
                notes.append("do_not_claim_true_directional_decrease_or_increase")
            if validation_class == "supported_direction":
                notes.append("z_significant_raw_direction_concordant_but_not_significant")
            if expected_sign and not z_matches_expected:
                notes.append("z_direction_does_not_match_cluster_tstat_direction")
            if expected_sign and not raw_matches_expected:
                notes.append("raw_direction_does_not_match_cluster_tstat_direction")

            out = {
                **base,
                **add_metric_prefix("z", z_vals),
                **add_metric_prefix("raw", raw_vals),
                "z_matches_expected_direction": z_matches_expected,
                "raw_matches_expected_direction": raw_matches_expected,
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
            .sort_values(["cluster_set", "contrast", "validation_class"])
        )
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_out, index=False)
    return summary


def _get_single_contrast_row(group: pd.DataFrame, contrast: str) -> Optional[pd.Series]:
    rows = group[group["contrast"].astype(str).eq(contrast)]
    if rows.empty:
        return None
    return rows.iloc[0]


def _bool_value(x) -> bool:
    try:
        return bool(x)
    except Exception:
        return False


def _safe_abs_ratio(numer, denom) -> float:
    numer = safe_float(numer)
    denom = safe_float(denom)
    if pd.isna(numer) or pd.isna(denom) or np.isclose(denom, 0):
        return np.nan
    return abs(numer) / abs(denom)


def persistence_effect_class(group: pd.DataFrame) -> str:
    """Awake-anchored aggregate class for one P_v_S overlap/conjunction cluster.

    The awake psilocin effect (AwP_vs_AwS) is the anchor. The anesthetized
    psilocin effect (AnP_vs_AnS) is interpreted as persistence/preservation of
    that awake effect. Raw IF discordance blocks strong directional claims.
    """
    awake = _get_single_contrast_row(group, "AwP_vs_AwS")
    anes = _get_single_contrast_row(group, "AnP_vs_AnS")

    if awake is None or anes is None:
        return "persistence_incomplete_missing_state_contrast"

    awake_class = str(awake.get("validation_class", ""))
    anes_class = str(anes.get("validation_class", ""))

    if awake_class == "discordant_exclude_directional_claim":
        return "awake_anchor_discordant_exclude_directional_claim"
    if anes_class == "discordant_exclude_directional_claim":
        return "persistent_discordant_raw_exclude_or_review"

    expected_sign = int(awake.get("expected_direction_sign") or 0)
    awake_z_sign = int(awake.get("z_direction_sign") or 0)
    anes_z_sign = int(anes.get("z_direction_sign") or 0)
    awake_raw_sign = int(awake.get("raw_direction_sign") or 0)
    anes_raw_sign = int(anes.get("raw_direction_sign") or 0)

    # For tstat1/tstat2-defined clusters, require the awake anchor to match the
    # direction implied by the cluster set before calling persistence.
    if expected_sign and awake_z_sign and awake_z_sign != expected_sign:
        return "awake_anchor_unexpected_z_direction_review"
    if expected_sign and awake_raw_sign and awake_raw_sign != expected_sign:
        return "awake_anchor_unexpected_raw_direction_review"

    awake_supported = _bool_value(awake.get("include_in_main_directional_interpretation"))
    anes_supported = _bool_value(anes.get("include_in_main_directional_interpretation"))

    if not awake_supported:
        if awake_class == "raw_only":
            return "awake_anchor_raw_only_z_not_significant_review"
        return "awake_anchor_not_supported"

    # At this point the awake effect is supported and directionally interpretable.
    if expected_sign and anes_z_sign and anes_z_sign != expected_sign:
        return "awake_effect_not_preserved_reversed_under_anesthesia"
    if expected_sign and anes_raw_sign and anes_raw_sign != expected_sign:
        return "awake_effect_not_preserved_raw_opposite_under_anesthesia"

    if anes_supported:
        if awake_class == "robust" and anes_class == "robust":
            return "persistent_robust"
        return "persistent_supported"

    if anes_class == "raw_only":
        return "persistence_raw_only_under_anesthesia_review"
    if anes_class in {"concordant_nonsig", "concordant_uncertain_significance"}:
        return "persistent_direction_concordant_but_not_significant_under_anesthesia"
    if anes_class == "incomplete_or_ambiguous":
        return "persistence_under_anesthesia_incomplete_or_ambiguous"

    return "awake_effect_not_clearly_preserved_under_anesthesia"


def write_persistence_summary(audit: pd.DataFrame, persistence_out: Path) -> pd.DataFrame:
    """Write an awake-anchored persistence table for P_v_S overlap/conjunction sets."""
    if audit.empty:
        persistence = pd.DataFrame()
    else:
        mask = (
            audit["cluster_set"].str.contains("P_v_S", na=False)
            & audit["contrast_source"].eq("dirname_p_v_s_state_pairwise")
        )
        rows = audit[mask].copy()
        if rows.empty:
            persistence = pd.DataFrame()
        else:
            pieces = []
            for (cluster_set, cluster_id), g in rows.groupby(["cluster_set", "cluster_ID"], dropna=False):
                g = g.sort_values("contrast")
                awake = _get_single_contrast_row(g, "AwP_vs_AwS")
                anes = _get_single_contrast_row(g, "AnP_vs_AnS")

                piece = {
                    "cluster_set": cluster_set,
                    "cluster_source_type": g["cluster_source_type"].iloc[0],
                    "cluster_ID": cluster_id,
                    "expected_direction_from_cluster_name": g["expected_direction_from_cluster_name"].dropna().iloc[0] if not g["expected_direction_from_cluster_name"].dropna().empty else "",
                    "expected_direction_sign": g["expected_direction_sign"].dropna().iloc[0] if not g["expected_direction_sign"].dropna().empty else 0,
                    "persistence_class": persistence_effect_class(g),
                    "n_state_pairwise_contrasts": g["contrast"].nunique(),
                    "n_include_in_main_directional_interpretation": int(g["include_in_main_directional_interpretation"].fillna(False).sum()),
                    "contrast_classes": ";".join(f"{r.contrast}:{r.validation_class}" for r in g.itertuples()),
                    "z_directions": ";".join(f"{r.contrast}:{r.z_direction}" for r in g.itertuples()),
                    "raw_directions": ";".join(f"{r.contrast}:{r.raw_direction}" for r in g.itertuples()),
                    "z_sigs": ";".join(f"{r.contrast}:{r.z_sig}" for r in g.itertuples()),
                    "raw_sigs": ";".join(f"{r.contrast}:{r.raw_sig}" for r in g.itertuples()),
                }

                if awake is not None:
                    piece.update({
                        "awake_validation_class": awake.get("validation_class", ""),
                        "awake_z_direction": awake.get("z_direction", ""),
                        "awake_z_sig": awake.get("z_sig", ""),
                        "awake_z_p": awake.get("z_p", np.nan),
                        "awake_z_effect": awake.get("z_effect", np.nan),
                        "awake_raw_direction": awake.get("raw_direction", ""),
                        "awake_raw_sig": awake.get("raw_sig", ""),
                        "awake_raw_p": awake.get("raw_p", np.nan),
                        "awake_raw_effect": awake.get("raw_effect", np.nan),
                        "awake_include": awake.get("include_in_main_directional_interpretation", False),
                    })
                if anes is not None:
                    piece.update({
                        "anes_validation_class": anes.get("validation_class", ""),
                        "anes_z_direction": anes.get("z_direction", ""),
                        "anes_z_sig": anes.get("z_sig", ""),
                        "anes_z_p": anes.get("z_p", np.nan),
                        "anes_z_effect": anes.get("z_effect", np.nan),
                        "anes_raw_direction": anes.get("raw_direction", ""),
                        "anes_raw_sig": anes.get("raw_sig", ""),
                        "anes_raw_p": anes.get("raw_p", np.nan),
                        "anes_raw_effect": anes.get("raw_effect", np.nan),
                        "anes_include": anes.get("include_in_main_directional_interpretation", False),
                    })

                piece["anes_to_awake_abs_z_effect_ratio"] = _safe_abs_ratio(
                    piece.get("anes_z_effect", np.nan), piece.get("awake_z_effect", np.nan)
                )
                piece["anes_to_awake_abs_raw_effect_ratio"] = _safe_abs_ratio(
                    piece.get("anes_raw_effect", np.nan), piece.get("awake_raw_effect", np.nan)
                )

                pieces.append(piece)

            persistence = pd.DataFrame(pieces).sort_values(["cluster_set", "persistence_class", "cluster_ID"])

    persistence_out.parent.mkdir(parents=True, exist_ok=True)
    persistence.to_csv(persistence_out, index=False)
    return persistence


def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    z_base = root / args.z_dir
    raw_base = root / args.raw_dir

    z_dirs = build_dir_map(z_base)
    raw_dirs = build_dir_map(raw_base)

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

    audit = pd.concat(pair_tables, ignore_index=True) if pair_tables else pd.DataFrame()

    out = Path(args.out).expanduser()
    if not out.is_absolute():
        out = root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(out, index=False)

    summary_out = Path(args.summary_out).expanduser()
    if not summary_out.is_absolute():
        summary_out = root / summary_out
    summary = write_summary(audit, summary_out)

    persistence = pd.DataFrame()
    persistence_out_arg = args.shared_out if args.shared_out is not None else args.persistence_out
    persistence_out_path = None
    if persistence_out_arg:
        persistence_out_path = Path(persistence_out_arg).expanduser()
        if not persistence_out_path.is_absolute():
            persistence_out_path = root / persistence_out_path
        persistence = write_persistence_summary(audit, persistence_out_path)

    if skipped:
        skipped_out = out.with_name(out.stem + "_skipped.csv")
        pd.DataFrame(skipped, columns=["cluster_set", "reason"]).to_csv(skipped_out, index=False)
    else:
        skipped_out = None

    print(f"Saved audit table: {out}")
    print(f"Saved summary table: {summary_out}")
    if persistence_out_path is not None:
        print(f"Saved awake-anchored persistence table: {persistence_out_path}")
    if skipped_out:
        print(f"Saved skipped-pairs table: {skipped_out}")
    if not summary.empty:
        print("\nSummary:")
        print(summary.to_string(index=False))
    if not persistence.empty and not args.quiet:
        print("\nAwake-anchored P_v_S persistence summary:")
        print(
            persistence.groupby(["cluster_set", "persistence_class"], dropna=False)
            .size()
            .reset_index(name="n_clusters")
            .to_string(index=False)
        )


if __name__ == "__main__":
    main()
