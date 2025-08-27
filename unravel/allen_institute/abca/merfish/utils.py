#!/usr/bin/env python3
"""
Utilities for processing Allen Brain Cell Atlas (ABCA) MERFISH cells metadata and visualizing a brain slice with cells or gene expression data.
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterable, Literal, Tuple

import numpy as np
import pandas as pd
import nibabel as nib
import matplotlib.pyplot as plt

# Optional; only needed for expression-related functions
try:
    import anndata 
except Exception:  
    anndata = None 


def filter_neurons(cell_df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter cells to neuronal classes (class index ≤ 29), based on integer prefix of 'class'.
    """
    if "class" not in cell_df.columns:
        raise ValueError("Cannot filter neurons: 'class' column not found.")
    try:
        class_idx = cell_df["class"].astype(str).str.split().str[0].astype(int)
        return cell_df[class_idx <= 29]
    except Exception as e:
        raise ValueError(f"Failed to parse 'class' column as integers: {e}")

# ----------------------------- core joins -------------------------------------

def load_cell_metadata(download_base_or_file: Path | str) -> pd.DataFrame:
    """Load MERFISH cell metadata (index: cell_label)."""
    p = Path(download_base_or_file)
    if p.is_file():
        cell_metadata_path = p
    else:
        cell_metadata_path = (
            Path(p) / "metadata/MERFISH-C57BL6J-638850/20231215/cell_metadata.csv"
        )
    df = pd.read_csv(cell_metadata_path, dtype={"cell_label": str})
    df.rename(columns={"x": "x_section", "y": "y_section", "z": "z_section"}, inplace=True)
    df.set_index("cell_label", inplace=True)
    return df


def join_reconstructed_coords(cell_df: pd.DataFrame, download_base: Path | str) -> pd.DataFrame:
    """Join reconstructed coordinates + parcellation_index."""
    if {"x_reconstructed", "y_reconstructed", "z_reconstructed", "parcellation_index"}.issubset(
        cell_df.columns
    ):
        return cell_df
    p = (
        Path(download_base)
        / "metadata/MERFISH-C57BL6J-638850-CCF/20231215/reconstructed_coordinates.csv"
    )
    rc = (
        pd.read_csv(p, dtype={"cell_label": str})
        .rename(
            columns={"x": "x_reconstructed", "y": "y_reconstructed", "z": "z_reconstructed"}
        )
        .set_index("cell_label")
    )
    return cell_df.join(rc, how="inner")


def join_cluster_details(cell_df: pd.DataFrame, download_base: Path | str,
                         species: Literal["mouse", "human"] = "mouse") -> pd.DataFrame:
    """Join cluster annotations (class/subclass/etc.)."""
    if {"class", "subclass", "cluster_alias"}.issubset(cell_df.columns):
        return cell_df
    if species != "mouse":
        raise ValueError("Only 'mouse' supported; extend as needed.")
    p = (
        Path(download_base)
        / "metadata/WMB-taxonomy/20231215/views/cluster_to_cluster_annotation_membership_pivoted.csv"
    )
    ann = pd.read_csv(p).set_index("cluster_alias")
    return cell_df.join(ann, on="cluster_alias")


def join_cluster_colors(cell_df: pd.DataFrame, download_base: Path | str,
                        species: Literal["mouse", "human"] = "mouse") -> pd.DataFrame:
    """Join cluster color columns."""
    expected = {
        "neurotransmitter_color",
        "class_color",
        "subclass_color",
        "supertype_color",
        "cluster_color",
    }
    if expected.issubset(cell_df.columns):
        return cell_df
    if species != "mouse":
        raise ValueError("Only 'mouse' supported; extend as needed.")
    p = (
        Path(download_base)
        / "metadata/WMB-taxonomy/20231215/views/cluster_to_cluster_annotation_membership_color.csv"
    )
    col = pd.read_csv(p).set_index("cluster_alias")
    return cell_df.join(col, on="cluster_alias")


def join_parcellation_annotation(cell_df: pd.DataFrame, download_base: Path | str) -> pd.DataFrame:
    """Join parcellation term acronyms."""
    if {"parcellation_structure", "parcellation_substructure"}.issubset(cell_df.columns):
        return cell_df
    p = (
        Path(download_base)
        / "metadata/Allen-CCF-2020/20230630/views/parcellation_to_parcellation_term_membership_acronym.csv"
    )
    ann = pd.read_csv(p).set_index("parcellation_index")
    ann.columns = [f"parcellation_{c}" for c in ann.columns]
    return cell_df.join(ann, on="parcellation_index")


