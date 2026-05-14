#!/usr/bin/env python3

"""
Make per-subject absolute-deviation images for Brown-Forsythe or Levene tests.

Brown-Forsythe:
    abs(subject - group_median)

Levene:
    abs(subject - group_mean)

Outputs:
    Dark_*.nii.gz and Light_*.nii.gz images for input into `vstats`.

Interpretation after vstats:
    tstat1 = Dark > Light variance
    tstat2 = Light > Dark variance
"""

import argparse
from pathlib import Path

import numpy as np

from unravel.core.img_io import load_nii, save_as_nii


def parse_args():
    p = argparse.ArgumentParser(
        description="Convert .nii.gz images into Brown-Forsythe or Levene inputs for vstats."
    )
    p.add_argument(
        "-i", "--input",
        nargs="+",
        required=True,
        help="Input .nii.gz files"
    )
    p.add_argument(
        "-m", "--method",
        choices=["brown-forsythe", "levene"],
        default="brown-forsythe",
        help="brown-forsythe = abs(img - group median), levene = abs(img - group mean)"
    )
    p.add_argument(
        "-o", "--output_dir",
        required=True,
        help="Output directory"
    )
    return p.parse_args()


def get_group(path):
    name = path.name
    if "Dark" in name:
        return "Dark"
    if "Light" in name:
        return "Light"
    raise ValueError(f"Could not determine group from filename: {name}")


def load_stack(paths):
    arrays = []
    for path in paths:
        arrays.append(load_nii(path).astype(np.float32))
    return np.stack(arrays, axis=0)


def main():
    args = parse_args()

    input_paths = [Path(p) for p in args.input]
    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Split into groups
    groups = {"Dark": [], "Light": []}
    for path in input_paths:
        groups[get_group(path)].append(path)

    if not groups["Dark"] or not groups["Light"]:
        raise ValueError("Need at least one Dark and one Light image.")

    print(f"Found {len(groups['Dark'])} Dark and {len(groups['Light'])} Light images")

    # Load stacks
    dark_stack = load_stack(groups["Dark"])
    light_stack = load_stack(groups["Light"])

    # Compute centers
    if args.method == "brown-forsythe":
        dark_center = np.median(dark_stack, axis=0)
        light_center = np.median(light_stack, axis=0)
        suffix = "bf_absdev"
    else:
        dark_center = np.mean(dark_stack, axis=0)
        light_center = np.mean(light_stack, axis=0)
        suffix = "lev_absdev"

    # Save Dark outputs
    for i, path in enumerate(groups["Dark"]):
        out = np.abs(dark_stack[i] - dark_center).astype(np.float32)

        name = str(path.name).replace(".nii.gz", "")
        out_path = outdir / f"Dark_{name}_{suffix}.nii.gz"

        save_as_nii(out, out_path, reference=path)
        print(out_path)

    # Save Light outputs
    for i, path in enumerate(groups["Light"]):
        out = np.abs(light_stack[i] - light_center).astype(np.float32)

        name = str(path.name).replace(".nii.gz", "")
        out_path = outdir / f"Light_{name}_{suffix}.nii.gz"

        save_as_nii(out, out_path, reference=path)
        print(out_path)

    print(f"\nSaved transformed images to: {outdir}")


if __name__ == "__main__":
    main()