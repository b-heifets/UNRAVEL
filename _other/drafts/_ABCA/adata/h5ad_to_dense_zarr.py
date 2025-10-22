#!/usr/bin/env python3

import sys
import anndata as ad
import zarr
import numpy as np

# TODO: Also support uns data conversion or reading with load_dense_zarr_dask.py

def h5ad_to_dense_zarr(h5ad_file_path):
    """Convert a .h5ad file to a dense .zarr file with one column (gene) per chunk."""

    print(f"\nLoading h5ad file: {h5ad_file_path}\n")
    adata = ad.read_h5ad(h5ad_file_path)

    print(f"Converting to dense array format...\n")
    adata.X = adata.X.toarray()

    # Write to zarr with one column (gene) per chunk 
    output = h5ad_file_path.replace(".h5ad", ".zarr")
    print(f"\nWriting zarr file: {output}\n")
    adata.write_zarr(
        output,
        chunks=(adata.n_obs, 1),  # one column (gene) per chunk
    )

def main():
    if len(sys.argv) != 2 or not sys.argv[1].endswith(".h5ad"):
        print("Usage: h5ad_to_dense_zarr.py <input_file.h5ad>")
        sys.exit(1)

    h5ad_to_dense_zarr(sys.argv[1])

if __name__ == "__main__":
    main()