def join_parcellation_color(cell_df: pd.DataFrame, download_base: Path | str) -> pd.DataFrame:
    """Join parcellation color columns."""
    expected = {"parcellation_structure_color", "parcellation_substructure_color"}
    if expected.issubset(cell_df.columns):
        return cell_df
    p = (
        Path(download_base)
        / "metadata/Allen-CCF-2020/20230630/views/parcellation_to_parcellation_term_membership_color.csv"
    )
    col = pd.read_csv(p).set_index("parcellation_index")
    col.columns = [f"parcellation_{c}" for c in col.columns]
    return cell_df.join(col, on="parcellation_index")


def filter_brain_section(cell_df: pd.DataFrame, slice_index: int) -> pd.DataFrame:
    """Subset to a single-section label by numeric slice index."""
    return cell_df[cell_df["brain_section_label"] == f"C57BL6J-638850.{slice_index}"]


# -------------------------- expression helpers --------------------------------

def load_expression_data(download_base: Path | str, imputed: bool = False):
    """Open the (imputed or raw) log2 expression matrix .h5ad (backed='r')."""
    if anndata is None:
        raise ImportError("Please install `anndata` to enable gene-expression plots.")
    base = Path(download_base)
    path = (
        base / "expression_matrices/MERFISH-C57BL6J-638850-imputed/20240831/C57BL6J-638850-imputed-log2.h5ad"
        if imputed
        else base / "expression_matrices/MERFISH-C57BL6J-638850/20230830/C57BL6J-638850-log2.h5ad"
    )
    return anndata.read_h5ad(path, backed="r")


def select_gene(adata, gene: str):
    """Return (adata_subset_in_memory, gene_symbol) for a single gene."""
    sym = adata.var.get("gene_symbol", adata.var_names)
    mask = [g == gene for g in sym]
    if not any(mask):
        raise ValueError(f"Gene '{gene}' not found.")
    sub = adata[:, np.where(mask)[0]].to_memory()
    gene_symbol = str(sym[np.where(mask)[0][0]])
    return sub, gene_symbol


def join_expression_to_section(adata_sub, gene_symbol: str, section_df: pd.DataFrame) -> pd.DataFrame:
    """Join single-gene expression to a section-level metadata table by cell_label."""
    gdf = adata_sub.to_df()
    gdf.columns = [gene_symbol]
    return section_df.join(gdf, how="inner")


def genes_in_merfish_data(download_base: Path | str) -> list[str]:
    """Return list of gene symbols in the raw MERFISH log2 matrix."""
    ad = load_expression_data(download_base, imputed=False)
    return list(ad.var.get("gene_symbol", ad.var_names))


def genes_in_imputed_merfish_data(download_base: Path | str) -> list[str]:
    """Return list of gene symbols in the imputed MERFISH log2 matrix."""
    ad = load_expression_data(download_base, imputed=True)
    return list(ad.var.get("gene_symbol", ad.var_names))


# ------------------------------ one-call pipeline -----------------------------

def prepare_cells_table(download_base: Path | str,
                        species: Literal["mouse", "human"] = "mouse",
                        include: Iterable[str] = ("coords", "cluster", "colors", "parcellation", "parcellation_color")) -> pd.DataFrame:
    """
    Run the frequent sequence of joins and return a fully enriched cell table.

    include flags:
      'coords' → reconstructed coords + parcellation_index
      'cluster' → cluster annotations (class/subclass/etc.)
      'colors' → cluster colors
      'parcellation' → parcellation term acronyms
      'parcellation_color' → parcellation colors
    """
    df = load_cell_metadata(download_base)
    if "coords" in include:
        df = join_reconstructed_coords(df, download_base)
    if "cluster" in include:
        df = join_cluster_details(df, download_base, species=species)
    if "colors" in include:
        df = join_cluster_colors(df, download_base, species=species)
    if "parcellation" in include:
        df = join_parcellation_annotation(df, download_base)
    if "parcellation_color" in include:
        df = join_parcellation_color(df, download_base)
    return df

