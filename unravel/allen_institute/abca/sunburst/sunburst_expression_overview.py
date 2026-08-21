#!/usr/bin/env python3

"""
Use ``abca_sunburst_expression_overview`` or ``seov`` from UNRAVEL to 
combine multiple *_all.csv outputs from ``abca_sunburst_expression`` and create overview plots.

The dot plot shows:
    - rows: regions/input datasets
    - columns: genes
    - dot color: mean expression
    - dot size: percent of cells above the expression threshold

Inputs:
    - One or more *_all.csv files, directories, or glob patterns (e.g.,
      "ABCA_sunburst_cmax6.0_thr3.0/*_all.csv" or "ABCA_sunburst_cmax6.0_thr3.0/*/*_all.csv")
    - Each *_all.csv file should have the following columns:
        - input: the input dataset name (e.g., WMB-10Xv3, WHB-10Xv3)
        - species: mouse or human
        - gene: the gene symbol
        - threshold: the expression threshold used for filtering
        - all_mean: the mean expression value for the gene in the input dataset
        - all_percent: the percent of cells above the threshold for the gene in the input dataset
    - The *_all.csv files can be generated using ``abca_sunburst_expression``

Outputs:
    - path/abca_expression_overview_long.csv: combined long-format CSV of all *_all.csv files
    - path/abca_expression_overview_mean_wide.csv: wide-format CSV of mean expression values (rows: regions, columns: genes)
    - path/abca_expression_overview_percent_wide.csv: wide-format CSV of percent expressing values (rows: regions, columns: genes)
    - path/abca_expression_overview_dotplot.png/pdf: dot plot
    - path/abca_expression_overview_mean_heatmap.png/pdf: heatmap of mean expression values
    - path/abca_expression_overview_percent_heatmap.png/pdf: heatmap of percent expressing values

Usage:
------
    ./sunburst_expression_overview.py -i ABCA_sunburst_cmax6.0_thr3.0/all_expression_thr3.0
"""

import argparse
import glob
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "input",
    "species",
    "gene",
    "threshold",
    "all_mean",
    "all_percent",
}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-i",
        "--input",
        nargs="+",
        required=True,
        help="One or more *_all.csv files, directories, or glob patterns.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="abca_expression_overview",
        help="Output prefix. Default: abca_expression_overview",
    )
    parser.add_argument(
        "-t",
        "--threshold",
        type=float,
        default=None,
        help="Keep only this expression threshold when multiple thresholds are present.",
    )
    parser.add_argument(
        "--region-order",
        default=None,
        help="Comma-separated region order or a text file with one region per line.",
    )
    parser.add_argument(
        "--gene-order",
        default=None,
        help="Comma-separated gene order or a text file with one gene per line.",
    )
    parser.add_argument(
        "--annotate",
        action="store_true",
        help="Write numeric values in heatmap cells.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="PNG resolution. Default: 300",
    )
    return parser.parse_args()


def collect_files(inputs):
    files = []

    for item in inputs:
        path = Path(item)

        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(path.rglob("*_all.csv"))
        else:
            files.extend(Path(match) for match in glob.glob(item, recursive=True))

    files = sorted({path.resolve() for path in files if path.name.endswith("_all.csv")})

    if not files:
        raise FileNotFoundError("No *_all.csv files were found.")

    return files


def parse_order(value):
    if value is None:
        return None

    path = Path(value)
    if path.is_file():
        return [
            line.strip()
            for line in path.read_text().splitlines()
            if line.strip()
        ]

    return [item.strip() for item in value.split(",") if item.strip()]


def region_from_input(input_name):
    """
    Example:
        WMB-10Xv3_Htr2a_expression_data_all_regions_log2__ACA.csv -> ACA
        WHB-...__Human_NAC.csv -> Human_NAC
    """
    stem = Path(str(input_name)).stem
    return stem.rsplit("__", 1)[-1]


def load_summary(files):
    frames = []

    for path in files:
        df = pd.read_csv(path)
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"{path} is missing columns: {sorted(missing)}")

        df = df.copy()
        df["source_file"] = str(path)

        if "region" not in df.columns:
            df["region"] = df["input"].map(region_from_input)

        frames.append(df)

    summary = pd.concat(frames, ignore_index=True)
    summary = summary.drop_duplicates()

    return summary


def apply_order(values, requested_order, name):
    observed = list(dict.fromkeys(values))

    if requested_order is None:
        return sorted(observed, key=str.casefold)

    missing = [item for item in requested_order if item not in observed]
    if missing:
        print(f"Warning: {name} values not found and skipped: {missing}")

    requested_present = [item for item in requested_order if item in observed]
    remaining = [item for item in observed if item not in requested_present]

    return requested_present + sorted(remaining, key=str.casefold)


