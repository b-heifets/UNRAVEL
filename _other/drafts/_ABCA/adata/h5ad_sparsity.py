#!/usr/bin/env python3

import sys
import numpy as np
from scipy import sparse
import anndata as ad


adata = ad.read_h5ad(sys.argv[1])

# Density = nonzero fraction
if sparse.issparse(adata.X):
    nnz = adata.X.nnz
    total = np.prod(adata.X.shape)
    density = nnz / total
else:
    density = np.count_nonzero(adata.X) / adata.X.size

print(f"Density: {density:.4f} ({density*100:.2f}% nonzero)")
print(f"Sparsity: {1-density:.4f} ({(1-density)*100:.2f}% zeros)")
