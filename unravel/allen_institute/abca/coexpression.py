#!/usr/bin/env python3

"""
Use ``abca_coexpression`` (``coexpression``) to summarize
cell-level co-expression from Allen Brain Cell Atlas expression CSV files.

The input must contain one row per cell, such as output from
``abca_scRNAseq_expression`` (``rna_exp``) or
``abca_merfish_join_expression``. An ``exp_summary`` output cannot be used,
because separate per-gene summaries do not retain which genes occur in the
same cells.

Gene pairs are supplied with ``--pairs`` using ``gene1:gene2`` syntax. Either
side may instead be a gene set whose members are joined with ``+``, such as
``gene1+gene2:gene3+gene4+gene5``. A gene is considered expressed when its
log2 expression is > 3 by default. A set is positive when any member is above
the threshold.

The primary output is ``percent_coexpressing``: the percentage of analyzed
cells positive for both sides of a comparison. Two conditional percentages
show the overlap relative to the positive cells on each side. Mean expression
is calculated across the genes on each side and across co-expressing cells.
The expression ratio is side 1 mean / side 2 mean; a value > 1 favors side 1
and a value < 1 favors side 2.

The ratio is only a rough transcript-balance measure. It is not a signaling
ratio and does not account for receptor protein abundance, agonist affinity or
potency, receptor reserve, coupling efficiency, or downstream amplification.

Examples:
---------
    # Human snRNA-seq neurons
    coexpression -i WHB_HTR.csv \
        -p HTR2A:HTR2C HTR1E:HTR2A HTR1E:HTR2C \
        -o WHB_HTR_coexpression.csv

    # Mouse scRNA-seq neurons
    coexpression -i WMB_Htr.csv \
        -p Htr2a:Htr2c Htr1f:Htr2a Htr1f:Htr2c \
        -o WMB_Htr_coexpression.csv

    # Gene sets are also supported
    coexpression -i expression.csv \
        -p gene1+gene2:gene3+gene4+gene5 \
        -o gene_set_coexpression.csv

    # Also summarize within each region
    coexpression -i WHB_HTR.csv -p HTR2A:HTR2C \
        -g region_of_interest_acronym \
        -o WHB_HTR_coexpression_by_region.csv
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SM, SuppressMetavar
from unravel.core.utils import log_command, verbose_end_msg, verbose_start_msg


@dataclass(frozen=True)
class Comparison:
    """Two genes or gene sets to compare."""

    side_1: tuple[str, ...]
    side_2: tuple[str, ...]

    @property
    def side_1_label(self) -> str:
        return "+".join(self.side_1)

    @property
    def side_2_label(self) -> str:
        return "+".join(self.side_2)

    @property
    def label(self) -> str:
        return f"{self.side_1_label}:{self.side_2_label}"

    @property
    def genes(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.side_1, *self.side_2)))

    @property
    def comparison_type(self) -> str:
        if len(self.side_1) == len(self.side_2) == 1:
            return "gene_pair"
        return "gene_set"


def parse_args():
    parser = RichArgumentParser(
        formatter_class=SuppressMetavar,
        add_help=False,
        docstring=__doc__,
    )

    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument(
        "-i",
        "--input",
        help="Cell-level expression CSV (one row per cell).",
        required=True,
        action=SM,
    )
    reqs.add_argument(
        "-p",
        "--pairs",
        help=(
            "Pairs as SIDE1:SIDE2. Join genes within a set with +, such as "
            "gene1+gene2:gene3+gene4+gene5."
        ),
        nargs="*",
        required=True,
        action=SM,
    )

    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument(
        "-o",
        "--output",
        help="Output CSV. Default: <input>_coexpression.csv",
        default=None,
        action=SM,
    )
    opts.add_argument(
        "-g",
        "--group-by",
        help=(
            "Optional metadata column(s) for joint grouping, such as "
            "region_of_interest_acronym or subclass."
        ),
        nargs="+",
        default=None,
        action=SM,
    )
    opts.add_argument(
        "-t",
        "--threshold",
        help="A gene is positive when expression is > this value. Default: 3",
        type=float,
        default=3.0,
        action=SM,
    )
    opts.add_argument(
        "--min-cells",
        help="Minimum number of cells with complete data per output row. Default: 1",
        type=int,
        default=1,
        action=SM,
    )

    general = parser.add_argument_group("General arguments")
    general.add_argument(
        "-v",
        "--verbose",
        help="Increase verbosity. Default: False",
        action="store_true",
        default=False,
    )

    return parser.parse_args()


def _parse_side(text: str, specification: str) -> tuple[str, ...]:
    genes = tuple(gene.strip() for gene in text.split("+") if gene.strip())
    if not genes:
        raise ValueError(f"Empty side in comparison: {specification}")
    if len(set(genes)) != len(genes):
        raise ValueError(f"Repeated gene within comparison: {specification}")
    return genes


def parse_comparison(specification: str) -> Comparison:
    """Parse ``GENE:GENE`` or ``GENE:GENE+GENE`` syntax."""
    if specification.count(":") != 1:
        raise ValueError(
            f"Invalid comparison '{specification}'. Use SIDE1:SIDE2, for "
            "example gene1:gene2+gene3."
        )

    side_1_text, side_2_text = specification.split(":")
    side_1 = _parse_side(side_1_text, specification)
    side_2 = _parse_side(side_2_text, specification)

    overlap = set(side_1).intersection(side_2)
    if overlap:
        raise ValueError(
            f"The two sides of '{specification}' overlap: "
            f"{', '.join(sorted(overlap))}"
        )

    return Comparison(side_1=side_1, side_2=side_2)


def parse_comparisons(specifications: Sequence[str]) -> list[Comparison]:
    """Parse comparisons while preserving order and rejecting duplicates."""
    if not specifications:
        raise ValueError("Provide at least one comparison with --pairs.")
    comparisons = [parse_comparison(spec) for spec in specifications]
    labels = [comparison.label for comparison in comparisons]
    if len(labels) != len(set(labels)):
        raise ValueError("Duplicate comparisons were provided.")
    return comparisons


def required_genes(comparisons: Sequence[Comparison]) -> list[str]:
    """Return all comparison genes in first-seen order."""
    return list(
        dict.fromkeys(
            gene
            for comparison in comparisons
            for gene in comparison.genes
        )
    )


def _percent(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return np.nan
    return 100.0 * numerator / denominator


def summarize_cells(
    cells: pd.DataFrame,
    comparison: Comparison,
    threshold: float,
) -> dict[str, int | float | str]:
    """Calculate co-expression statistics for one set of cells."""
    values = cells.loc[:, comparison.genes]
    complete = values.notna().all(axis=1)
    values = values.loc[complete]

    input_cell_count = len(cells)
    cell_count = len(values)
    missing_cell_count = input_cell_count - cell_count

    side_1_positive = values.loc[:, comparison.side_1].gt(threshold).any(axis=1)
    side_2_positive = values.loc[:, comparison.side_2].gt(threshold).any(axis=1)
    coexpressing = side_1_positive & side_2_positive

    side_1_count = int(side_1_positive.sum())
    side_2_count = int(side_2_positive.sum())
    coexpressing_count = int(coexpressing.sum())

    side_1_mean = np.nan
    side_2_mean = np.nan
    mean_ratio = np.nan
    if coexpressing_count:
        coexpressing_values = values.loc[coexpressing]
        side_1_mean = float(
            coexpressing_values.loc[:, comparison.side_1]
            .to_numpy(dtype=float)
            .mean()
        )
        side_2_mean = float(
            coexpressing_values.loc[:, comparison.side_2]
            .to_numpy(dtype=float)
            .mean()
        )
        if side_2_mean != 0:
            mean_ratio = side_1_mean / side_2_mean

    return {
        "comparison": comparison.label,
        "comparison_type": comparison.comparison_type,
        "side_1": comparison.side_1_label,
        "side_2": comparison.side_2_label,
        "threshold": threshold,
        "input_cell_count": input_cell_count,
        "cell_count": cell_count,
        "missing_cell_count": missing_cell_count,
        "side_1_positive_count": side_1_count,
        "side_2_positive_count": side_2_count,
        "coexpressing_cell_count": coexpressing_count,
        "percent_side_1_positive": _percent(side_1_count, cell_count),
        "percent_side_2_positive": _percent(side_2_count, cell_count),
        "percent_coexpressing": _percent(coexpressing_count, cell_count),
        "percent_of_side_1_positive_also_side_2": _percent(
            coexpressing_count,
            side_1_count,
        ),
        "percent_of_side_2_positive_also_side_1": _percent(
            coexpressing_count,
            side_2_count,
        ),
        "mean_side_1_expression_in_coexpressing_cells": side_1_mean,
        "mean_side_2_expression_in_coexpressing_cells": side_2_mean,
        "side_1_to_side_2_mean_expression_ratio_in_coexpressing_cells": (
            mean_ratio
        ),
    }


def analyze_coexpression(
    expression_df: pd.DataFrame,
    comparisons: Sequence[Comparison],
    threshold: float = 3.0,
    group_by: Sequence[str] | None = None,
    min_cells: int = 1,
) -> pd.DataFrame:
    """Return overall and optional grouped co-expression summaries."""
    group_by = list(group_by or [])
    rows: list[dict] = []

    for comparison in comparisons:
        overall = summarize_cells(expression_df, comparison, threshold)
        if overall["cell_count"] >= min_cells:
            rows.append(
                {
                    "scope": "overall",
                    **{column: "All" for column in group_by},
                    **overall,
                }
            )

        if not group_by:
            continue

        grouper = group_by[0] if len(group_by) == 1 else group_by
        groups = expression_df.groupby(
            grouper,
            dropna=False,
            observed=True,
            sort=False,
        )
        for keys, cells in groups:
            if len(group_by) == 1:
                keys = (keys,)
            grouped = summarize_cells(cells, comparison, threshold)
            if grouped["cell_count"] < min_cells:
                continue
            rows.append(
                {
                    "scope": "grouped",
                    **dict(zip(group_by, keys)),
                    **grouped,
                }
            )

    if not rows:
        raise ValueError(
            "No rows met --min-cells after excluding cells with missing "
            "expression values."
        )

    results = pd.DataFrame(rows)
    float_columns = results.select_dtypes(include="number").columns.difference(
        [
            "input_cell_count",
            "cell_count",
            "missing_cell_count",
            "side_1_positive_count",
            "side_2_positive_count",
            "coexpressing_cell_count",
        ]
    )
    results.loc[:, float_columns] = results.loc[:, float_columns].round(6)
    return results


def load_expression_csv(
    input_path: Path,
    comparisons: Sequence[Comparison],
    group_by: Sequence[str] | None,
    columns: Sequence[str],
) -> pd.DataFrame:
    """Load only columns required for the requested analysis."""
    group_by = list(group_by or [])
    genes = required_genes(comparisons)
    missing_genes = [gene for gene in genes if gene not in columns]
    missing_groups = [column for column in group_by if column not in columns]

    if missing_genes:
        raise ValueError(
            f"Genes not found in the input CSV: {', '.join(missing_genes)}"
        )

    if missing_groups:
        raise ValueError(
            "Grouping columns not found: " + ", ".join(missing_groups)
        )

    usecols = [*group_by, *genes]
    dtype = {column: "string" for column in group_by}
    expression_df = pd.read_csv(
        input_path,
        usecols=usecols,
        dtype=dtype or None,
        low_memory=False,
    )

    invalid_counts = {}
    for gene in genes:
        original_missing = expression_df[gene].isna()
        numeric = pd.to_numeric(expression_df[gene], errors="coerce")
        invalid_count = int((numeric.isna() & ~original_missing).sum())
        if invalid_count:
            invalid_counts[gene] = invalid_count
        expression_df[gene] = numeric

    if invalid_counts:
        details = ", ".join(
            f"{gene}={count}" for gene, count in invalid_counts.items()
        )
        print(
            "[yellow]Warning: Non-numeric expression values were treated as "
            f"missing ({details}).[/yellow]"
        )

    if expression_df.loc[:, genes].lt(0).any(axis=None):
        raise ValueError(
            "Negative expression values were found. This script expects "
            "nonnegative log2(x + 1) expression values."
        )

    return expression_df


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if args.min_cells < 1:
        raise ValueError("--min-cells must be at least 1.")
    if not np.isfinite(args.threshold):
        raise ValueError("--threshold must be a finite number.")

    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name(f"{input_path.stem}_coexpression.csv")
    )
    if output_path.exists():
        raise FileExistsError(
            f"Output file already exists: {output_path}. "
            "Choose a new path with -o."
        )

    comparisons = parse_comparisons(args.pairs)
    columns = pd.read_csv(input_path, nrows=0).columns.tolist()
    expression_df = load_expression_csv(
        input_path,
        comparisons,
        args.group_by,
        columns,
    )
    results = analyze_coexpression(
        expression_df,
        comparisons,
        threshold=args.threshold,
        group_by=args.group_by,
        min_cells=args.min_cells,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    results.to_csv(output_path, index=False)
    print(
        f"\n    Analyzed {len(expression_df):,} cells for "
        f"{len(comparisons):,} comparisons at expression > "
        f"{args.threshold:g}."
    )
    print(f"    Saved {len(results):,} rows to {output_path}\n")

    verbose_end_msg()


if __name__ == "__main__":
    main()