#!/usr/bin/env python3
"""
Use ``abca_merfish_cells_to_nii`` (``mc``) from UNRAVEL to make mouse ABCA MERFISH cell-type label images for coloring with FSLeyes LUTs.

Companion to abca_merfish_expression_to_nii; no expression matrix is loaded.
Run in the UNRAVEL environment. Reuses merfish.py metadata/color/coordinate
helpers and the standard UNRAVEL CLI/logging utilities.

Inputs:
    - Allen Brain Cell Atlas MERFISH download cache (see UNRAVEL guide)
    - Optional prefiltered cell metadata CSV (first column must contain unique cell IDs)
        - Use ``merfish_cluster`` or ``merfish_filter`` to generate filtered cell data.
    - Optional reference .nii.gz for header info (otherwise uses the standard Allen MERFISH


Outputs:
    <stem>.nii.gz: uint16 categorical labels; zero is background.
    <stem>_labels.csv: label/color key and selected/in-bounds cell and voxel counts.

Default filenames:
    GABA neurons colored by neurotransmitter: MERFISH_neurons_GABA.nii.gz
    GABA neurons colored by subclass: MERFISH_neurons_GABA_by_subclass.nii.gz
    All neurons colored by neurotransmitter: MERFISH_neurons_by_neurotransmitter.nii.gz
    All cells colored by subclass: MERFISH_by_subclass.nii.gz
    With -i, the input CSV stem is also included. Use -o for a custom filename.

FSLeyes coloring:
    Reusable LUTs are located in the UNRAVEL repository at:
        unravel/allen_institute/abca/merfish/fsleyes_luts_for_cell_types_to_nii/

    Choose the LUT corresponding to --label-column (or its inferred default):
        neurotransmitter: merfish_neurotransmitter.lut
        class:           merfish_class.lut
        subclass:        merfish_subclass.lut
        supertype:       merfish_supertype.lut
        cluster:         merfish_cluster.lut

    No LUT is written during a run. These LUTs use the WMB 20231215 label IDs
    described below; retain the same ID-to-name mapping when reusing them.
    The cell-type LUTs are distinct from the anatomical atlas ccfv3_2020.lut.

    For LUT setup instructions, see "Setting up Allen brain atlas coloring
    in FSLeyes" in the UNRAVEL guide:
        https://b-heifets.github.io/UNRAVEL/guide.html#reg-check

    Display the output as a "Label image" and select the matching cell-type LUT.
    After installing the LUT, for example:
        fsleyes subclasses.nii.gz -ot label -l merfish_subclass
    Alternatively, pass the full path to merfish_subclass.lut with -l.

Labels are 1-based positions in the sorted FULL taxonomy for the chosen level,
not cluster_alias values. IDs stay fixed across filters within WMB 20231215.
Blank neurotransmitter annotations are explicitly labeled Unassigned (gray).
When types share a voxel, the most frequent selected type wins; ties use the
lowest label ID. Labels are never added or averaged. No dilation or smoothing.

Usage:
------
    mc -b <abc_download_root> -c neurotransmitter -val Glut
    mc -b <abc_download_root> --label-column subclass
    mc -b <abc_download_root> -c neurotransmitter -val Glut "--label-column subclass"


"""

from __future__ import annotations

from pathlib import Path
import re

import nibabel as nib
import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

import unravel.allen_institute.abca.merfish.merfish as mf
from unravel.core.config import Configuration
from unravel.core.help_formatter import SM, RichArgumentParser, SuppressMetavar
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


