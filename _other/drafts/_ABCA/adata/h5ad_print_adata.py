#!/usr/bin/env python3
import sys
import anndata as ad
import numpy as np

fname = sys.argv[1]
adata = ad.read_h5ad(fname, backed="r")
print(adata)