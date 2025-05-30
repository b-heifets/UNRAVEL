#!/usr/bin/env python3

"""
Convert a Zarr file to a series of TIFF files.

Usage:
    ./zarr_to_tifs.py <path_to_zarr_file>
"""

import sys
import zarr
import numpy as np
import tifffile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

def save_pixel_spacing_txt(output_dir, spacing_xyz):
    """
    Save voxel spacing in microns to a text file.
    """
    spacing_txt = Path(output_dir) / "pixel_spacing.txt"
    with open(spacing_txt, "w") as f:
        f.write("Voxel size in microns (Z, Y, X):\n")
        f.write(f"{spacing_xyz[0]} {spacing_xyz[1]} {spacing_xyz[2]}\n")
    print(f"📝 Wrote voxel size to: {spacing_txt}")

def save_slice_tif(slice_, slice_idx, out_dir):
    """
    Save a single TIFF slice.
    """
    slice_path = out_dir / f"slice_{slice_idx:04d}.tif"
    tifffile.imwrite(str(slice_path), slice_)

def save_as_tifs_parallel(ndarray, tif_dir_out, voxel_spacing_xyz=None):
    """
    Save 3D image as a TIFF series using parallel writing.
    """
    tif_dir_out = Path(tif_dir_out)
    tif_dir_out.mkdir(parents=True, exist_ok=True)

    if voxel_spacing_xyz:
        save_pixel_spacing_txt(tif_dir_out.parent, voxel_spacing_xyz)

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(save_slice_tif, slice_, i, tif_dir_out)
                for i, slice_ in enumerate(ndarray)]
        for f in futures:
            f.result()  # Wait for all to finish

    print(f"✅ Saved TIFF series to: {tif_dir_out}")


def extract_red_green(zarr_path, resolution_level="3"):
    """
    Extract red and green channels from a Zarr file and save them as TIFF series.
    """
    zarr_path = Path(zarr_path)
    stem_parts = zarr_path.stem.split("_")

    # Common output folder
    common_output_dir = Path("TIFFs")
    common_output_dir.mkdir(exist_ok=True)

    # Output path for this sample
    output_base = common_output_dir / "_".join(stem_parts[:-1])

    z = zarr.open(zarr_path, mode="r")
    level = z[resolution_level]

    if level.ndim != 4:
        raise ValueError(f"Expected shape (c, z, y, x), got {level.shape}")

    red = level[0]   # (z, y, x)
    green = level[1] # (z, y, x)

    # Pixel spacing at level 3: Z = 100 µm, Y = X = 2.8 µm
    spacing_xyz = (100.0, 2.8, 2.8)

    save_as_tifs_parallel(red, output_base / "red", voxel_spacing_xyz=spacing_xyz)
    save_as_tifs_parallel(green, output_base / "green", voxel_spacing_xyz=spacing_xyz)


if __name__ == "__main__":

    # Use consistent logic for checking if already extracted
    zarr_input_path = Path(sys.argv[1])
    stem_parts = zarr_input_path.stem.split("_")
    output_dir = Path("TIFFs") / "_".join(stem_parts[:-1])

    if not output_dir.is_dir():
        extract_red_green(zarr_input_path, resolution_level="3")
        print(f"✅ Extracted red and green channels to: {output_dir}")
    else:
        print(f"❌ Output directory already exists: {output_dir}, skipping.")