LEVELS = ("neurotransmitter", "class", "subclass", "supertype", "cluster")
TAXONOMY_DIR = Path("metadata/WMB-taxonomy/20231215/views")
REFERENCE_PATH = Path("image_volumes/MERFISH-C57BL6J-638850-CCF/20230630/resampled_annotation.nii.gz")


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)
    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument("-b", "--base", required=True, action=SM,
                      help="Root directory of the Allen Brain Cell Atlas download cache")
    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument("-r", "--ref_nii", action=SM, default=None,
                      help="Original reconstructed MERFISH reference. Default: standard file under -b")
    opts.add_argument("-i", "--input", action=SM, default=None,
                      help="Cell metadata CSV, optionally prefiltered; first column must contain unique cell IDs")
    opts.add_argument("-c", "--filter-column", action=SM, default=None,
                      help="Metadata column to filter; pair with -val")
    opts.add_argument("-val", "--filter-value", action=SM, nargs="*", default=None,
                      help="Exact value(s) to keep (OR); quote values containing spaces")
    opts.add_argument("-lc", "--label-column", action=SM, choices=LEVELS, default=None,
                      help="Level used for labels/colors. Default: -c if it is a taxonomy level, otherwise neurotransmitter")
    cell_types = opts.add_mutually_exclusive_group()
    cell_types.add_argument("-n", "--neurons", action="store_true",
                            help="Keep mouse WMB classes 01-29")
    cell_types.add_argument("-nn", "--nonneurons", action="store_true",
                            help="Keep mouse WMB classes 30-34")
    opts.add_argument("-o", "--output", action=SM, default=None,
                      help="Output .nii.gz path; label CSV uses the same stem")
    opts.add_argument("-f", "--force", action="store_true", help="Overwrite existing outputs")
    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose", action="store_true", help="Increase verbosity")
    return parser.parse_args()


def load_taxonomy(download_base: Path) -> pd.DataFrame:
    """Load all clusters before filtering, so LUT IDs do not depend on a subset."""
    path = download_base / TAXONOMY_DIR / "cluster_to_cluster_annotation_membership_pivoted.csv"
    taxonomy = pd.read_csv(path, keep_default_na=False).set_index("cluster_alias")
    if not taxonomy.index.is_unique:
        raise ValueError("Taxonomy contains duplicate cluster_alias values.")
    taxonomy = mf.join_cluster_colors(taxonomy, download_base)
    if not taxonomy.index.is_unique:
        raise ValueError("Color table contains duplicate cluster_alias values.")
    taxonomy["neurotransmitter"] = taxonomy["neurotransmitter"].replace("", "Unassigned").fillna("Unassigned")
    return taxonomy


def build_label_table(taxonomy: pd.DataFrame, level: str) -> pd.DataFrame:
    """Make stable integer IDs and normalized RGB colors from the full taxonomy."""
    pairs = taxonomy[[level, f"{level}_color"]].copy()
    pairs.columns = ["name", "hex_color"]
    if pairs.isna().any().any() or (pairs["name"] == "").any():
        raise ValueError(f"Missing names or colors for {level}.")
    pairs["hex_color"] = pairs["hex_color"].str.upper()
    pairs = pairs.drop_duplicates()
    if pairs["name"].duplicated().any():
        raise ValueError(f"Conflicting Allen colors for the same {level} name.")
    if not pairs["hex_color"].str.fullmatch(r"#[0-9A-F]{6}").all():
        raise ValueError(f"Invalid hex colors for {level}.")
    if pairs["name"].str.contains(r"[\r\n]").any():
        raise ValueError("LUT names cannot contain line breaks.")
    table = pairs.sort_values("name").reset_index(drop=True)
    if len(table) > np.iinfo(np.uint16).max:
        raise ValueError("Too many labels for uint16.")
    table.insert(0, "label", np.arange(1, len(table) + 1))
    for channel, start in zip(("red", "green", "blue"), (1, 3, 5)):
        table[channel] = table["hex_color"].map(lambda color: int(color[start:start + 2], 16) / 255.0)
    return table


