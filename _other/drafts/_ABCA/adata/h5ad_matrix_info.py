#!/usr/bin/env python3

import sys
import h5py

with h5py.File(sys.argv[1], "r") as f:
    # Navigate to the X group
    print("Keys under /X:", list(f["X"].keys()))

    # Check the storage format
    if "data" in f["X"] and "indices" in f["X"]:
        fmt = f["X"].attrs.get("encoding-type", "unknown")
        print("Encoding type:", fmt)
    else:
        print("Not a sparse matrix (probably dense).")