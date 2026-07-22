#!/usr/bin/env python3
"""
Audit effect direction in z-scored versus non-z-scored mean IF results.

This script pairs matching cluster-result directories under:
    mean_IF_z/cluster_mean_z_<cluster_set>
    mean_IF_wo_z/cluster_mean_IF_<cluster_set>

For each paired directory, it reads the full per-cluster statistics CSV produced
by `mean_IF_2x2_anova.py` or `mean_IF_2group_ttest.py`. It then compares the
sign of the biologically relevant effect in the z-scored and non-z-scored data.
For 2x2 results, Holm-Sidak reject columns are preferred over recomputing
significance from corrected p-values.

The audit also checks whether each measured direction agrees with the direction
implied by tstat1/tstat2 in the cluster-set directory name.

Default contrast extraction:
    AwP_v_AwS  -> AwP vs AwS
    AnP_v_AnS  -> AnP vs AnS
    AnS_v_AwS  -> AnS vs AwS
    P_v_S      -> Psilocin vs Saline main effect

For AnS_v_AwS, a dedicated two-group result is preferred. If only a 2x2 result
is available, direction is calculated from the exact AnS and AwS condition
means; the State main effect is not substituted because it is a different
contrast. Significance is left unknown unless a direct pairwise test is present.

Classification:
    robust
        z significant, raw IF significant, same direction

    supported_direction
        z significant, raw IF same direction, raw IF not significant or unknown

    discordant_exclude_directional_claim
        z and raw IF have opposite directions

    raw_only
        raw IF significant, z not significant or unknown, same direction

    concordant_nonsig
        same direction, neither metric significant

    incomplete_or_ambiguous
        missing result, missing direction, or tie/near-zero effect

Example from the mean_IF directory:
    mean_IF_z_raw_audit.py -r .
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SM, SuppressMetavar
from unravel.core.utils import log_command, verbose_end_msg, verbose_start_msg


Z_DIR_PREFIX = "cluster_mean_z_"
RAW_DIR_PREFIX = "cluster_mean_IF_"

DEFAULT_RESULT_PATTERNS = [
    "mean_IF_2x2_anova_results.csv",
    "mean_IF_2group_ttest_results.csv",
    "mean_IF_*ttest_results.csv",
    "*2group*results.csv",
    "*2x2*results.csv",
    "*anova_results.csv",
]

EXCLUDED_RESULT_NAME_PARTS = {
    "raw_data",
    "audit",
    "summary",
    "concise",
    "skipped",
}

CONDITION_LABELS = {
    "AwS": "Awake Saline",
    "AwP": "Awake Psilocin",
    "AnS": "Anesthetized Saline",
    "AnP": "Anesthetized Psilocin",
    "Psilocin": "Psilocin",
    "Saline": "Saline",
}


@dataclass(frozen=True)
class ContrastSpec:
    contrast_type: str  # pairwise, two_group, drug_main, unknown
    ref: str
    test: str
    label: str
    source: str


def parse_args():
    parser = RichArgumentParser(
        formatter_class=SuppressMetavar,
        add_help=False,
        docstring=__doc__,
    )

    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument(
        "-r",
        "--root",
        default=".",
        help=(
            "Root directory containing mean_IF_z and mean_IF_wo_z. "
            "Default: current directory"
        ),
        action=SM,
    )
    opts.add_argument(
        "-z",
        "--z_dir",
        default="mean_IF_z",
        help="Directory containing z-scored result folders. Default: mean_IF_z",
        action=SM,
    )
    opts.add_argument(
        "-nz",
        "--raw_dir",
        default="mean_IF_wo_z",
        help=(
            "Directory containing non-z-scored result folders. "
            "Default: mean_IF_wo_z"
        ),
        action=SM,
    )
    opts.add_argument(
        "-o",
        "--out",
        default="mean_IF_z_raw_audit.csv",
        help="Detailed audit CSV. Default: mean_IF_z_raw_audit.csv",
        action=SM,
    )
    opts.add_argument(
        "-so",
        "--summary_out",
        default="mean_IF_z_raw_audit_summary.csv",
        help="Summary-count CSV. Default: mean_IF_z_raw_audit_summary.csv",
        action=SM,
    )
    opts.add_argument(
        "-p",
        "--p_cutoff",
        type=float,
        default=0.05,
        help=(
            "P-value cutoff used only when an explicit reject column is absent. "
            "Default: 0.05"
        ),
        action=SM,
    )
    opts.add_argument(
        "-ts",
        "--ttest_sig_col",
        default="auto",
        choices=["auto", "sig_holm_sidak", "sig_fdr_bh", "sig"],
        help=(
            "Significance result to prefer for two-group outputs. "
            "Default: auto"
        ),
        action=SM,
    )
    opts.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    return parser.parse_args()


def safe_float(value) -> float:
    try:
        if pd.isna(value):
            return np.nan
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def p_to_sig(p_value: float) -> str:
    p_value = safe_float(p_value)
    if pd.isna(p_value):
        return ""
    if p_value < 0.0001:
        return "****"
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < 0.05:
        return "*"
    return "n.s."


def value_to_bool(value) -> Optional[bool]:
    """Convert common CSV boolean encodings to True, False, or None."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        if value == 1:
            return True
        if value == 0:
            return False

    text = str(value).strip().lower()
    if text in {"true", "t", "yes", "y", "1"}:
        return True
    if text in {"false", "f", "no", "n", "0"}:
        return False
    return None


