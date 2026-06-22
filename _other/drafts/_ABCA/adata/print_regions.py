#!/usr/bin/env python3
"""
Use ``load_metadata_regions`` to inspect available regions in an Allen Brain Cell Atlas dataset
(.zarr or .h5ad).

Example:
    load_metadata_regions.py path/to/C57BL6J-638850-log2.zarr
    load_metadata_regions.py path/to/WHB-10Xv3-log2.h5ad --column anatomical_division_label
"""

import sys
import anndata as ad
import pandas as pd
import zarr
from pathlib import Path
import warnings
from anndata._core.aligned_df import ImplicitModificationWarning
warnings.filterwarnings("ignore", category=ImplicitModificationWarning)

from load_dense_zarr_dask import load_zarr_table

# def load_zarr_table(group):
#     """Rebuild a pandas DataFrame from an AnnData Zarr group, handling categorical data."""
#     cols = {}
#     for key, v in group.items():
#         if isinstance(v, zarr.Array):
#             cols[key] = v[:]
#         elif isinstance(v, zarr.Group) and {"categories", "codes"} <= set(v.keys()):
#             categories = v["categories"][:].astype(str)
#             codes = v["codes"][:]
#             cols[key] = pd.Categorical.from_codes(codes, categories)
#     df = pd.DataFrame(cols)
#
#     idx_name = group.attrs.get("_index")
#     if isinstance(idx_name, str) and idx_name in df.columns:
#         df = df.set_index(idx_name)
#
#     return df


def load_metadata(path):
    """Load only metadata from a .zarr or .h5ad file."""
    path = Path(path)
    if path.suffix == ".zarr":
        print(f"[green]Loading metadata from {path} (Zarr)...[/green]")
        root = zarr.open_group(path, mode="r")
        obs = load_zarr_table(root["obs"])
        return obs

    elif path.suffix == ".h5ad":
        print(f"[green]Loading metadata from {path} (H5AD)...[/green]")
        adata = ad.read_h5ad(path, backed="r")
        return adata.obs.copy()

    else:
        raise ValueError("Input must be a .zarr or .h5ad file.")


def summarize_regions(obs_df, region_col=None, top_n=30):
    """Summarize cell counts by region column."""

    print(obs_df)

    # Auto-detect plausible region column if not specified
    candidates = [c for c in obs_df.columns if "region" in c or "section" in c or "division" in c]
    if not region_col:
        if candidates:
            region_col = candidates[0]
            print(f"[yellow]No region column specified; using '{region_col}'[/yellow]")
        else:
            raise ValueError("Could not infer region column; specify one with --column")

    counts = obs_df[region_col].value_counts().sort_values(ascending=False)
    print(f"\n[bold cyan]Top {min(top_n, len(counts))} regions by cell count:[/bold cyan]\n")
    print(counts.head(top_n).to_string())

    return counts


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Inspect regions in .zarr or .h5ad metadata.")
    parser.add_argument("input", help="Path to .zarr or .h5ad file.")
    parser.add_argument("--column", help="Metadata column to use for region grouping.")
    parser.add_argument("--save", help="Optional path to save summary CSV.")
    parser.add_argument("--top", type=int, default=30, help="Show top N regions (default: 30).")
    args = parser.parse_args()

    obs = load_metadata(args.input)
    region_counts = summarize_regions(obs, args.column, args.top)

    if args.save:
        out = Path(args.save)
        region_counts.to_csv(out)
        print(f"\nSaved region summary to {out.resolve()}")


if __name__ == "__main__":
    main()
