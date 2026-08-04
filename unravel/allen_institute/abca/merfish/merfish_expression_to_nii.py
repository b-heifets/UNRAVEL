#!/usr/bin/env python3

"""
Use ``abca_merfish_expression_to_nii`` or ``me`` from UNRAVEL to make 3D .nii.gz
images of ABCA MERFISH expression data.

Parallel / in-memory version:
    - avoids backed AnnData subsetting, which can fail or be slow for CSRDataset-backed h5ad files
    - loads ``adata.X`` fully into memory once
    - aligns AnnData rows to MERFISH cell metadata once
    - subsets rows/columns only after the matrix is in memory
    - precomputes image voxel indices once
    - optionally processes/saves multiple requested genes in parallel with threads

Usage:
------
    # Selected genes
    abca_merfish_expression_to_nii -b <abc_download_root> -g <gene> [<gene> ...] \
        -r <ref_nii> [-n] [-o <output>] [-im] [-w <workers>] [-f] [-v]

    # All genes in the selected MERFISH dataset
    abca_merfish_expression_to_nii -b <abc_download_root> -r <ref_nii> [-n] [-im] [-w <workers>] [-f] [-v]

Notes:
------
    - ``-w`` uses threads, not processes, to avoid duplicating the loaded expression matrix.
    - Each worker still creates one full 3D output image in memory, so keep ``-w`` modest.
"""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import anndata
import nibabel as nib
import numpy as np
import pandas as pd
from rich import print
from rich.live import Live
from rich.traceback import install
from scipy import sparse as sp_sparse

import unravel.allen_institute.abca.merfish.merfish as mf
from unravel.core.config import Configuration
from unravel.core.help_formatter import SM, RichArgumentParser, SuppressMetavar
from unravel.core.utils import (
    initialize_progress_bar,
    log_command,
    verbose_end_msg,
    verbose_start_msg,
)