def sig_to_bool(sig: object) -> Optional[bool]:
    if sig is None or pd.isna(sig):
        return None
    text = str(sig).strip()
    if not text:
        return None
    if text.lower() in {"n.s.", "ns", "n.s", "not significant", "false"}:
        return False
    if text in {"*", "**", "***", "****"}:
        return True
    return None


def significant_from(
    row: pd.Series,
    reject_col: Optional[str],
    p_col: Optional[str],
    sig_col: Optional[str],
    p_cutoff: float,
) -> tuple[Optional[bool], float, str]:
    """Return significance decision, p-value, and significance stars."""
    p_value = np.nan
    if p_col and p_col in row.index:
        p_value = safe_float(row[p_col])

    sig = ""
    if sig_col and sig_col in row.index and not pd.isna(row[sig_col]):
        sig = str(row[sig_col])
    elif not pd.isna(p_value):
        sig = p_to_sig(p_value)

    # The source analysis owns the multiple-comparison decision. Prefer its
    # explicit reject column when available.
    if reject_col and reject_col in row.index:
        reject = value_to_bool(row[reject_col])
        if reject is not None:
            return reject, p_value, sig

    if not pd.isna(p_value):
        return bool(p_value < p_cutoff), p_value, sig

    sig_bool = sig_to_bool(sig)
    if sig_bool is not None:
        return sig_bool, p_value, sig

    return None, p_value, sig


def cluster_set_sort_key(name: str) -> tuple:
    """Provide a stable order by contrast, t-stat image, q value, and name."""
    tstat = re.search(r"tstat(\d+)", name)
    q_match = re.search(r"q([0-9.]+)", name)
    q_value = safe_float(q_match.group(1)) if q_match else np.nan
    return (
        name.split("_vox_")[0],
        int(tstat.group(1)) if tstat else 999,
        q_value if not pd.isna(q_value) else 999,
        name,
    )


def build_dir_map(base: Path, prefix: str) -> dict[str, Path]:
    """Map the suffix after the expected metric-specific directory prefix."""
    if not base.exists():
        return {}

    out = {}
    for path in base.iterdir():
        if path.is_dir() and path.name.startswith(prefix):
            out[path.name[len(prefix):]] = path
    return out


def is_candidate_result_csv(path: Path) -> bool:
    name = path.name.lower()
    return (
        path.is_file()
        and path.suffix.lower() == ".csv"
        and not any(part in name for part in EXCLUDED_RESULT_NAME_PARTS)
    )


def choose_result_csv(directory: Path, cluster_set: str = "") -> Optional[Path]:
    """Choose a full results CSV, never the renamed concise output."""
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
            path for path in directory.glob(pattern)
            if is_candidate_result_csv(path)
        )
        if matches:
            return matches[0]
    return None


