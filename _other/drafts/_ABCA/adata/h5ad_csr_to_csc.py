#!/usr/bin/env python3

import sys
import anndata as ad
from pathlib import Path

adata = ad.read_h5ad(sys.argv[1])
print(type(adata.raw.X if adata.raw is not None else adata.X))

# Convert to CSC format (column-based)
adata.X = adata.X.tocsc()
print(type(adata.raw.X if adata.raw is not None else adata.X))

output_path = str(Path(sys.argv[1])).replace(".h5ad", "_csc.h5ad")
adata.write_h5ad(output_path)