#!/usr/bin/env python3

# pyenv deactivate
# pyenv activate zarr
# pip install zarr numpy tifffile

# Convert Zarr level 5 arrays to TIFF series

# USAGE: ./conv_zarr_l5.py /path/file.zarr channel output_parent_dir
# Example: ./conv_zarr_l5.py 1005230289.zarr 0 red
# Example: ./conv_zarr_l5.py 1005230289.zarr 1 green


from pathlib import Path
import sys

import tifffile
import zarr


def save_tif_series(volume, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    for z in range(volume.shape[0]):
        tifffile.imwrite(out_dir / f"slice_{z:04d}.tif", volume[z])


def main():
    if len(sys.argv) != 4:
        print("Usage: python zarr_to_tifs.py /path/to/file.zarr <channel> <output_parent>")
        print("Example: python zarr_to_tifs.py 1005230289.zarr 0 red")
        sys.exit(1)

    zarr_path = Path(sys.argv[1])
    channel = int(sys.argv[2])
    output_parent = Path(sys.argv[3])

    # Match conv behavior: use zarr name without .zarr
    out_dir = output_parent / zarr_path.stem

    # Open level 5 directly
    arr = zarr.open_array(store=str(zarr_path), path="5", mode="r")

    # Expect shape: (channel, z, y, x)
    volume = arr[channel]

    save_tif_series(volume, out_dir)

    print(f"Saved channel {channel} to: {out_dir}")


if __name__ == "__main__":
    main()