def load_cell_metadata(download_base: Path, input_path, taxonomy: pd.DataFrame) -> pd.DataFrame:
    """Reuse MERFISH loading/joining; add authoritative taxonomy by cluster_alias."""
    if input_path:
        cells = pd.read_csv(input_path, index_col=0)
    else:
        cells = mf.load_cell_metadata(download_base)
    if not cells.index.is_unique:
        raise ValueError("Cell IDs must be unique; duplicate rows would bias voxel votes.")
    coord_columns = ["x_reconstructed", "y_reconstructed"]
    if not all(col in cells for col in coord_columns):
        cells = cells.drop(columns=["x_reconstructed", "y_reconstructed", "z_reconstructed", "parcellation_index"], errors="ignore")
        n_before = len(cells)
        cells = mf.join_reconstructed_coords(cells, download_base)
        print(f"    Coordinate join retained {len(cells):,} / {n_before:,} cells")
    if not cells.index.is_unique:
        raise ValueError("Coordinate join introduced duplicate cell IDs.")
    if "cluster_alias" not in cells:
        raise KeyError("Cell metadata requires cluster_alias to join the full taxonomy.")
    aliases = pd.to_numeric(cells["cluster_alias"], errors="raise")
    known = aliases.isin(taxonomy.index)
    if not known.all():
        raise ValueError(f"{int((~known).sum()):,} cells have missing/unknown cluster_alias values.")
    for level in LEVELS:
        mapped = aliases.map(taxonomy[level])
        if level in cells:
            existing = cells[level].replace("", np.nan)
            mismatch = existing.notna() & (existing != mapped)
            if mismatch.any():
                raise ValueError(f"Input {level} annotations disagree with WMB 20231215 taxonomy.")
        cells[level] = mapped
    return cells


def filter_cells(cells: pd.DataFrame, args) -> pd.DataFrame:
    if args.neurons or args.nonneurons:
        class_num = cells["class"].str.split().str[0].astype(int)
        cells = cells.loc[class_num <= 29 if args.neurons else class_num > 29]
    if args.filter_column:
        if args.filter_column not in cells:
            raise KeyError(f"Cell metadata column not found: {args.filter_column}")
        values = cells[args.filter_column].astype(str)
        missing = set(args.filter_value) - set(values)
        if missing:
            raise ValueError(f"Requested values absent after neuron filtering: {sorted(missing)}")
        cells = cells.loc[values.isin(args.filter_value)]
    if cells.empty:
        raise ValueError("No cells remain after filtering.")
    return cells.copy()


def precompute_linear_indices(cells: pd.DataFrame, shape, slice_index_map) -> tuple[np.ndarray, np.ndarray]:
    """Match expression-map coordinates, rejecting invalid points before casting.

    Nonnegative x/y use the same truncation as the expression script. Negative
    subvoxel positions are rejected instead of accidentally landing at index 0.
    """
    required = ["x_reconstructed", "y_reconstructed", "brain_section_label"]
    missing = [col for col in required if col not in cells]
    if missing:
        raise KeyError(f"Missing coordinate columns: {missing}")
    x = pd.to_numeric(cells["x_reconstructed"], errors="coerce").to_numpy(dtype=float) / 0.01
    y = pd.to_numeric(cells["y_reconstructed"], errors="coerce").to_numpy(dtype=float) / 0.01
    z = cells["brain_section_label"].map(slice_index_map).to_numpy(dtype=float)
    valid = (np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
             & (x >= 0) & (x < shape[0]) & (y >= 0) & (y < shape[1])
             & (z >= 0) & (z < shape[2]))
    if not valid.any():
        raise ValueError("No selected cells have valid coordinates in the reconstructed MERFISH grid.")
    ijk = (x[valid].astype(np.int64), y[valid].astype(np.int64), z[valid].astype(np.int64))
    return np.ravel_multi_index(ijk, shape), valid


def labels_to_img(linear_idx, labels, shape):
    """Vote by type within each occupied voxel; ties favor the lowest label ID.

    Only occupied (voxel, label) pairs are counted; never allocate a dense
    number-of-voxels by number-of-types array.
    """
    stride = int(labels.max()) + 1
    pairs, votes = np.unique(linear_idx * stride + labels.astype(np.int64), return_counts=True)
    voxels, types = pairs // stride, pairs % stride
    order = np.lexsort((types, -votes, voxels))
    sorted_voxels = voxels[order]
    first = np.r_[True, sorted_voxels[1:] != sorted_voxels[:-1]]
    winners = order[first]
    image = np.zeros(int(np.prod(shape)), dtype=np.uint16)
    image[voxels[winners]] = types[winners]
    _, cells_per_voxel = np.unique(linear_idx, return_counts=True)
    _, types_per_voxel = np.unique(voxels, return_counts=True)
    stats = {
        "occupied_voxels": len(winners),
        "multiple_cell_voxels": int((cells_per_voxel > 1).sum()),
        "mixed_type_voxels": int((types_per_voxel > 1).sum()),
    }
    return image.reshape(shape), stats