def has_condition_means(result_cols: set[str], *conditions: str) -> bool:
    for condition in conditions:
        candidates = {
            f"{condition}_mean_IF",
            f"{condition}_mean",
            f"{condition}_mean_z",
        }
        if not candidates.intersection(result_cols):
            return False
    return True


def infer_contrast_spec(cluster_set: str, result_cols: set[str]) -> ContrastSpec:
    """Infer the exact contrast and the available extraction method."""
    if "AwP_v_AwS" in cluster_set:
        return ContrastSpec(
            "pairwise", "AwS", "AwP", "AwP_vs_AwS", "directory_name"
        )
    if "AnP_v_AnS" in cluster_set:
        return ContrastSpec(
            "pairwise", "AnS", "AnP", "AnP_vs_AnS", "directory_name"
        )
    if "AnS_v_AwS" in cluster_set:
        if {"higher_mean", "p"}.issubset(result_cols):
            return ContrastSpec(
                "two_group", "AwS", "AnS", "AnS_vs_AwS", "two_group_result"
            )
        if has_condition_means(result_cols, "AwS", "AnS"):
            return ContrastSpec(
                "pairwise",
                "AwS",
                "AnS",
                "AnS_vs_AwS",
                "condition_means_no_direct_test",
            )
        return ContrastSpec("unknown", "AwS", "AnS", "AnS_vs_AwS", "unknown")
    if "P_v_S" in cluster_set:
        return ContrastSpec(
            "drug_main", "Saline", "Psilocin", "Psilocin_vs_Saline", "directory_name"
        )
    return ContrastSpec("unknown", "", "", "unknown", "unknown")


def choose_base_spec(z_spec: ContrastSpec, raw_spec: ContrastSpec) -> ContrastSpec:
    if z_spec.contrast_type != "unknown":
        return z_spec
    return raw_spec


def expected_direction_from_name(cluster_set: str, spec: ContrastSpec) -> str:
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

    value = str(higher).strip()
    if not value or value.lower() == "tie":
        return "tie", 0
    if value in {test, CONDITION_LABELS.get(test, "")}:
        return f"{test}>{ref}", 1
    if value in {ref, CONDITION_LABELS.get(ref, "")}:
        return f"{test}<{ref}", -1
    return f"higher={value}", 0


def direction_from_effect(
    effect: float,
    ref: str,
    test: str,
    atol: float = 1e-12,
) -> tuple[str, int]:
    effect = safe_float(effect)
    if pd.isna(effect):
        return "", 0
    if np.isclose(effect, 0, atol=atol):
        return "tie", 0
    if effect > 0:
        return f"{test}>{ref}", 1
    return f"{test}<{ref}", -1


def get_mean(row: pd.Series, condition: str) -> float:
    for col in (
        f"{condition}_mean_IF",
        f"{condition}_mean",
        f"{condition}_mean_z",
    ):
        if col in row.index:
            return safe_float(row[col])
    return np.nan