def build_neuron_subset(base: "Path"):
    """
    Return a metadata dataframe subset containing ONLY neurons
    (rows where the integer prefix of the 'class' column <= 29)

    Notes:
      - Requires a 'class' column like '12 IT-L2/3 ...'.
      - Adds the standard joins so downstream plotting has colors and labels.
    """
    import pandas as pd

    df = load_cell_metadata(base)
    df = join_reconstructed_coords(df, base)
    df = join_cluster_details(df, base)
    df = join_cluster_colors(df, base)
    df = join_parcellation_annotation(df, base)
    df = join_parcellation_color(df, base)

    if "class" not in df.columns:
        return None

    # Parse the integer code at the start of 'class'
    try:
        class_idx = df["class"].astype(str).str.split().str[0].astype(int)
    except Exception as e:
        raise ValueError(f"Failed to parse 'class' column as integers: {e}")

    neuron_mask = class_idx <= 29
    subset = df.loc[neuron_mask].copy()
    return subset if not subset.empty else None



# ------------------------------ plotting helpers ------------------------------

def slice_index_dict() -> dict[str, int]:
    """
    Mapping from brain section labels (e.g. 'C57BL6J-638850.40')
    to corresponding slice indices in the 3D boundary volume.

    Returns
    -------
    dict
        Keys are section labels, values are z indices.
    """
    return {
        "C57BL6J-638850.05": 4,
        "C57BL6J-638850.06": 5,
        "C57BL6J-638850.08": 7,
        "C57BL6J-638850.09": 8,
        "C57BL6J-638850.10": 9,
        "C57BL6J-638850.11": 10,
        "C57BL6J-638850.12": 11,
        "C57BL6J-638850.13": 12,
        "C57BL6J-638850.14": 13,
        "C57BL6J-638850.15": 14,
        "C57BL6J-638850.16": 15,
        "C57BL6J-638850.17": 16,
        "C57BL6J-638850.18": 17,
        "C57BL6J-638850.19": 18,
        "C57BL6J-638850.24": 19,
        "C57BL6J-638850.25": 20,
        "C57BL6J-638850.26": 21,
        "C57BL6J-638850.27": 22,
        "C57BL6J-638850.28": 23,
        "C57BL6J-638850.29": 24,
        "C57BL6J-638850.30": 25,
        "C57BL6J-638850.31": 27,
        "C57BL6J-638850.32": 28,
        "C57BL6J-638850.33": 29,
        "C57BL6J-638850.35": 31,
        "C57BL6J-638850.36": 32,
        "C57BL6J-638850.37": 33,
        "C57BL6J-638850.38": 34,
        "C57BL6J-638850.39": 35,
        "C57BL6J-638850.40": 36,
        "C57BL6J-638850.42": 38,
        "C57BL6J-638850.43": 39,
        "C57BL6J-638850.44": 40,
        "C57BL6J-638850.45": 41,
        "C57BL6J-638850.46": 42,
        "C57BL6J-638850.47": 44,
        "C57BL6J-638850.48": 45,
        "C57BL6J-638850.49": 46,
        "C57BL6J-638850.50": 47,
        "C57BL6J-638850.51": 48,
        "C57BL6J-638850.52": 49,
        "C57BL6J-638850.54": 51,
        "C57BL6J-638850.55": 52,
        "C57BL6J-638850.56": 54,
        "C57BL6J-638850.57": 55,
        "C57BL6J-638850.58": 56,
        "C57BL6J-638850.59": 57,
        "C57BL6J-638850.60": 59,
        "C57BL6J-638850.61": 60,
        "C57BL6J-638850.62": 61,
        "C57BL6J-638850.64": 65,
        "C57BL6J-638850.66": 69,
        "C57BL6J-638850.67": 71,
    }

def load_region_boundaries(download_base: Path | str) -> Tuple[np.ndarray, Tuple[float, float, float, float]]:
    """
    Load the boundary NIfTI and return (array[z,y,x], extent) suitable for imshow.
    """
    p = (
        Path(download_base)
        / "image_volumes/MERFISH-C57BL6J-638850-CCF/20230630/resampled_annotation_boundary.nii.gz"
    )
    img = nib.load(str(p))
    data = img.get_fdata().astype(np.float32)
    # Build imshow extent from affine
    aff = img.affine
    x0, y0, _ = aff[:3, 3]
    sx, sy = float(abs(aff[0, 0])), float(abs(aff[1, 1]))
    nx, ny, _ = img.shape
    extent = (x0 - 0.5 * sx, x0 + (nx - 0.5) * sx, y0 + (ny - 0.5) * sy, y0 - 0.5 * sy)
    # Reorder to [z,y,x]
    data = np.moveaxis(data, [0, 1, 2], [2, 1, 0])
    return data, extent

