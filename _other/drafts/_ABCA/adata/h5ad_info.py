#!/usr/bin/env python3
import sys
import h5py

path = sys.argv[1]
print(f"Inspecting: {path}\n")

with h5py.File(path, "r") as f:
    # Check if 'X' exists and whether it's dense or sparse
    if "X" in f:
        X = f["X"]
        if isinstance(X, h5py.Group):
            print("Sparse matrix stored under X/")
            print("Available subkeys:", list(X.keys()))
            if "data" in X:
                data = X["data"]
                print(f"  data.shape: {data.shape}, chunks: {data.chunks}")
            if "indices" in X:
                indices = X["indices"]
                print(f"  indices.shape: {indices.shape}, chunks: {indices.chunks}")
            if "indptr" in X:
                indptr = X["indptr"]
                print(f"  indptr.shape: {indptr.shape}, chunks: {indptr.chunks}")
        else:
            print("Dense matrix stored directly in X")
            print(f"  shape: {X.shape}, chunks: {X.chunks}")
    else:
        print("No 'X' dataset found in this file")

    # Print lightweight metadata info (no heavy read)
    if "obs" in f:
        print(f"\nobs columns: {list(f['obs'].keys())[:5]}{'...' if len(f['obs'].keys())>5 else ''}")
    if "var" in f:
        print(f"var columns: {list(f['var'].keys())[:5]}{'...' if len(f['var'].keys())>5 else ''}")