@dataclass(frozen=True)
class GeneJobResult:
    gene: str
    output_path: Path
    nonzero_cells: int
    expression_sum: float


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument("-b", "--base", 
                      help="Path to the root directory of the Allen Brain Cell Atlas data", 
                      required=True, action=SM)
    reqs.add_argument("-g", "--gene", 
                      help="Gene(s) to convert. If omitted, all genes in the selected MERFISH dataset are processed.",
                      required=False, nargs="*", default=None, action=SM)
    reqs.add_argument("-r", "--ref_nii", 
                      help=("Path to reference .nii.gz for header/affine/shape info "
                            "(e.g., image_volumes/MERFISH-C57BL6J-638850-CCF/20230630/resampled_annotation.nii.gz)"),
                      required=True, action=SM)

    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument("-n", "--neurons", 
                      help="Filter out non-neuronal cells. Default: False", 
                      action="store_true", default=False)
    opts.add_argument("-o", "--output",
                      help=("Output path for the saved .nii.gz image. Only valid with one gene. "
                            r"Default: \[imputed_]MERFISH[_neuronal]_expression_maps/<gene>.nii.gz" ),
                      default=None, action=SM)
    opts.add_argument("-im", "--imputed", 
                      help="Use imputed expression data. Default: False", 
                      action="store_true", default=False)
    opts.add_argument("--h5ad", 
                      help="Optional expression .h5ad path. If given, bypass mf.load_expression_data().", 
                      default=None, action=SM)
    opts.add_argument("-w", "--workers", 
                      help="Number of genes to process/save in parallel. Default: 16", 
                      type=int, default=16, action=SM)
    opts.add_argument("-f", "--force", 
                      help="Overwrite existing outputs. Default: False", 
                      action="store_true", default=False)
    opts.add_argument("-dt", "--dtype", 
                      help="Output dtype. Default: float32", choices=["float32", "float64"], 
                      default="float32", action=SM)
    opts.add_argument("--dense", 
                      help=("In-memory expression matrix --> dense NumPy array after row/gene subsetting. "
                            "Default: keep sparse matrices sparse. Use only if RAM is sufficient." ),
                      action="store_true", default=False)
    opts.add_argument("--no-csc",
                      help=("Do not convert sparse matrices to CSC after row/gene subsetting. "
                            "Default: convert to CSC for faster repeated gene-column extraction." ),
                      action="store_true", default=False)

    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose",
                         help="Increase verbosity. Default: False", action="store_true", default=False)

    return parser.parse_args()


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    """Return unique strings while preserving first occurrence order."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        value = str(value)
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def get_requested_genes_from_args(args) -> tuple[list[str], bool]:
    """Return requested genes and whether the user omitted -g/--gene.

    When ``-g`` is omitted, use the curated ABCA MERFISH gene-list helpers from
    ``merfish.py``. These lists let us build output paths and skip existing files
    before loading the large expression matrix. The final list is still validated
    against ``adata.var`` after AnnData is loaded.
    """
    if args.gene:
        return unique_preserve_order(args.gene), False

    if args.imputed:
        if hasattr(mf, "genes_in_imputed_merfish_data"):
            return unique_preserve_order(mf.genes_in_imputed_merfish_data()), True
        raise AttributeError(
            "-g/--gene was omitted with --imputed, but mf.genes_in_imputed_merfish_data() "
            "is not available. Provide -g explicitly or update merfish.py."
        )

    if hasattr(mf, "genes_in_merfish_data"):
        return unique_preserve_order(mf.genes_in_merfish_data()), True

    raise AttributeError(
        "-g/--gene was omitted, but mf.genes_in_merfish_data() is not available. "
        "Provide -g explicitly or update merfish.py."
    )


def format_gene_preview(genes: list[str], max_genes: int = 20) -> str:
    """Return a compact gene-list preview for console output."""
    if len(genes) <= max_genes:
        return ", ".join(genes)
    preview = ", ".join(genes[:max_genes])
    return f"{preview}, ... ({len(genes):,} total)"


def find_expression_h5ad(download_base: Path, imputed: bool, verbose: bool = False) -> Path | None:
    """Try to find the ABCA MERFISH expression h5ad without using backed subsetting.

    This lets the script bypass ``mf.load_expression_data()``, which may subset a
    CSRDataset-backed h5ad before loading it into memory. The selected AnnData is
    opened backed/read-only, then ``adata.X`` is loaded fully into memory later.
    """
    download_base = Path(download_base)

    # Fast path: common files are often placed directly under the MERFISH root.
    direct_candidates = list(download_base.glob("*.h5ad"))

    # If direct lookup fails, do a recursive search. This usually finds only a few
    # expression-matrix files, but keep it as a fallback in case the ABCA cache
    # layout changes.
    candidates = direct_candidates
    if not candidates:
        if verbose:
            print("    No .h5ad files found directly under base; searching recursively...")
        candidates = list(download_base.rglob("*.h5ad"))

    if not candidates:
        return None

    def rank(path: Path) -> tuple[int, str]:
        name = path.name.lower()
        is_imputed = ("imput" in name)
        if imputed:
            # Prefer explicitly imputed h5ad files.
            return (0 if is_imputed else 10, str(path))

        # Non-imputed default: prefer log2 expression over raw, and avoid imputed.
        if is_imputed:
            primary = 20
        elif "log2" in name or "log" in name:
            primary = 0
        elif "raw" in name:
            primary = 5
        else:
            primary = 2
        return (primary, str(path))

    candidates = sorted(candidates, key=rank)
    selected = candidates[0]

    if imputed and "imput" not in selected.name.lower():
        return None

    if verbose:
        print(f"    Selected h5ad: {selected}")
        if len(candidates) > 1:
            print("    Other h5ad candidates:")
            for path in candidates[1:6]:
                print(f"      - {path}")

    return selected


def load_anndata_without_var_subsetting(download_base: Path, args, requested_genes: list[str]):
    """Load AnnData backed/read-only without subsetting variables first."""
    if args.h5ad:
        h5ad_path = Path(args.h5ad)
        print(f"\nLoading AnnData from explicit h5ad path: {h5ad_path}")
        return anndata.read_h5ad(h5ad_path, backed="r")

    h5ad_path = find_expression_h5ad(download_base, imputed=args.imputed, verbose=args.verbose)
    if h5ad_path is not None:
        print(f"\nLoading AnnData without backed variable subsetting: {h5ad_path}")
        return anndata.read_h5ad(h5ad_path, backed="r")

    # Fallback for unusual ABCA layouts. This preserves compatibility with the
    # existing UNRAVEL helper, but the auto-h5ad path above is preferred because
    # it avoids CSRDataset-backed subsetting before the matrix is loaded.
    print("\nCould not auto-detect an expression .h5ad; falling back to mf.load_expression_data().")
    print("If this fails with a CSRDataset subsetting error, rerun with --h5ad /path/to/expression.h5ad.")
    return mf.load_expression_data(download_base, requested_genes, imputed=args.imputed)


def default_output_path(gene: str, args, n_requested_genes: int) -> Path:
    """Return the default output path for one gene."""
    if args.output:
        if n_requested_genes > 1:
            raise ValueError("--output can only be used when one gene is requested.")
        return Path(args.output)

    if args.imputed and args.neurons:
        return Path.cwd() / "imputed_MERFISH_neuronal_expression_maps" / f"{gene}_imputed_neurons.nii.gz"
    if args.imputed:
        return Path.cwd() / "imputed_MERFISH_expression_maps" / f"{gene}_imputed.nii.gz"
    if args.neurons:
        return Path.cwd() / "MERFISH_neuronal_expression_maps" / f"{gene}_neurons.nii.gz"
    return Path.cwd() / "MERFISH_expression_maps" / f"{gene}.nii.gz"


def get_var_symbols(adata) -> np.ndarray:
    """Return gene symbols aligned to ``adata.var`` columns."""
    if "gene_symbol" in adata.var.columns:
        return adata.var["gene_symbol"].astype(str).to_numpy()
    return adata.var_names.astype(str).to_numpy()


def get_gene_to_cols(adata, requested_genes: list[str]) -> dict[str, list[int]]:
    """Map requested gene symbols to integer column positions in ``adata.X``."""
    symbols = get_var_symbols(adata)
    gene_to_cols: dict[str, list[int]] = {}
    for gene in requested_genes:
        gene_to_cols[gene] = np.flatnonzero(symbols == gene).astype(int).tolist()
    return gene_to_cols


def load_and_prepare_cell_metadata(download_base: Path, neurons: bool) -> pd.DataFrame:
    """Load MERFISH cell metadata, add reconstructed coords, and optionally keep neurons only."""
    cell_df = mf.load_cell_metadata(download_base)
    cell_df_joined = mf.join_reconstructed_coords(cell_df, download_base)

    if neurons:
        cell_df_joined = mf.join_cluster_details(cell_df_joined, download_base)
        class_num = cell_df_joined["class"].str.split().str[0].astype(int)
        cell_df_joined = cell_df_joined[class_num <= 29].copy()

    return cell_df_joined


def infer_cell_id_column(cell_df: pd.DataFrame, obs_names: pd.Index) -> tuple[pd.Series, str, int]:
    """
    Infer which cell metadata field matches AnnData obs_names best.

    The original ABCA metadata generally uses cell labels as the index, but this keeps
    the script robust if future exports expose them as a column instead.
    """
    candidates: list[tuple[str, pd.Series]] = [("index", pd.Series(cell_df.index.astype(str), index=cell_df.index))]
    for col in ["cell_label", "feature_matrix_label", "cell_barcode", "barcoded_cell_sample_label"]:
        if col in cell_df.columns:
            candidates.append((col, cell_df[col].astype(str)))

    best_name = "index"
    best_series = candidates[0][1]
    best_overlap = -1
    obs_set = set(obs_names.astype(str))

    for name, series in candidates:
        overlap = int(series.isin(obs_set).sum())
        if overlap > best_overlap:
            best_name = name
            best_series = series
            best_overlap = overlap

    return best_series.astype(str), best_name, best_overlap


def align_cells_to_adata(cell_df: pd.DataFrame, adata) -> tuple[pd.DataFrame, np.ndarray, str]:
    """
    Align cell metadata to AnnData row order without subsetting backed AnnData.

    Returns
    -------
    aligned_cell_df : DataFrame
        Metadata rows in the same order as ``adata.X[row_indices, :]``.
    row_indices : ndarray[int]
        Integer AnnData row indices to keep.
    id_source : str
        Metadata field used for matching.
    """
    obs_names = pd.Index(adata.obs_names.astype(str))
    cell_ids, id_source, overlap = infer_cell_id_column(cell_df, obs_names)
    if overlap == 0:
        raise ValueError("No overlap between AnnData obs_names and cell metadata cell IDs.")

    indexed = cell_df.copy()
    indexed["_merfish_cell_id"] = cell_ids.to_numpy()
    indexed = indexed.drop_duplicates("_merfish_cell_id", keep="first").set_index("_merfish_cell_id", drop=False)

    keep_mask = obs_names.isin(indexed.index)
    row_indices = np.flatnonzero(keep_mask).astype(np.int64)
    aligned_obs_names = obs_names[keep_mask]
    aligned_cell_df = indexed.reindex(aligned_obs_names).copy()

    if aligned_cell_df.isna().all(axis=None):
        raise ValueError("Cell metadata alignment failed; aligned metadata is all NA.")

    return aligned_cell_df, row_indices, id_source


def precompute_linear_indices(
    cell_df: pd.DataFrame,
    shape: tuple[int, int, int],
    pixel_size_um: float,
) -> tuple[np.ndarray, np.ndarray, str]:
    """
    Convert reconstructed MERFISH coordinates to flattened image indices once.

    This mirrors ``mf.points_to_img_sum`` style accumulation, but does it in 3D:
        img[int(x / pixel_size), int(y / pixel_size), z_index] += expression
    """
    required = ["x_reconstructed", "y_reconstructed", "brain_section_label"]
    missing = [col for col in required if col not in cell_df.columns]
    if missing:
        raise KeyError(f"Cell metadata is missing required column(s): {missing}")

    pixel_size_coord_units = pixel_size_um / 1000.0
    slice_index_map = mf.slice_index_dict()

    # Original mf.points_to_img_sum likely uses astype(int), i.e. truncation toward zero.
    i = (cell_df["x_reconstructed"].to_numpy(dtype=np.float64) / pixel_size_coord_units).astype(np.int64)
    j = (cell_df["y_reconstructed"].to_numpy(dtype=np.float64) / pixel_size_coord_units).astype(np.int64)
    k_series = cell_df["brain_section_label"].map(slice_index_map)
    k = k_series.to_numpy(dtype=float)

    finite_k = np.isfinite(k)
    k_int = np.zeros_like(i, dtype=np.int64)
    k_int[finite_k] = k[finite_k].astype(np.int64)

    in_bounds = (
        finite_k
        & (i >= 0) & (i < shape[0])
        & (j >= 0) & (j < shape[1])
        & (k_int >= 0) & (k_int < shape[2])
    )

    if not np.any(in_bounds):
        raise ValueError("No cells have valid in-bounds x/y/z coordinates for the reference image shape.")

    linear_idx = np.ravel_multi_index((i[in_bounds], j[in_bounds], k_int[in_bounds]), dims=shape)
    return linear_idx.astype(np.int64, copy=False), in_bounds


def load_X_fully_into_memory(adata):
    """
    Load ``adata.X`` into memory once, avoiding backed slicing/subsetting.

    For AnnData CSRDataset/CSCDataset, ``to_memory()`` should return a scipy sparse
    matrix. Fallbacks cover older anndata/scipy combinations.
    """
    X = adata.X
    print(f"\nLoading full expression matrix into memory from {type(X).__name__}...")

    if hasattr(X, "to_memory"):
        X_mem = X.to_memory()
    else:
        try:
            X_mem = X[:]
        except Exception:
            X_mem = np.asarray(X)

    if sp_sparse.issparse(X_mem):
        print(f"    Loaded sparse matrix: shape={X_mem.shape}, nnz={X_mem.nnz:,}, format={X_mem.getformat()}")
    else:
        print(f"    Loaded dense/array-like matrix: shape={getattr(X_mem, 'shape', None)}")

    return X_mem


def subset_matrix_after_memory_load(
    X,
    row_indices: np.ndarray,
    valid_cell_mask: np.ndarray,
    gene_to_cols: dict[str, list[int]],
    genes_to_process: list[str],
    dense: bool,
    convert_to_csc: bool,
):
    """Subset rows/columns after full in-memory load and return local gene-column mapping."""
    all_cols: list[int] = []
    for gene in genes_to_process:
        all_cols.extend(gene_to_cols[gene])
    all_cols = [int(c) for c in unique_preserve_order(all_cols)]
    old_to_new = {old: new for new, old in enumerate(all_cols)}
    local_gene_to_cols = {gene: [old_to_new[c] for c in gene_to_cols[gene]] for gene in genes_to_process}

    print("    Subsetting in-memory matrix to aligned/valid cells and requested genes...")
    X = X[row_indices, :]
    X = X[valid_cell_mask, :]
    X = X[:, all_cols]

    if dense:
        if sp_sparse.issparse(X):
            print("    Converting requested expression subset to dense array...")
            X = X.toarray()
        else:
            X = np.asarray(X)
    elif convert_to_csc and sp_sparse.issparse(X) and X.getformat() != "csc":
        print("    Converting sparse requested expression subset to CSC for faster column extraction...")
        X = X.tocsc(copy=False)

    if sp_sparse.issparse(X):
        print(f"    Working matrix: shape={X.shape}, nnz={X.nnz:,}, format={X.getformat()}\n")
    else:
        print(f"    Working matrix: shape={X.shape}, dtype={getattr(X, 'dtype', None)}\n")

    return X, local_gene_to_cols


def get_gene_values(X, cols: list[int], dtype: np.dtype) -> np.ndarray:
    """Return a dense 1D expression vector for one gene from the working matrix."""
    if sp_sparse.issparse(X):
        if len(cols) == 1:
            values = X[:, cols[0]]
        else:
            values = X[:, cols].sum(axis=1)
        values = np.asarray(values.toarray()).ravel()
    else:
        if len(cols) == 1:
            values = np.asarray(X[:, cols[0]]).ravel()
        else:
            values = np.asarray(X[:, cols]).sum(axis=1).ravel()

    return values.astype(dtype, copy=False)


def expression_values_to_img(values: np.ndarray, linear_idx: np.ndarray, shape: tuple[int, int, int], dtype: np.dtype) -> np.ndarray:
    """Accumulate per-cell expression values into a 3D image."""
    img_flat = np.zeros(int(np.prod(shape)), dtype=dtype)

    # Skip zeros; this matters for sparse gene expression.
    nonzero = values != 0
    if np.any(nonzero):
        np.add.at(img_flat, linear_idx[nonzero], values[nonzero])

    return img_flat.reshape(shape)


def save_nii(img: np.ndarray, affine: np.ndarray, header, output_path: Path, dtype: np.dtype) -> None:
    """Save image with reference affine/header and a floating output dtype."""
    header = header.copy()
    header.set_data_dtype(dtype)
    nii_img = nib.Nifti1Image(img.astype(dtype, copy=False), affine=affine, header=header)
    nib.save(nii_img, str(output_path))


def process_gene_job(
    gene: str,
    X,
    gene_to_cols: dict[str, list[int]],
    linear_idx: np.ndarray,
    shape: tuple[int, int, int],
    dtype: np.dtype,
    affine: np.ndarray,
    header,
    output_path: Path,
) -> GeneJobResult:
    """Build and save one gene image from the shared in-memory expression matrix."""
    values = get_gene_values(X, cols=gene_to_cols[gene], dtype=dtype)
    nonzero_cells = int(np.count_nonzero(values))
    expression_sum = float(np.sum(values, dtype=np.float64))
    img = expression_values_to_img(values, linear_idx=linear_idx, shape=shape, dtype=dtype)
    save_nii(img, affine=affine, header=header, output_path=output_path, dtype=dtype)
    return GeneJobResult(gene=gene, output_path=output_path, nonzero_cells=nonzero_cells, expression_sum=expression_sum)


def run_gene_jobs(
    genes_to_process: list[str],
    X,
    gene_to_cols: dict[str, list[int]],
    linear_idx: np.ndarray,
    shape: tuple[int, int, int],
    dtype: np.dtype,
    affine: np.ndarray,
    header,
    output_paths: dict[str, Path],
    workers: int,
    verbose: bool,
) -> list[GeneJobResult]:
    """Run gene image construction/saving sequentially or in a thread pool."""
    workers = max(1, min(int(workers), len(genes_to_process)))
    results: list[GeneJobResult] = []

    if workers == 1:
        for gene in genes_to_process:
            print(f"    Processing gene: {gene}")
            result = process_gene_job(
                gene=gene,
                X=X,
                gene_to_cols=gene_to_cols,
                linear_idx=linear_idx,
                shape=shape,
                dtype=dtype,
                affine=affine,
                header=header,
                output_path=output_paths[gene],
            )
            results.append(result)
            if verbose:
                print(f"        nonzero cells={result.nonzero_cells:,}; expression sum={result.expression_sum:g}")
            print(f"        Saved image to {result.output_path}\n")
        return results

    print(f"\nProcessing/saving {len(genes_to_process)} gene(s) with {workers} worker threads...")

    lock = Lock()

    def wrapped(gene: str) -> GeneJobResult:
        result = process_gene_job(
            gene=gene,
            X=X,
            gene_to_cols=gene_to_cols,
            linear_idx=linear_idx,
            shape=shape,
            dtype=dtype,
            affine=affine,
            header=header,
            output_path=output_paths[gene],
        )
        return result

    progress, task_id = initialize_progress_bar(len(genes_to_process), task_message="[bold green]Making MERFISH expression maps...")
    with Live(progress):
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(wrapped, gene): gene for gene in genes_to_process}
            for future in as_completed(futures):
                result = future.result()
                with lock:
                    progress.update(task_id, advance=1)
                results.append(result)
                if verbose:
                    print(f"    {result.gene}: nonzero cells={result.nonzero_cells:,}; expression sum={result.expression_sum:g}")
                print(f"    Saved image to {result.output_path}")

    # Preserve input order in returned results.
    result_by_gene = {result.gene: result for result in results}
    return [result_by_gene[gene] for gene in genes_to_process if gene in result_by_gene]


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)
    requested_genes, processing_all_genes = get_requested_genes_from_args(args)
    dtype = np.dtype(args.dtype)

    if processing_all_genes:
        print(f"\n-g/--gene was omitted; processing all selected MERFISH genes: {len(requested_genes):,}")
    else:
        print(f"\nRequested genes: {format_gene_preview(requested_genes)}")

    if args.output and len(requested_genes) > 1:
        raise ValueError("--output can only be used when one gene is requested. Omit -o when processing all genes.")
    if args.workers < 1:
        raise ValueError("--workers must be >= 1.")

    # Load reference once and use its shape rather than hard-coding 1100 x 1100 x 76.
    ref_nii = nib.load(args.ref_nii)
    shape = tuple(int(x) for x in ref_nii.shape[:3])
    affine = ref_nii.affine.copy()
    header = ref_nii.header.copy()
    print(f"\nReference image shape: {shape}\n")

    # Build output paths up front and skip already-existing images before loading expression data.
    output_paths: dict[str, Path] = {}
    genes_to_process: list[str] = []
    for gene in requested_genes:
        out = default_output_path(gene, args, n_requested_genes=len(requested_genes))
        out.parent.mkdir(parents=True, exist_ok=True)
        output_paths[gene] = out
        if out.exists() and not args.force:
            print(f"    Output file already exists, skipping: {out}")
        else:
            genes_to_process.append(gene)

    if not genes_to_process:
        print("\nAll requested outputs already exist.\n")
        verbose_end_msg()
        return

    # Load metadata once.
    cell_df = load_and_prepare_cell_metadata(download_base, neurons=args.neurons)
    if args.verbose:
        print("\nColumns in cell metadata:")
        print(cell_df.columns)
        print(f"\nCells after metadata/neuron filtering: {len(cell_df):,}")

    # Load AnnData once. Avoid adata[...] backed variable subsetting later.
    adata = load_anndata_without_var_subsetting(download_base, args, requested_genes=genes_to_process)

    # Validate genes against selected dataset.
    gene_to_cols = get_gene_to_cols(adata, genes_to_process)
    missing_genes = [gene for gene in genes_to_process if not gene_to_cols[gene]]
    if missing_genes:
        print(f"\nSkipping {len(missing_genes)} gene(s) not found in the selected expression dataset:")
        print(missing_genes)
    genes_to_process = [gene for gene in genes_to_process if gene_to_cols[gene]]

    if not genes_to_process:
        print("\nNo requested genes were found in the selected expression dataset.\n")
        verbose_end_msg()
        return

    # Align metadata to AnnData row order, still without subsetting backed X.
    aligned_cell_df, row_indices, id_source = align_cells_to_adata(cell_df, adata)
    print(f"\nAligned cells: {len(row_indices):,} using metadata field: {id_source}")

    # Precompute coordinates once before matrix row/gene subsetting.
    linear_idx, valid_cell_mask = precompute_linear_indices(
        aligned_cell_df,
        shape=shape,
        pixel_size_um=10, # MERFISH in-plane pixel size in microns
        coord_unit="mm",
    )
    valid_count = int(valid_cell_mask.sum())
    print(f"    Coordinate unit used: mm")
    print(f"    Cells with valid image coordinates: {valid_count:,} / {len(valid_cell_mask):,}\n")

    # Load full X into memory once, then subset in memory.
    X_full = load_X_fully_into_memory(adata)
    X_work, local_gene_to_cols = subset_matrix_after_memory_load(
        X=X_full,
        row_indices=row_indices,
        valid_cell_mask=valid_cell_mask,
        gene_to_cols=gene_to_cols,
        genes_to_process=genes_to_process,
        dense=args.dense,
        convert_to_csc=not args.no_csc,
    )
    del X_full

    print(f"Processing {len(genes_to_process):,} gene(s): {format_gene_preview(genes_to_process)}\n")
    if args.workers > 1:
        bytes_per_img = int(np.prod(shape)) * np.dtype(dtype).itemsize
        print(
            "[yellow]Note:[/yellow] each worker creates one full output image in memory "
            f"(~{bytes_per_img / 1024**2:.1f} MiB per worker for {args.dtype}).\n"
        )

    run_gene_jobs(
        genes_to_process=genes_to_process,
        X=X_work,
        gene_to_cols=local_gene_to_cols,
        linear_idx=linear_idx,
        shape=shape,
        dtype=dtype,
        affine=affine,
        header=header,
        output_paths=output_paths,
        workers=args.workers,
        verbose=args.verbose,
    )

    verbose_end_msg()


if __name__ == "__main__":
    main()