def save_label_nii(image, reference, output_path):
    """Keep reference geometry; reset scaling, intent, and display range for labels."""
    header = reference.header.copy()
    header.set_data_dtype(np.uint16)
    header.set_intent("label")
    header.set_slope_inter(1, 0)
    header["cal_min"], header["cal_max"] = 0, int(image.max())
    nii = nib.Nifti1Image(image, reference.affine, header=header)
    nii.set_qform(reference.get_qform(), int(reference.header["qform_code"]))
    nii.set_sform(reference.get_sform(), int(reference.header["sform_code"]))
    nii.header.set_slope_inter(1, 0)
    nib.save(nii, str(output_path))


def output_paths(args, level):
    """Name maps by selection, adding the coloring level only when needed."""
    if args.output:
        image = Path(args.output)
        if not image.name.endswith(".nii.gz"):
            raise ValueError("-o must end with .nii.gz.")
    else:
        stem = "MERFISH"
        if args.neurons:
            stem += "_neurons"
        elif args.nonneurons:
            stem += "_nonneurons"
        if args.input:
            stem += f"_{Path(args.input).stem}"
        if args.filter_column:
            stem += f"_{'_'.join(args.filter_value)}"
        if level != args.filter_column:
            stem += f"_by_{level}"
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem)
        image = Path.cwd() / "MERFISH_cell_type_maps" / f"{stem}.nii.gz"
    stem = image.name[:-7]
    return image, image.with_name(f"{stem}_labels.csv")


def load_reference(download_base, ref_path):
    canonical = download_base / REFERENCE_PATH
    reference = nib.load(str(ref_path or canonical))
    if len(reference.shape) != 3:
        raise ValueError("Reference must be a 3D reconstructed MERFISH image.")
    if ref_path and canonical.exists():
        original = nib.load(str(canonical))
        if reference.shape != original.shape or not np.allclose(reference.affine, original.affine, rtol=0, atol=1e-5):
            raise ValueError("Reference grid differs from the original MERFISH reconstructed grid.")
    elif ref_path:
        print("    Canonical reference absent: supplied grid cannot be independently checked. "
              "It must be the original 10-um XY reconstructed MERFISH grid with the original section order.")
    return reference


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
    if (args.filter_column is None) != (args.filter_value is None):
        raise ValueError("-c and -val must be used together.")
    level = args.label_column or (args.filter_column if args.filter_column in LEVELS else "neurotransmitter")
    image_path, csv_path = output_paths(args, level)
    paths = [image_path, csv_path]
    existing = [str(path) for path in paths if path.exists()]
    if existing and not args.force:
        raise FileExistsError(f"Outputs already exist; use -f to overwrite: {existing}")
    download_base = Path(args.base)
    taxonomy = load_taxonomy(download_base)
    table = build_label_table(taxonomy, level)
    reference = load_reference(download_base, args.ref_nii)
    cells = filter_cells(load_cell_metadata(download_base, args.input, taxonomy), args)
    print(f"\n    Selected cells: {len(cells):,}; label/color level: {level}")
    linear_idx, valid = precompute_linear_indices(cells, reference.shape, mf.slice_index_dict())
    label_ids = cells.loc[valid, level].map(table.set_index("name")["label"]).to_numpy(dtype=np.uint16)
    image, stats = labels_to_img(linear_idx, label_ids, reference.shape)
    table["selected_cell_count"] = table["name"].map(cells[level].value_counts()).fillna(0).astype(int)
    table["in_bounds_cell_count"] = table["name"].map(cells.loc[valid, level].value_counts()).fillna(0).astype(int)
    voxel_counts = np.bincount(image.ravel(), minlength=len(table) + 1)
    table["assigned_voxel_count"] = voxel_counts[table["label"].to_numpy()]
    print(f"    Mapped cells: {int(valid.sum()):,}; excluded coordinates: {int((~valid).sum()):,}")
    print(f"    Voxel counts: {stats}")
    if args.verbose:
        print(table.loc[table["selected_cell_count"] > 0].to_string(index=False))
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
    save_label_nii(image, reference, image_path)
    table.to_csv(csv_path, index=False)
    for path in paths:
        print(f"    Saved: {path}")
    verbose_end_msg()


if __name__ == "__main__":
    main()