def save_figure(fig, output_stem, dpi):
    fig.savefig(f"{output_stem}.png", dpi=dpi, bbox_inches="tight")
    fig.savefig(f"{output_stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def make_dotplot(summary, regions, genes, output_prefix, dpi):
    plot_df = summary.copy()
    x_lookup = {gene: i for i, gene in enumerate(genes)}
    y_lookup = {region: i for i, region in enumerate(regions)}

    x = plot_df["gene"].map(x_lookup)
    y = plot_df["region"].map(y_lookup)

    percent = plot_df["all_percent"].clip(lower=0, upper=100)
    dot_sizes = 8 + percent * 2.5

    width = max(7, 0.65 * len(genes) + 3.5)
    height = max(4.5, 0.34 * len(regions) + 2.5)

    fig, ax = plt.subplots(figsize=(width, height), constrained_layout=True)

    scatter = ax.scatter(
        x,
        y,
        s=dot_sizes,
        c=plot_df["all_mean"],
        cmap="magma_r",
        edgecolors="black",
        linewidths=0.35,
    )

    ax.set_xticks(range(len(genes)), genes, rotation=45, ha="right")
    ax.set_yticks(range(len(regions)), regions)
    ax.set_xlabel("Gene")
    ax.set_ylabel("Region / input dataset")
    ax.set_xlim(-0.6, len(genes) - 0.4)
    ax.set_ylim(len(regions) - 0.4, -0.6)
    ax.grid(False)

    colorbar = fig.colorbar(scatter, ax=ax, pad=0.02)
    colorbar.set_label("Mean log2(CPM + 1)")

    legend_values = [10, 25, 50, 75, 100]
    handles = [
        ax.scatter(
            [],
            [],
            s=8 + value * 2.5,
            facecolors="none",
            edgecolors="black",
            linewidths=0.6,
            label=f"{value}%",
        )
        for value in legend_values
    ]
    ax.legend(
        handles=handles,
        title="Cells above threshold",
        bbox_to_anchor=(1.02, 0),
        loc="lower left",
        frameon=False,
        borderaxespad=0,
    )

    save_figure(fig, f"{output_prefix}_dotplot", dpi)


def make_heatmap(
    summary,
    regions,
    genes,
    value_col,
    label,
    output_stem,
    cmap,
    dpi,
    annotate=False,
    vmin=None,
    vmax=None,
):
    matrix = (
        summary.pivot(index="region", columns="gene", values=value_col)
        .reindex(index=regions, columns=genes)
    )

    width = max(7, 0.65 * len(genes) + 3.0)
    height = max(4.5, 0.34 * len(regions) + 2.0)

    fig, ax = plt.subplots(figsize=(width, height), constrained_layout=True)

    masked = np.ma.masked_invalid(matrix.to_numpy(dtype=float))
    image = ax.imshow(
        masked,
        aspect="auto",
        interpolation="nearest",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
    )

    ax.set_xticks(range(len(genes)), genes, rotation=45, ha="right")
    ax.set_yticks(range(len(regions)), regions)
    ax.set_xlabel("Gene")
    ax.set_ylabel("Region / input dataset")

    colorbar = fig.colorbar(image, ax=ax, pad=0.02)
    colorbar.set_label(label)

    if annotate:
        values = matrix.to_numpy(dtype=float)
        for row in range(values.shape[0]):
            for col in range(values.shape[1]):
                value = values[row, col]
                if np.isfinite(value):
                    ax.text(
                        col,
                        row,
                        f"{value:.1f}",
                        ha="center",
                        va="center",
                        fontsize=7,
                    )

    save_figure(fig, output_stem, dpi)


def main():
    args = parse_args()

    files = collect_files(args.input)
    summary = load_summary(files)

    if args.threshold is not None:
        summary = summary[np.isclose(summary["threshold"], args.threshold)].copy()
        if summary.empty:
            raise ValueError(f"No rows matched threshold {args.threshold}.")

    thresholds = sorted(summary["threshold"].dropna().unique())
    if len(thresholds) > 1:
        raise ValueError(
            f"Multiple thresholds found: {thresholds}. "
            "Use --threshold to select one before plotting."
        )

    key_cols = ["region", "gene"]
    duplicates = summary.duplicated(key_cols, keep=False)
    if duplicates.any():
        duplicate_rows = (
            summary.loc[duplicates, key_cols + ["input", "source_file"]]
            .sort_values(key_cols)
            .to_string(index=False)
        )
        raise ValueError(
            "More than one result was found for at least one region-gene pair:\n"
            f"{duplicate_rows}"
        )

    region_order = parse_order(args.region_order)
    gene_order = parse_order(args.gene_order)

    regions = apply_order(summary["region"].tolist(), region_order, "region")
    genes = apply_order(summary["gene"].tolist(), gene_order, "gene")

    output_prefix = Path(args.output)
    output_prefix.parent.mkdir(parents=True, exist_ok=True)

    summary = summary.sort_values(
        ["region", "gene"],
        key=lambda col: col.astype(str).str.casefold(),
    )
    summary.to_csv(f"{output_prefix}_long.csv", index=False)

    mean_wide = (
        summary.pivot(index="region", columns="gene", values="all_mean")
        .reindex(index=regions, columns=genes)
    )
    mean_wide.to_csv(f"{output_prefix}_mean_wide.csv")

    percent_wide = (
        summary.pivot(index="region", columns="gene", values="all_percent")
        .reindex(index=regions, columns=genes)
    )
    percent_wide.to_csv(f"{output_prefix}_percent_wide.csv")

    make_dotplot(summary, regions, genes, output_prefix, args.dpi)

    make_heatmap(
        summary,
        regions,
        genes,
        value_col="all_mean",
        label="Mean log2(CPM + 1)",
        output_stem=f"{output_prefix}_mean_heatmap",
        cmap="magma_r",
        dpi=args.dpi,
        annotate=args.annotate,
    )

    make_heatmap(
        summary,
        regions,
        genes,
        value_col="all_percent",
        label="Cells above threshold (%)",
        output_stem=f"{output_prefix}_percent_heatmap",
        cmap="viridis_r",
        dpi=args.dpi,
        annotate=args.annotate,
        vmin=0,
        vmax=100,
    )

    print(f"Found {len(files)} *_all.csv files.")
    print(f"Saved {len(summary)} region-gene rows.")
    print(f"Output prefix: {output_prefix}")


if __name__ == "__main__":
    main()