# def load_region_boundaries(download_base):
#     """
#     Load the region boundaries from the MERFISH data.

#     Parameters:
#     -----------
#     download_base : Path
#         The root directory of the MERFISH data.

#     Returns:
#     --------
#     annotation_boundary_array : np.ndarray
#         The region boundaries.
#     extent : tuple
#         The extent of the image in mm coordinates for plotting with matplotlib.
#     """
#     annotation_boundary_image_path = download_base / 'image_volumes/MERFISH-C57BL6J-638850-CCF/20230630/resampled_annotation_boundary.nii.gz'
#     print(f"\n    Loading annotation boundary image from {annotation_boundary_image_path}\n")
#     annotation_boundary_image = sitk.ReadImage(annotation_boundary_image_path)
#     annotation_boundary_array = sitk.GetArrayViewFromImage(annotation_boundary_image)

#     # Compute the extent the image in mm coordinates for plotting
#     size = annotation_boundary_image.GetSize()
#     spacing = annotation_boundary_image.GetSpacing()
#     extent = (-0.5 * spacing[0], (size[0]-0.5) * spacing[0], (size[1]-0.5) * spacing[1], -0.5 * spacing[1])

    return annotation_boundary_array, extent

def auto_zoom(ax, section_df, pad: float = 0.25) -> None:
    """
    Tighten axes to the bounding box of x_reconstructed/y_reconstructed
    for the given section (plus a small padding).

    Note: y-axis is inverted (top=small y), so we set ylim with (top, bottom).
    """
    df = section_df.dropna(subset=["x_reconstructed", "y_reconstructed"])
    if df.empty:
        return
    xs = df["x_reconstructed"].to_numpy()
    ys = df["y_reconstructed"].to_numpy()

    xmin, xmax = xs.min() - pad, xs.max() + pad
    ymin, ymax = ys.min() - pad, ys.max() + pad

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymax, ymin)   # inverted y
    ax.set_aspect("equal", adjustable="box")


