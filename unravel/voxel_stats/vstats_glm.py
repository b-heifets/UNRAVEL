#!/usr/bin/env python3

"""
Use ``vstats_glm`` (``vsg``)as a fast parametric alternative to ``vstats`` for a
two-sample unpaired voxel-wise t-test.

The script is intentionally organized similarly to UNRAVEL's ``vstats``:
    - Input images are ``*.nii.gz`` files in the current directory.
    - Condition/group names are taken from the filename prefix before the first "_".
    - Files are merged in Python ``sorted()`` order.
    - Outputs are written to ``./stats/``.
    - The current directory name is used as the output prefix.
    - The merge order is saved to ``stats/merged_image_order.csv``.
    - Optional masking, smoothing, atlas copying, and extra FSL GLM options are supported.

Inputs:
    - ``*.nii.gz`` files in the current directory, with conditions as prefixes
      (e.g., saline_1.nii.gz, saline_2.nii.gz, drug_1.nii.gz, drug_2.nii.gz).

Group/order notes:
    - Files are merged in the order returned by Python's ``sorted()`` function.
    - This order determines group assignment in the design matrix.
    - Sorting is case-sensitive and follows Unicode code-point order.
    - ``design_ttest2`` creates:
        tstat1 / zstat1: group 1 > group 2
        tstat2 / zstat2: group 2 > group 1

Outputs:
    - ``stats/all.nii.gz``: merged 4D input.
    - ``stats/all_s<kernel_um>.nii.gz``: optional smoothed 4D input.
    - ``stats/design.mat`` and ``stats/design.con``.
    - ``stats/<folder>_z.nii.gz``: 4D Z-statistic output from ``fsl_glm``.
    - ``stats/<folder>_zstat1.nii.gz`` and ``..._zstat2.nii.gz``.
    - ``stats/<folder>_vox_p_tstat1.nii.gz`` and ``..._vox_p_tstat2.nii.gz``:
      uncorrected directional 1-p maps, analogous in display convention to
      ``randomise --uncorrp`` outputs.
    - ``stats/groups.txt`` and ``stats/fsl_glm_params.txt``.

P-value convention:
    Each ``design_ttest2`` contrast is directional (one-sided). The ``vox_p``
    images contain 1-p, so:
        0.95 = p < 0.05
        0.99 = p < 0.01
    These are uncorrected parametric p-values. Apply FDR or another appropriate
    multiple-comparison correction before making whole-brain significance claims.

Usage:
------
    vstats_glm [-mas mask.nii.gz] [-k 0.05] [-a atlas/atlas_CCFv3_2020_30um.nii.gz] [-v]
               [--options <additional fsl_glm options>]

Examples:
---------
    vstats_glm -mas atlas/mask.nii.gz -k 0.05 -v

    vstats_glm -mas atlas/mask.nii.gz --options --demean

"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

try:
    from rich import print
    from rich.traceback import install
except ImportError:
    install = lambda: None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fast parametric voxel-wise two-sample t-test using FSL fsl_glm.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-mas", "--mask",
        help="Path to mask.nii.gz. If omitted, fsl_glm is run without an explicit mask.",
    )
    parser.add_argument(
        "-k", "--kernel",
        help="Gaussian smoothing sigma in mm if > 0. Default: 0.",
        default=0,
        type=float,
    )
    parser.add_argument(
        "-a", "--atlas",
        help=(
            "Atlas copied to stats/ for viewing. "
            "Default: atlas/atlas_CCFv3_2020_30um.nii.gz"
        ),
        default="atlas/atlas_CCFv3_2020_30um.nii.gz",
    )
    parser.add_argument(
        "-v", "--verbose",
        help="Stream FSL command output. Default: False.",
        action="store_true",
    )
    parser.add_argument(
        "-opt", "--options",
        help="Additional options passed to fsl_glm; this must be the final script argument.",
        nargs=argparse.REMAINDER,
        default=[],
    )
    return parser.parse_args()


def run_command(command, verbose=False):
    """Run a command, optionally streaming combined stdout/stderr."""
    print(f"\n[bold]{' '.join(map(str, command))}[/bold]\n")

    if verbose:
        with subprocess.Popen(
            [str(x) for x in command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        ) as proc:
            assert proc.stdout is not None
            for line in proc.stdout:
                print(line, end="")
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, command)
    else:
        subprocess.run(
            [str(x) for x in command],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


def match_images():
    """Return sorted input NIfTI files in the current directory."""
    return sorted(Path.cwd().glob("*.nii.gz"))


def group_from_filename(path):
    """Use the text before the first underscore as the group name."""
    return path.name.split("_", 1)[0]


def get_groups_info(images):
    """Return insertion-ordered {group: [files]} based on sorted image order."""
    groups = {}
    for image in images:
        group = group_from_filename(image)
        groups.setdefault(group, []).append(image)
    return groups


def create_design_ttest2(stats_dir, group1_n, group2_n, verbose=False):
    """Create design.mat and design.con for a two-group unpaired t-test."""
    design_prefix = stats_dir / "design"
    run_command(
        ["design_ttest2", design_prefix, str(group1_n), str(group2_n)],
        verbose=verbose,
    )


def merge_images(images, merged_file, verbose=False):
    """Merge 3D subject images into one 4D file."""
    if merged_file.exists():
        print(f"\n    {merged_file} exists. Skipping merge.\n")
        return

    print("\n    Merging *.nii.gz in this order:")
    for image in images:
        print(f"    {image.name}")

    run_command(
        ["fslmerge", "-t", merged_file, *images],
        verbose=verbose,
    )


def smooth_image(merged_file, kernel, verbose=False):
    """Smooth 4D merged data with fslmaths -s; return GLM input path."""
    if kernel <= 0:
        return merged_file

    kernel_in_um = int(round(kernel * 1000))
    smoothed_file = merged_file.with_name(f"all_s{kernel_in_um}.nii.gz")

    if smoothed_file.exists():
        print(f"\n    {smoothed_file} exists. Skipping smoothing.\n")
        return smoothed_file

    run_command(
        ["fslmaths", merged_file, "-s", str(kernel), smoothed_file],
        verbose=verbose,
    )
    return smoothed_file


def split_zstat_4d(z_file, output_prefix):
    """
    Split fsl_glm's 4D --out_z file into one 3D Z-stat image per contrast.

    Returns a list of output paths in contrast order.
    """
    img = nib.load(z_file)
    data = np.asanyarray(img.dataobj)

    if data.ndim == 3:
        data = data[..., np.newaxis]

    if data.ndim != 4:
        raise ValueError(f"Expected a 3D/4D Z-stat image, got shape {data.shape}")

    outputs = []
    for index in range(data.shape[3]):
        out = output_prefix.parent / f"{output_prefix.name}_zstat{index + 1}.nii.gz"
        if not out.exists():
            z_img = nib.Nifti1Image(
                np.asarray(data[..., index], dtype=np.float32),
                img.affine,
                img.header,
            )
            z_img.set_data_dtype(np.float32)
            nib.save(z_img, out)
        outputs.append(out)

    return outputs


def z_to_one_minus_p(z_file, output_file, verbose=False):
    """
    Convert a directional Z-stat image to an uncorrected 1-p image.

    FSL's ``-ztop`` returns the upper-tail p-value. Therefore:
        1-p = 1 - ztop(z)

    Positive Z values supporting the specified contrast approach 1.
    """
    run_command(
        [
            "fslmaths", z_file,
            "-ztop",
            "-mul", "-1",
            "-add", "1",
            output_file,
        ],
        verbose=verbose,
    )


def copy_if_available(source, stats_dir, label):
    """Copy a mask/atlas to stats/ if it exists."""
    if not source:
        return None

    source = Path(source)
    if not source.exists():
        print(f"\n    [yellow]{label} not found: {source}. Skipping copy.[/yellow]\n")
        return None

    destination = stats_dir / source.name
    if not destination.exists():
        shutil.copy2(source, destination)
    return source


def main():
    install()
    args = parse_args()

    cwd = Path.cwd()
    stats_dir = cwd / "stats"
    stats_dir.mkdir(exist_ok=True)

    images = match_images()
    if len(images) < 2:
        sys.exit("Error: At least two input *.nii.gz files are required.")

    groups = get_groups_info(images)
    group_names = list(groups)

    if len(group_names) != 2:
        group_summary = ", ".join(f"{g} (n={len(groups[g])})" for g in group_names)
        sys.exit(
            "Error: This fsl_glm alternative currently supports exactly two groups.\n"
            f"Detected: {group_summary}"
        )

    group1, group2 = group_names
    group1_n = len(groups[group1])
    group2_n = len(groups[group2])

    print(f"\n    Group 1: {group1}, N={group1_n}")
    print(f"    Group 2: {group2}, N={group2_n}")
    print(f"    zstat1 / vox_p_tstat1: {group1} > {group2}")
    print(f"    zstat2 / vox_p_tstat2: {group2} > {group1}\n")

    # Save exact merge/group order.
    order_csv = stats_dir / "merged_image_order.csv"
    with order_csv.open("w") as f:
        f.write("index,group,filename\n")
        for i, image in enumerate(images):
            f.write(f"{i},{group_from_filename(image)},{image.name}\n")

    # Copy viewing/support files.
    mask_path = copy_if_available(args.mask, stats_dir, "Mask")
    copy_if_available(args.atlas, stats_dir, "Atlas")

    # Merge and optionally smooth.
    merged_file = stats_dir / "all.nii.gz"
    merge_images(images, merged_file, verbose=args.verbose)
    glm_input = smooth_image(merged_file, args.kernel, verbose=args.verbose)

    # Create t-test design.
    create_design_ttest2(
        stats_dir,
        group1_n,
        group2_n,
        verbose=args.verbose,
    )

    output_prefix = stats_dir / cwd.name
    z_file = stats_dir / f"{cwd.name}_z.nii.gz"

    # Save a simple human-readable analysis log.
    groups_file = stats_dir / "groups.txt"
    groups_file.write_text(
        f"Group 1 and N: {group1} {group1_n}\n"
        f"Group 2 and N: {group2} {group2_n}\n"
        f"*stat1: {group1} > {group2}\n"
        f"*stat2: {group2} > {group1}\n"
    )

    command = [
        "fsl_glm",
        "-i", glm_input,
        "-d", stats_dir / "design.mat",
        "-c", stats_dir / "design.con",
        f"--out_z={z_file}",
    ]

    if mask_path is not None:
        command.extend(["-m", mask_path])

    if args.options:
        command.extend(args.options)

    params_file = stats_dir / "fsl_glm_params.txt"
    params_file.write_text(
        f"Input: {glm_input}\n"
        f"Mask: {mask_path if mask_path else 'None'}\n"
        f"Kernel_mm: {args.kernel}\n"
        f"Group1: {group1} n={group1_n}\n"
        f"Group2: {group2} n={group2_n}\n"
        f"Command: {' '.join(map(str, command))}\n"
    )

    if not z_file.exists():
        run_command(command, verbose=args.verbose)
    else:
        print(f"\n    {z_file} exists. Skipping fsl_glm.\n")

    # Split one Z volume per contrast and create vstats-like 1-p maps.
    zstats = split_zstat_4d(z_file, output_prefix)

    if len(zstats) < 2:
        sys.exit(
            f"Error: Expected two contrast Z volumes from design_ttest2, "
            f"but found {len(zstats)}."
        )

    for contrast_index, zstat_file in enumerate(zstats, start=1):
        p1_file = stats_dir / f"{cwd.name}_vox_p_tstat{contrast_index}.nii.gz"
        if not p1_file.exists():
            z_to_one_minus_p(
                zstat_file,
                p1_file,
                verbose=args.verbose,
            )
        else:
            print(f"\n    {p1_file} exists. Skipping 1-p conversion.\n")

    print("\n[bold green]fsl_glm finished.[/bold green]")
    print(f"    Output directory: {stats_dir}")
    print(f"    Contrast 1: {group1} > {group2}")
    print(f"    Contrast 2: {group2} > {group1}")
    print("    vox_p maps are uncorrected 1-p maps: 0.95 = p < 0.05.")
    print("    Apply FDR or another multiple-comparison correction for whole-brain inference.\n")


if __name__ == "__main__":
    main()
