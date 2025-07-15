#!/usr/bin/env python3

"""
Use ``io_img`` (``img``) from UNRAVEL to load a 3D image and save as a different format.

Input image types:
    - .czi
    - .nii.gz
    - .ome.tif or .tif series (provide a path to the dir containing the .tif files or to a single .tif file)
    - .zarr
    - .h5

Output image types:
    - .nii.gz
    - .tif series (provide a path to the dir where the .tif files will be saved)
    - .zarr
    - .h5

Note:
    - Provide -x and -z for .tif, .zarr, .h5 files to set the xy and z resolution in micrometers.

Usage to convert a .czi file to .nii.gz:
----------------------------------------
io_img -i 'sample.czi' -c 1 -s .nii.gz

Usage to convert a single .tif series to .nii.gz:
-------------------------------------------------
io_img -i 'sample*/tifs/' -x 3.5 -z 6 -s .nii.gz 

Usage to recursively convert all dirs with tif files to .zarr:
--------------------------------------------------------------
io_img -i '**/*.tif' -x 3.5 -z 6 --save_as .zarr 
"""

from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_3D_img
from unravel.core.utils import initialize_progress_bar, log_command, match_files, print_func_name_args_times, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help="Glob pattern(s) for input image files (e.g., '*.czi', '*.nii.gz', etc.). For TIFFs, match individual .tif files or dirs w/ .tif series.", required=True, nargs='*', action=SM)
    reqs.add_argument('-s', '--save_as', help='Output format extension (e.g., .nii.gz, .zarr, .tif).', required=True, choices=['.nii.gz', '.tif', '.zarr', '.h5'], action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-x', '--xy_res', help='xy resolution in µm. Provide for .tifs', type=float, action=SM)
    opts.add_argument('-z', '--z_res', help='z resolution in µm', type=float, action=SM)
    opts.add_argument('-c', '--channel', help='.czi channel number. Default: 0 for autofluo', default=0, type=int, action=SM)
    opts.add_argument('-o', '--output', help='Output directory path. Default: None (saves in the same directory as input).', default=None, action=SM)
    opts.add_argument('-d', '--dtype', help='Data type for .nii.gz. Options: np.uint8, np.uint16, np.float32.', default=None, action=SM)
    opts.add_argument('-r', '--reference', help='Reference image for .nii.gz metadata. Default: None', default=None, action=SM)
    opts.add_argument('-f', '--force', help='Force overwrite existing output files. Default: False', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Test if other scripts in the image_io parent dir of this script are redundant and can be removed. If so, consolidate them into this script.
# TODO: Could add parallel processing multiple inputs
# TODO: This works for loading a .zarr from save_as_zarr(). Test it if works with .zarr files from download_GTA_STPT_zarr. 
# TODO: Perhaps add support for zarr_level_to_tifs() can allow for saving in different formats, e.g., .nii.gz, .tif, etc.?
# TODO: Add support for extracting metadata from .zarr and .h5 files.
# TODO: Consider rename this script to img_convert.py to make it more intuitive and distinct from img_io.py

@print_func_name_args_times()
def io_img(img_file, save_as, output, force, channel, xy_res=None, z_res=None, dtype=None, reference=None, verbose=False):
    """
    Load a 3D image and save it in a different format.

    Parameters:
    -----------
    img_file : str
        Path to the input image file (e.g., .czi, .nii.gz, .tif series, .zarr, .h5).
    save_as : str
        Desired output format (e.g., '.nii.gz', '.tif', '.zarr', '.h5').
    output : str
        Directory path where the output file will be saved. If None, saves in the same directory as the input file.
    force : bool
        If True, overwrites existing output files. Default is False.
    channel : int
        Channel number to extract from .czi files. Default is 0.
    xy_res : float, optional
        xy resolution in micrometers. Required for .tif, .zarr, and .h5 files.
    z_res : float, optional
        z resolution in micrometers.
    dtype : str, optional
        Data type for the output .nii.gz file. Options include 'np.uint8', 'np.uint16', 'np.float32'. If None, uses the original data type.
    reference : str, optional
        Path to a reference image for .nii.gz metadata. If None, the metadata will not be set.
    verbose : bool
        If True, prints detailed information about the image being processed. Default is False.

    """

    if save_as not in ['.nii.gz', '.tif', '.zarr', '.h5']:
        raise ValueError(f"Unsupported output format: {save_as}")
    
    img_path = Path(img_file)
    if img_path.suffix == '.tif':
        img_path = img_path.parent  # If it's a .tif series, use the directory containing the .tif files

    img_file_basename = str(img_path.name).replace('.nii.gz', '') if str(img_path).endswith('.nii.gz') else img_path.stem

    # Define output path based on the input file name and specified output format
    if save_as == '.tif':
        out_path = img_path.parent / img_file_basename if not output else Path(output) / img_file_basename
    else:
        # For other formats, use the same directory as the input file
        out_dir_path = img_path.parent if not output else Path(output)
        out_path = out_dir_path / f"{img_file_basename}{save_as}"

    if not force:
        if out_path.exists():
            print(f"[yellow]Output file {out_path} already exists for {img_path.name}. Skipping conversion.[/yellow]")
            return

    # Load the image
    if xy_res is None or z_res is None:
        img, xy_res, z_res = load_3D_img(img_path, channel, return_res=True, verbose=verbose)
    else:
        img = load_3D_img(img_path, channel, verbose=verbose)

    if verbose:
        print(f"\n📄 [bold]{img_path.name}[/bold]")
        print(f"    Type: {type(img)}")
        print(f"    Shape: {img.shape}")
        print(f"    Dtype: {img.dtype}")
        print(f"    xy res: {xy_res} µm, z res: {z_res} µm")

    # Save the image in the specified format
    save_3D_img(img, out_path, xy_res=xy_res, z_res=z_res, data_type=dtype, reference_img=reference)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    img_files = match_files(args.input)
    
    # Make sure the output directory exists
    if args.output:
        Path(args.output).mkdir(parents=True, exist_ok=True)

    progress, task_id = initialize_progress_bar(len(img_files), task_message="[bold green]Converting images...")
    with Live(progress):

        for img_file in img_files:
            io_img(img_file, args.save_as, args.output, args.force, args.channel, args.xy_res, args.z_res, args.dtype, args.reference, args.verbose)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()