def extract_pairwise(
    row: pd.Series,
    spec: ContrastSpec,
    p_cutoff: float,
) -> dict:
    ref, test = spec.ref, spec.test
    prefix = f"{test}_vs_{ref}"

    reject_col = (
        f"{prefix}_reject_holm_sidak"
        if f"{prefix}_reject_holm_sidak" in row.index
        else None
    )
    p_col = (
        f"{prefix}_p_holm_sidak"
        if f"{prefix}_p_holm_sidak" in row.index
        else f"{prefix}_p"
    )
    p_col = p_col if p_col in row.index else None
    sig_col = (
        f"{prefix}_sig_holm_sidak"
        if f"{prefix}_sig_holm_sidak" in row.index
        else None
    )
    higher_col = f"{prefix}_higher_mean"
    higher = row[higher_col] if higher_col in row.index else None

    effect_candidates = [
        f"{test}_minus_{ref}",
        f"{test}_diff_{test}_minus_{ref}",
    ]
    if test == "AwP" and ref == "AwS":
        effect_candidates.insert(0, "awake_diff_AwP_minus_AwS")
    elif test == "AnP" and ref == "AnS":
        effect_candidates.insert(0, "anes_diff_AnP_minus_AnS")

    effect = np.nan
    for col in effect_candidates:
        if col in row.index:
            effect = safe_float(row[col])
            break

    mean_ref = get_mean(row, ref)
    mean_test = get_mean(row, test)
    if pd.isna(effect) and not pd.isna(mean_ref) and not pd.isna(mean_test):
        effect = mean_test - mean_ref

    direction, sign = direction_from_effect(effect, ref, test)
    if sign == 0:
        direction, sign = direction_from_higher(higher, ref, test)

    significant, p_value, sig = significant_from(
        row,
        reject_col=reject_col,
        p_col=p_col,
        sig_col=sig_col,
        p_cutoff=p_cutoff,
    )

    return {
        "analysis_type": "pairwise",
        "contrast_source": spec.source,
        "ref_group": ref,
        "test_group": test,
        "effect": effect,
        "direction": direction,
        "direction_sign": sign,
        "higher_mean": higher if higher is not None and not pd.isna(higher) else "",
        "p": p_value,
        "sig": sig,
        "significant": significant,
        "reject_column_used": reject_col or "",
        "p_column_used": p_col or "",
        "sig_column_used": sig_col or "",
        "ref_mean": mean_ref,
        "test_mean": mean_test,
    }