def plot_slice_color(
    base: Path | str,
    slice_index: int,
    color_col: str,
    *,
    s_all: float,
    s_subset: float,
    alpha_all: float,
    alpha_subset: float,
    df: "pd.DataFrame | None",   # already fully joined by caller (or None)
    neurons: bool = False,
):
    """
    Color mode: plots all cells for the slice using a categorical/hex color column,
    optionally overlays a subset, and adds boundary wireframe on top.
    """
    import matplotlib.pyplot as plt

    # 1) Build full table (coords + cluster + colors + parcellation + parcellation_color)
    all_df = prepare_cells_table(base)

    # 2) Optional neuron filter (opt-in only)
    if neurons and "class" in all_df.columns:
        try:
            class_idx = all_df["class"].astype(str).str.split().str[0].astype(int)
            all_df = all_df.loc[class_idx <= 29]
        except Exception:
            pass  # if parsing fails, fall back to unfiltered

    # 3) Slice
    all_section = filter_brain_section(all_df, slice_index)

    # 4) Boundaries
    boundary, extent = load_region_boundaries(base)
    boundary_slice = boundary[slice_index, :, :]

    # 5) Plot
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.scatter(
        all_section["x_reconstructed"],
        all_section["y_reconstructed"],
        s=s_all,
        c=all_section[color_col],
        marker=".",
        alpha=alpha_all,
        zorder=2,
    )
    ax.imshow(
        boundary_slice,
        cmap=plt.cm.Greys,
        extent=extent,
        alpha=(boundary_slice > 0).astype(float),
        zorder=3,
    )
    # 6) Optional subset overlay (larger markers / higher alpha)
    if df is not None and not df.empty:
        sub = df
        if neurons and "class" in sub.columns:
            try:
                class_idx = sub["class"].astype(str).str.split().str[0].astype(int)
                sub = sub.loc[class_idx <= 29]
            except Exception:
                pass

        subset_section = filter_brain_section(sub, slice_index)
        if not subset_section.empty:
            ax.scatter(
                subset_section["x_reconstructed"],
                subset_section["y_reconstructed"],
                s=s_subset,
                c=subset_section[color_col],
                marker=".",
                alpha=alpha_subset,
                zorder=4,
            )

    ax.set_xlim(0, 11)
    ax.set_ylim(11, 0)
    ax.axis("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    section_for_bbox = all_section if all_section is not None and not all_section.empty else subset_section
    if section_for_bbox is not None and not section_for_bbox.empty:
        auto_zoom(ax, section_for_bbox, pad=0.25)
    return fig, ax

def plot_slice_gene(
    base: Path | str,
    slice_index: int,
    gene: str,
    *,
    s_all: float,
    s_subset: float,
    alpha_all: float,
    alpha_subset: float,
    subset_df: "pd.DataFrame | None",
    imputed: bool,
    neurons: bool = False,
):
    """
    Gene mode: colors *all* cells by continuous expression (magma_r), adds a colorbar,
    optionally overlays a subset (also colored by expression), and adds the boundary wireframe.
    Highest-expressing cells are drawn last (on top).
    """
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    # 1) Build full table
    all_df = prepare_cells_table(base)

    # 2) Optional neuron filter
    if neurons and "class" in all_df.columns:
        try:
            class_idx = all_df["class"].astype(str).str.split().str[0].astype(int)
            all_df = all_df.loc[class_idx <= 29]
        except Exception:
            pass

    # 3) Load expression for the chosen gene and join
    ad = load_expression_data(base, imputed=imputed)
    ad_gene, gene_symbol = select_gene(ad, gene)
    # join to ALL cells
    all_df = join_expression_to_section(ad_gene, gene_symbol, all_df)
    all_section = filter_brain_section(all_df, slice_index)

    # 4) Boundaries
    boundary, extent = load_region_boundaries(base)
    boundary_slice = boundary[slice_index, :, :]

    # 5) Plot: continuous coloring for *all* cells (sorted so high expr on top)
    fig, ax = plt.subplots(figsize=(9, 9))
    if not all_section.empty:
        all_sorted = all_section.sort_values(by=gene_symbol, ascending=True)  # low→high
        sc = ax.scatter(
            all_sorted["x_reconstructed"],
            all_sorted["y_reconstructed"],
            s=s_all,
            c=all_sorted[gene_symbol].to_numpy(),
            cmap="magma_r",
            marker=".",
            alpha=alpha_all,
            zorder=2,
        )
        cbar = plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(f"{gene_symbol} log2 expression")

    # 6) Boundaries
    ax.imshow(
        boundary_slice,
        cmap=plt.cm.Greys,
        extent=extent,
        alpha=(boundary_slice > 0).astype(float),
        zorder=3,
    )

    # 7) Optional subset overlay (also colored by expression; high expr on top)
    subset_section = None  # ensure defined for later
    if subset_df is not None and not subset_df.empty:
        sub = subset_df
        if neurons and "class" in sub.columns:
            try:
                class_idx = sub["class"].astype(str).str.split().str[0].astype(int)
                sub = sub.loc[class_idx <= 29]
            except Exception:
                pass

        sub = join_expression_to_section(ad_gene, gene_symbol, sub)
        subset_section = filter_brain_section(sub, slice_index)
        if not subset_section.empty:
            sub_sorted = subset_section.sort_values(by=gene_symbol, ascending=True)
            ax.scatter(
                sub_sorted["x_reconstructed"],
                sub_sorted["y_reconstructed"],
                s=s_subset,
                c=sub_sorted[gene_symbol].to_numpy(),
                cmap="magma_r",
                marker=".",
                alpha=alpha_subset,
                zorder=4,
            )

    # Axes style (no fixed limits; use auto_zoom if data exists)
    ax.axis("equal")
    ax.set_xticks([])
    ax.set_yticks([])

    section_for_bbox = (
        all_section if all_section is not None and not all_section.empty else subset_section
    )
    if section_for_bbox is not None and not section_for_bbox.empty:
        auto_zoom(ax, section_for_bbox, pad=0.25)

    return fig, ax
