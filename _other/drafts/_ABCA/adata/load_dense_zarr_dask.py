#!/usr/bin/env python3

import sys
import scanpy as sc
import anndata as ad
import pandas as pd
from pathlib import Path
import zarr
import dask.array as da

import warnings
from anndata._core.aligned_df import ImplicitModificationWarning
warnings.filterwarnings("ignore", category=ImplicitModificationWarning)

def load_zarr_table(group):
    """Rebuild a pandas DataFrame from an AnnData Zarr group, handling categorical data."""
    cols = {}
    for key, v in group.items():
        if isinstance(v, zarr.Array):
            # Regular 1D column (e.g., cell_label)
            cols[key] = v[:]
        elif isinstance(v, zarr.Group) and set(v.keys()) >= {"categories", "codes"}:
            # Categorical column
            categories = v["categories"][:].astype(str)
            codes = v["codes"][:]
            col = pd.Categorical.from_codes(codes, categories)
            cols[key] = col
        else:
            print(f"Skipping unrecognized entry: {key}")

    df = pd.DataFrame(cols)

    # Set index according to _index attribute if present
    idx_name = group.attrs.get("_index", None)
    if isinstance(idx_name, str) and idx_name in df.columns:
        df = df.set_index(idx_name)

    # Keep columns in stored order if provided
    col_order = group.attrs.get("column-order", None)
    if col_order:
        cols_to_keep = [c for c in col_order if c in df.columns]
        df = df[cols_to_keep]

    return df

def lazy_load_genes(zarr_path: str | Path, gene_list: list[str]) -> ad.AnnData:
    """
    Lazily load a subset of genes from a Zarr-stored AnnData dataset.

    Parameters
    ----------
    zarr_path : str or Path
        Path to the .zarr store.
    gene_list : list of str
        List of gene symbols to extract (case-insensitive).

    Returns
    -------
    AnnData
        A lightweight AnnData object with only the selected genes.
    """
    print(f"Opening {zarr_path} lazily...")
    f = zarr.open_group(zarr_path, mode="r")

    # Load metadata
    obs = load_zarr_table(f["obs"])
    var = load_zarr_table(f["var"])

    # Match genes (case-insensitive)
    gene_list_lower = [g.lower() for g in gene_list]
    sym_lower = var["gene_symbol"].astype(str).str.lower()
    mask = sym_lower.isin(gene_list_lower)
    found = var.loc[mask, "gene_symbol"].tolist()
    if not found:
        raise ValueError(f"No genes from {gene_list} found in var['gene_symbol'].")

    # Lazily load X as Dask array and subset
    X = da.from_zarr(f["X"], chunks=f["X"].chunks)[:, mask.to_numpy()]
    print(f"Lazily loaded expression data: {X.shape}")

    # Build lightweight AnnData object
    adata_subset = ad.AnnData(
        X=X,
        obs=obs,
        var=var.loc[mask].reset_index(drop=True),
    )

    return adata_subset


def main():

    file_path = sys.argv[1]

    if not str(Path(file_path)).endswith(".zarr"):
        raise ValueError("Please provide a .zarr file path as the first argument.")

    adata_subset = lazy_load_genes(file_path, sys.argv[2:])

    print(adata_subset)

if __name__ == "__main__":
    main()