def choose_ttest_sig_cols(
    df_cols: set[str],
    ttest_sig_col: str,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    if ttest_sig_col == "sig_holm_sidak":
        return "reject_holm_sidak", "p_holm_sidak", "sig_holm_sidak"
    if ttest_sig_col == "sig_fdr_bh":
        return "reject_fdr_bh", "p_fdr_bh", "sig_fdr_bh"
    if ttest_sig_col == "sig":
        return "reject", "p", "sig"

    if "reject_holm_sidak" in df_cols or "p_holm_sidak" in df_cols:
        return "reject_holm_sidak", "p_holm_sidak", "sig_holm_sidak"
    if "reject_fdr_bh" in df_cols or "p_fdr_bh" in df_cols:
        return "reject_fdr_bh", "p_fdr_bh", "sig_fdr_bh"
    return "reject", "p", "sig"


def extract_two_group(
    row: pd.Series,
    spec: ContrastSpec,
    p_cutoff: float,
    ttest_sig_col: str,
) -> dict:
    ref, test = spec.ref, spec.test
    reject_col, p_col, sig_col = choose_ttest_sig_cols(
        set(row.index),
        ttest_sig_col,
    )

    reject_col = reject_col if reject_col in row.index else None
    p_col = p_col if p_col in row.index else ("p" if "p" in row.index else None)
    sig_col = (
        sig_col if sig_col in row.index else ("sig" if "sig" in row.index else None)
    )

    diff_col = f"{test}_minus_{ref}"
    effect = safe_float(row[diff_col]) if diff_col in row.index else np.nan
    mean_ref = get_mean(row, ref)
    mean_test = get_mean(row, test)
    if pd.isna(effect) and not pd.isna(mean_ref) and not pd.isna(mean_test):
        effect = mean_test - mean_ref

    higher = row["higher_mean"] if "higher_mean" in row.index else ""
    direction, sign = direction_from_effect(effect, ref, test)
    if sign == 0:
        direction, sign = direction_from_higher(higher, ref, test)

    significant, p_value, sig = significant_from(
        row,
        reject_col=reject_col,
        p_col=p_col,
        sig_col=sig_col,
        p_cutoff=p_cutoff,
    )

    return {
        "analysis_type": "two_group",
        "contrast_source": spec.source,
        "ref_group": ref,
        "test_group": test,
        "effect": effect,
        "direction": direction,
        "direction_sign": sign,
        "higher_mean": higher if not pd.isna(higher) else "",
        "p": p_value,
        "sig": sig,
        "significant": significant,
        "reject_column_used": reject_col or "",
        "p_column_used": p_col or "",
        "sig_column_used": sig_col or "",
        "ref_mean": mean_ref,
        "test_mean": mean_test,
    }


def extract_drug_main(
    row: pd.Series,
    spec: ContrastSpec,
    p_cutoff: float,
) -> dict:
    ref, test = spec.ref, spec.test
    p_col = "Drug_p" if "Drug_p" in row.index else None
    sig_col = "Drug_sig" if "Drug_sig" in row.index else None
    higher = row["Drug_higher_mean"] if "Drug_higher_mean" in row.index else ""

    saline_values = [get_mean(row, "AwS"), get_mean(row, "AnS")]
    psilocin_values = [get_mean(row, "AwP"), get_mean(row, "AnP")]
    mean_ref = (
        np.nanmean(saline_values)
        if np.any(~pd.isna(saline_values))
        else np.nan
    )
    mean_test = (
        np.nanmean(psilocin_values)
        if np.any(~pd.isna(psilocin_values))
        else np.nan
    )
    effect = (
        mean_test - mean_ref
        if not pd.isna(mean_ref) and not pd.isna(mean_test)
        else np.nan
    )

    direction, sign = direction_from_effect(effect, ref, test)
    if sign == 0:
        direction, sign = direction_from_higher(higher, ref, test)

    significant, p_value, sig = significant_from(
        row,
        reject_col=None,
        p_col=p_col,
        sig_col=sig_col,
        p_cutoff=p_cutoff,
    )

    return {
        "analysis_type": "drug_main",
        "contrast_source": spec.source,
        "ref_group": ref,
        "test_group": test,
        "effect": effect,
        "direction": direction,
        "direction_sign": sign,
        "higher_mean": higher if not pd.isna(higher) else "",
        "p": p_value,
        "sig": sig,
        "significant": significant,
        "reject_column_used": "",
        "p_column_used": p_col or "",
        "sig_column_used": sig_col or "",
        "ref_mean": mean_ref,
        "test_mean": mean_test,
    }


def empty_extraction(spec: ContrastSpec, analysis_type: str = "unknown") -> dict:
    return {
        "analysis_type": analysis_type,
        "contrast_source": spec.source,
        "ref_group": spec.ref,
        "test_group": spec.test,
        "effect": np.nan,
        "direction": "",
        "direction_sign": 0,
        "higher_mean": "",
        "p": np.nan,
        "sig": "",
        "significant": None,
        "reject_column_used": "",
        "p_column_used": "",
        "sig_column_used": "",
        "ref_mean": np.nan,
        "test_mean": np.nan,
    }


def extract_metric_row(
    row: pd.Series,
    spec: ContrastSpec,
    p_cutoff: float,
    ttest_sig_col: str,
) -> dict:
    if spec.contrast_type == "pairwise":
        return extract_pairwise(row, spec, p_cutoff)
    if spec.contrast_type == "two_group":
        return extract_two_group(row, spec, p_cutoff, ttest_sig_col)
    if spec.contrast_type == "drug_main":
        return extract_drug_main(row, spec, p_cutoff)
    return empty_extraction(spec)


def normalize_cluster_id(value) -> str:
    """Normalize 1 and 1.0 to the same key while preserving nonnumeric IDs."""
    if pd.isna(value):
        return ""

    text = str(value).strip()
    numeric = safe_float(text)
    if not pd.isna(numeric) and np.isfinite(numeric) and numeric.is_integer():
        return str(int(numeric))
    return text


def read_results(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "cluster_ID" not in df.columns:
        raise ValueError(f"{path} is missing cluster_ID")

    df = df.copy()
    df["cluster_ID"] = df["cluster_ID"].map(normalize_cluster_id)
    if (df["cluster_ID"] == "").any():
        raise ValueError(f"{path} contains missing cluster_ID values")

    duplicated = df.loc[df["cluster_ID"].duplicated(), "cluster_ID"].unique()
    if len(duplicated):
        raise ValueError(
            f"{path} contains duplicate cluster_ID values: {duplicated.tolist()}"
        )
    return df


def classify(z_values: dict, raw_values: dict) -> tuple[str, str, Optional[bool], bool]:
    """Classify cross-metric direction and significance support."""
    z_sign = int(z_values.get("direction_sign") or 0)
    raw_sign = int(raw_values.get("direction_sign") or 0)
    z_sig = z_values.get("significant")
    raw_sig = raw_values.get("significant")

    if z_sign == 0 or raw_sign == 0:
        return "incomplete_or_ambiguous", "missing_or_tie", None, False

    if z_sign != raw_sign:
        return (
            "discordant_exclude_directional_claim",
            "opposite",
            False,
            False,
        )

    if z_sig is True and raw_sig is True:
        return "robust", "same", True, True
    if z_sig is True and raw_sig is not True:
        return "supported_direction", "same", True, True
    if z_sig is not True and raw_sig is True:
        return "raw_only", "same", True, False
    if z_sig is False and raw_sig is False:
        return "concordant_nonsig", "same", True, False
    return "concordant_uncertain_significance", "same", True, False


def direction_matches_expected(
    direction: str,
    expected_direction: str,
) -> Optional[bool]:
    if not direction or direction == "tie" or not expected_direction:
        return None
    return direction == expected_direction


def add_metric_prefix(metric: str, values: dict) -> dict:
    return {f"{metric}_{key}": value for key, value in values.items()}


def cluster_id_sort_key(value: str) -> tuple:
    numeric = safe_float(value)
    return (
        numeric if not pd.isna(numeric) else np.inf,
        str(value),
    )


def audit_pair(
    cluster_set: str,
    z_csv: Path,
    raw_csv: Path,
    p_cutoff: float,
    ttest_sig_col: str,
) -> pd.DataFrame:
    z_df = read_results(z_csv)
    raw_df = read_results(raw_csv)

    z_spec = infer_contrast_spec(cluster_set, set(z_df.columns))
    raw_spec = infer_contrast_spec(cluster_set, set(raw_df.columns))
    base_spec = choose_base_spec(z_spec, raw_spec)
    expected_direction = expected_direction_from_name(cluster_set, base_spec)

    z_by_cluster = z_df.set_index("cluster_ID", drop=False)
    raw_by_cluster = raw_df.set_index("cluster_ID", drop=False)
    cluster_ids = sorted(
        set(z_by_cluster.index) | set(raw_by_cluster.index),
        key=cluster_id_sort_key,
    )

    rows = []
    for cluster_id in cluster_ids:
        if cluster_id in z_by_cluster.index:
            z_values = extract_metric_row(
                z_by_cluster.loc[cluster_id],
                z_spec,
                p_cutoff,
                ttest_sig_col,
            )
        else:
            z_values = empty_extraction(z_spec, analysis_type="missing")

        if cluster_id in raw_by_cluster.index:
            raw_values = extract_metric_row(
                raw_by_cluster.loc[cluster_id],
                raw_spec,
                p_cutoff,
                ttest_sig_col,
            )
        else:
            raw_values = empty_extraction(raw_spec, analysis_type="missing")

        validation_class, concordance, same_direction, include_main = classify(
            z_values,
            raw_values,
        )
        z_matches_expected = direction_matches_expected(
            z_values.get("direction", ""),
            expected_direction,
        )
        raw_matches_expected = direction_matches_expected(
            raw_values.get("direction", ""),
            expected_direction,
        )

        notes = []
        if z_values["analysis_type"] == "missing":
            notes.append("missing_z_cluster")
        if raw_values["analysis_type"] == "missing":
            notes.append("missing_raw_cluster")
        if z_spec.source == "condition_means_no_direct_test":
            notes.append("z_direction_from_condition_means_significance_unknown")
        if raw_spec.source == "condition_means_no_direct_test":
            notes.append("raw_direction_from_condition_means_significance_unknown")
        if z_matches_expected is False:
            notes.append("z_direction_opposes_cluster_name")
        if raw_matches_expected is False:
            notes.append("raw_direction_opposes_cluster_name")
        if validation_class == "discordant_exclude_directional_claim":
            notes.append("do_not_claim_direction_without_qualification")
        elif validation_class == "supported_direction":
            notes.append("raw_direction_concordant_but_not_significant")

        rows.append({
            "cluster_set": cluster_set,
            "cluster_ID": cluster_id,
            "contrast": base_spec.label,
            "expected_direction_from_cluster_name": expected_direction,
            "z_results_csv": str(z_csv),
            "raw_results_csv": str(raw_csv),
            **add_metric_prefix("z", z_values),
            **add_metric_prefix("raw", raw_values),
            "z_matches_expected_direction": z_matches_expected,
            "raw_matches_expected_direction": raw_matches_expected,
            "same_effect_direction": same_direction,
            "direction_concordance": concordance,
            "validation_class": validation_class,
            "include_in_main_directional_interpretation": include_main,
            "notes": ";".join(notes),
        })

    return pd.DataFrame(rows)


def write_summary(audit: pd.DataFrame, summary_out: Path) -> pd.DataFrame:
    if audit.empty:
        summary = pd.DataFrame()
    else:
        summary = (
            audit.groupby(
                [
                    "cluster_set",
                    "contrast",
                    "direction_concordance",
                    "validation_class",
                ],
                dropna=False,
            )
            .size()
            .reset_index(name="n_clusters")
            .sort_values(
                ["cluster_set", "direction_concordance", "validation_class"]
            )
        )

    summary_out.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_out, index=False)
    return summary


def resolve_output_path(path_arg: str, root: Path) -> Path:
    path = Path(path_arg).expanduser()
    if not path.is_absolute():
        path = root / path
    return path


@log_command
def main() -> None:
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    root = Path(args.root).expanduser().resolve()
    z_base = root / args.z_dir
    raw_base = root / args.raw_dir

    z_dirs = build_dir_map(z_base, Z_DIR_PREFIX)
    raw_dirs = build_dir_map(raw_base, RAW_DIR_PREFIX)

    all_keys = sorted(set(z_dirs) | set(raw_dirs), key=cluster_set_sort_key)
    if not all_keys:
        raise FileNotFoundError(
            f"No cluster result directories found under {z_base} or {raw_base}."
        )

    pair_tables = []
    skipped = []

    for cluster_set in all_keys:
        z_dir = z_dirs.get(cluster_set)
        raw_dir = raw_dirs.get(cluster_set)
        if z_dir is None or raw_dir is None:
            reason = "missing_z_dir" if z_dir is None else "missing_raw_dir"
            skipped.append((cluster_set, reason))
            continue

        z_csv = choose_result_csv(z_dir, cluster_set)
        raw_csv = choose_result_csv(raw_dir, cluster_set)
        if z_csv is None or raw_csv is None:
            reasons = []
            if z_csv is None:
                reasons.append("missing_z_results_csv")
            if raw_csv is None:
                reasons.append("missing_raw_results_csv")
            skipped.append((cluster_set, ";".join(reasons)))
            continue

        if args.verbose:
            print(f"\nAuditing: {cluster_set}")
            print(f"  z:   {z_csv.relative_to(root)}")
            print(f"  raw: {raw_csv.relative_to(root)}")

        pair_tables.append(
            audit_pair(
                cluster_set=cluster_set,
                z_csv=z_csv,
                raw_csv=raw_csv,
                p_cutoff=args.p_cutoff,
                ttest_sig_col=args.ttest_sig_col,
            )
        )

    audit = (
        pd.concat(pair_tables, ignore_index=True)
        if pair_tables
        else pd.DataFrame()
    )

    out = resolve_output_path(args.out, root)
    out.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(out, index=False)

    summary_out = resolve_output_path(args.summary_out, root)
    summary = write_summary(audit, summary_out)

    if skipped:
        skipped_out = out.with_name(f"{out.stem}_skipped{out.suffix}")
        pd.DataFrame(
            skipped,
            columns=["cluster_set", "reason"],
        ).to_csv(skipped_out, index=False)
    else:
        skipped_out = None

    print(f"\nSaved audit table: {out}")
    print(f"Saved summary table: {summary_out}")
    if skipped_out is not None:
        print(f"Saved skipped-pairs table: {skipped_out}")

    if not summary.empty:
        print("\nSummary:")
        print(summary.to_string(index=False))

    verbose_end_msg()


if __name__ == "__main__":
    main()
