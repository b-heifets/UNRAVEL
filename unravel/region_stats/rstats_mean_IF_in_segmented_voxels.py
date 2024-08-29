#!/usr/bin/env python3

"""
Use ``rstats_mean_IF_in_seg`` from UNRAVEL to measure mean intensity of immunofluorescence (IF) staining in brain regions in segmented voxels.

Inputs:
    - rel_path/fluo_image or rel_path/fluo_img_dir
    - rel_path/seg_img.nii.gz in tissue space (1st glob match processed)
    - path/atlas.nii.gz to warp to tissue space

Output:
    - ./sample??/seg_dir/sample??_seg_dir_regional_mean_IF_in_seg.csv

Note:
    This uses full resolution images (i.e., the raw IF image and a segmentation from ``seg_ilastik``)

Next steps:
    ``utils_agg_files`` -i seg_dir/sample??_seg_dir_regional_mean_IF_in_seg.csv
    ``rstats_mean_IF_summary``

Usage
-----
    rstats_mean_IF_in_seg -i <asterisk>.czi -s seg_dir/sample??_seg_dir.nii.gz -a path/atlas.nii.gz [-o seg_dir/sample??_seg_dir_regional_mean_IF_in_seg.csv] [--region_ids 1 2 3] [-c 1] [Optional output: -n rel_path/native_image.zarr] [-fri autofl_50um_masked_fixed_reg_input.nii.gz] [-inp nearestNeighbor] [-ro reg_outputs] [-r 50] [-md parameters/metadata.txt] [-zo 0] [-mi] [-v]
"""

import csv
import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_rich_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times, initialize_progress_bar, get_samples
from unravel.warp.to_native import to_native


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/fluo_image or path/fluo_img_dir relative to sample?? folder', required=True, action=SM)
    reqs.add_argument('-s', '--seg', help='rel_path/seg_img.nii.gz. 1st glob match processed', required=True, action=SM)
    reqs.add_argument('-a', '--atlas', help='path/atlas.nii.gz to warp to native space', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='path/name.csv relative to ./sample??/', default=None, action=SM)
    opts.add_argument('--region_ids', help='Optional: Space-separated list of region intensities to process. Default: Process all regions', default=None, nargs='*', type=int)
    opts.add_argument('-c', '--chann_idx', help='.czi channel index. Default: 1', default=1, type=int, action=SM)

    # Optional to_native() args
    opts_to_native = parser.add_argument_group('Optional to_native() arguments')
    opts_to_native.add_argument('-n', '--native_atlas', help='Load/save native atlasfrom/to rel_path/native_image.zarr (fast) or rel_path/native_image.nii.gz if provided', default=None, action=SM)
    opts_to_native.add_argument('-fri', '--fixed_reg_in', help='Fixed input for registration (``reg``). Default: autofl_50um_masked_fixed_reg_input.nii.gz', default="autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)    
    opts_to_native.add_argument('-inp', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor [default], multiLabel [slow])', default="nearestNeighbor", action=SM)
    opts_to_native.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from ``reg`` (e.g., transforms). Default: reg_outputs", default="reg_outputs", action=SM)
    opts_to_native.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    opts_to_native.add_argument('-md', '--metadata', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    opts_to_native.add_argument('-zo', '--zoom_order', help='SciPy zoom order for scaling to full res. Default: 0 (nearest-neighbor)', default='0',type=int, action=SM)

    compatability = parser.add_argument_group('Compatability options for to_native()')
    compatability.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@print_func_name_args_times()
def calculate_mean_intensity(IF_img, ABA_seg, args):
    """Calculates mean intensity for each region in the atlas.
    
    Parameters:
        IF_img (np.ndarray): 3D image of immunofluorescence staining.
        ABA_seg (np.ndarray): 3D image of segmented brain regions.
        args (argparse.Namespace): Command line arguments.

    Returns:
        mean_intensities_dict: {region_id: mean_IF_in_seg}
    """

    print("\n  Calculating mean immunofluorescence intensity for each region in the atlas...\n")

    # Ensure both images have the same dimensions
    if IF_img.shape != ABA_seg.shape:
        raise ValueError("The dimensions of IF_img and ABA_seg do not match.")
    
    # Flatten the images to 1D arrays for bincount
    IF_img_flat = IF_img.flatten()
    ABA_seg_flat = ABA_seg.flatten()

    # Use bincount to get fluo intensity sums for each region
    sums = np.bincount(ABA_seg_flat, weights=IF_img_flat) # Sum of intensities in each region (excluding background)
    counts = np.bincount(ABA_seg_flat) # Number of voxels in each region (excluding background)

    # Suppress the runtime warning and handle potential division by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        mean_intensities = sums / counts

    mean_intensities = np.nan_to_num(mean_intensities)

    # Convert to dictionary
    mean_intensities_dict = {i: mean_intensities[i] for i in range(1, len(mean_intensities))}

    # Filter the dictionary if regions are provided
    if args.region_ids:
        mean_intensities_dict = {region: mean_intensities_dict[region] for region in args.region_ids if region in mean_intensities_dict}

    # Print results
    for region, mean_intensity in mean_intensities_dict.items():
        if mean_intensity > 0 and args.verbose:
            print(f"    Region: {region}\tMean intensity in segmented voxels: {mean_intensity}")

    return mean_intensities_dict


def write_to_csv(data, output_path):
    """Writes the data to a CSV file."""
    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Region_Intensity", "Mean_IF_Intensity"])
        for key, value in data.items():
            writer.writerow([key, value])


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:

            # Load or make the native atlas image
            native_atlas_path = next(sample_path.glob(str(args.native_atlas)), None)
            if args.native_atlas and native_atlas_path.exists():
                native_atlas = load_3D_img(native_atlas_path)
            else:
                fixed_reg_input = Path(sample_path, args.reg_outputs, args.fixed_reg_in) 
                if not fixed_reg_input.exists():
                    fixed_reg_input = sample_path / args.reg_outputs / "autofl_50um_fixed_reg_input.nii.gz"
                native_atlas = to_native(sample_path, args.reg_outputs, fixed_reg_input, args.atlas, args.metadata, args.reg_res, args.miracl, args.zoom_order, args.interpol, output=native_atlas_path)

            # Load the segmentation image
            seg_path = next(sample_path.glob(str(args.seg)), None)
            if seg_path is None:
                print(f"\n    [red bold]No files match the pattern {args.seg} in {sample_path}\n")
                continue
            seg_nii = nib.load(seg_path)
            seg_img = np.asanyarray(seg_nii.dataobj, dtype=np.bool_).squeeze()

            # Multiply the images to convert the seg image to atlas intenties
            ABA_seg = native_atlas * seg_img

            # Load the IF image
            IF_img_path = next(sample_path.glob(str(args.input)), None)
            if IF_img_path is None:
                print(f"No files match the pattern {args.input} in {sample_path}")
                continue
            IF_img = load_3D_img(IF_img_path, args.chann_idx, "xyz")

            # Calculate mean intensity
            mean_intensities = calculate_mean_intensity(IF_img, ABA_seg, args)

            # Write to CSV
            if args.output:
                output_path = sample_path / args.output
                output_path.parent.mkdir(parents=True, exist_ok=True)
                write_to_csv(mean_intensities, output_path)
            else: 
                output_str = str(seg_path).replace('.nii.gz', '_regional_mean_IF_in_seg.csv')
                write_to_csv(mean_intensities, output_str)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()