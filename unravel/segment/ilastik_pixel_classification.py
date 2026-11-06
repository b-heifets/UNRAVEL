#!/usr/bin/env python3

"""
Use ``seg_ilastik`` (``si``) from UNRAVEL to segment features of interest using Ilastik.

Prereqs:
    - Organize training TIFFs into a folder (e.g., with ``seg_copy_tifs``).
    - Train Ilastik (https://b-heifets.github.io/UNRAVEL/guide.html#train-an-ilastik-project).

Inputs:
    - Ilastik project: path/ilastik_project.ilp
    - Input: path/tif_dir or path/image (relative to current dir or sample??/)
    - Input image types: .tif, .czi, .nii.gz, .h5, .zarr
    - If a glob pattern is used, the first match is used.

Outputs:
    - seg_dir/seg_dir/*.tif (segmented images; delete with --rm_out_tifs)
    - Optional: seg_dir/seg_dir_<label>.nii.gz (binary masks for selected labels)
    - Skips processing if all requested masks exist, or reuses complete segmented TIFFs.

Notes:
    - For a directory of individual 2D OME-TIFF slices whose OME metadata describes
      a 3D volume, temporarily rewrites the slices as ordinary 2D TIFFs for Ilastik.
      The source files are never modified. Temporary inputs are deleted on exit.
    - The Ilastik project should be closed before running this script.
    - Example executable (Linux): /usr/local/ilastik-1.4.0.post1-Linux/run_ilastik.sh

Usage:
    seg_ilastik -ilp path/ilastik_project.ilp -i <tif_dir or image> -o seg_dir \
        [--labels 1 2 3] [--rm_out_tifs] [--channel 1] \
        [-ie path/ilastik_executable] [-d list of paths] [-p sample??] [-v]
"""

import shutil
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory

import nibabel as nib
import numpy as np
import tifffile
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_tifs
from unravel.core.img_tools import pixel_classification
from unravel.core.utils import (
    log_command, match_files, verbose_start_msg, verbose_end_msg,
    get_samples, print_func_name_args_times, initialize_progress_bar,
)


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-ilp', '--ilastik_prj', help='path/ilastik_project.ilp', required=True, action=SM)
    reqs.add_argument('-i', '--input', help='Relative path to TIFF dir or image (.czi, .tif, .nii.gz, .h5, .zarr).', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='Output dir name', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-l', '--labels', help='Segmentation label IDs to save as 3D binary .nii.gz images', nargs='*', type=int, action=SM)
    opts.add_argument('-rmo', '--rm_out_tifs', help='Delete segmented TIFFs after saving label masks.', action='store_true', default=False)
    opts.add_argument('-c', '--channel', help='Channel for applicable input formats. Default: 1', default=1, type=int, metavar='')
    opts.add_argument('-ie', '--ilastik_exe', help='Ilastik executable path. Default: /usr/local/ilastik-1.4.0.post1-Linux/run_ilastik.sh', default='/usr/local/ilastik-1.4.0.post1-Linux/run_ilastik.sh', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Sample dirs or their parent dirs (space-separated). Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Sample directory pattern. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    return parser.parse_args()


def tif_files_in(directory):
    """Sorted list of .tif files (includes .ome.tif)."""
    return sorted(Path(directory).glob('*.tif'))


def needs_plain_tif_conversion(first_tif):
    """True for 2D OME-TIFF slices whose metadata exposes a 3D series."""
    with tifffile.TiffFile(first_tif) as tif:
        return (
            tif.is_ome
            and len(tif.pages) == 1
            and tif.pages[0].ndim == 2
            and tif.series[0].ndim > 2
        )


def convert_ome_slices_to_plain_tifs(source_tifs, destination_dir):
    """Rewrite OME-TIFF slices as regular 2D TIFFs, one slice at a time.

    Reading ``pages[0]`` rather than ``asarray()`` avoids loading the
    entire multi-file OME series referenced by its XML metadata.
    """
    destination_dir = Path(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)

    for src in source_tifs:
        with tifffile.TiffFile(src) as tif:
            if len(tif.pages) != 1 or tif.pages[0].ndim != 2:
                raise ValueError(f'Expected a single 2D TIFF page: {src}')
            img = tif.pages[0].asarray()

        # Drop the misleading .ome suffix, since these temporary files are plain TIFFs.
        name = src.name[:-len('.ome.tif')] + '.tif' if src.name.endswith('.ome.tif') else src.name
        dst = destination_dir / name
        if dst.exists():
            raise FileExistsError(f'Duplicate temporary TIFF name: {dst}')
        tifffile.imwrite(dst, img, metadata=None, photometric='minisblack')

    converted_count = len(tif_files_in(destination_dir))
    if converted_count != len(source_tifs):
        raise RuntimeError(f'Converted {converted_count} of {len(source_tifs)} TIFF files.')


@print_func_name_args_times()
def save_labels_as_masks(tif_dir, labels, segmentation_dir, output_name, verbose=False):
    img = load_3D_img(tif_dir, verbose=verbose)
    for label in labels:
        print(f'\n    Converting label {label} to binary mask and saving as .nii.gz in {segmentation_dir}\n')
        label_img = (img == label).astype(np.uint8)
        nifti_img = nib.Nifti1Image(label_img, np.eye(4))
        nib.save(nifti_img, segmentation_dir / f'{output_name}_{label}.nii.gz')


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    labels = args.labels or []
    if args.rm_out_tifs and not labels:
        raise ValueError('--rm_out_tifs requires --labels; otherwise, all outputs would be removed.')

    ilastik_exe = Path(args.ilastik_exe).expanduser()
    if not ilastik_exe.is_file():
        raise FileNotFoundError(f'Ilastik executable not found: {ilastik_exe}. Specify -ie.')

    project_path = Path(args.ilastik_prj).expanduser().resolve()
    if not project_path.is_file():
        raise FileNotFoundError(f'Ilastik project not found: {project_path}')

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)
    progress, task_id = initialize_progress_bar(len(sample_paths), 'Processing samples...')

    with Live(progress):
        for sample_path in sample_paths:
            input_path = sample_path / args.input
            segmentation_dir = sample_path / args.output
            output_tif_dir = segmentation_dir / args.output
            segmentation_dir.mkdir(exist_ok=True, parents=True)

            # All final masks already present: nothing to do.
            if labels and all(
                (segmentation_dir / f'{args.output}_{label}.nii.gz').is_file()
                for label in labels
            ):
                print(f'\n    All requested label masks exist in {segmentation_dir}. Skipping.')
                progress.update(task_id, advance=1)
                continue

            # Determine input depth without loading all OME TIFF slices into RAM.
            input_tifs = []
            img = None
            if input_path.is_dir() and not input_path.name.endswith('.zarr'):
                input_tifs = tif_files_in(input_path)
            if input_tifs:
                input_z_size = len(input_tifs)
            else:
                matches = match_files(args.input, sample_path)
                if not matches:
                    raise FileNotFoundError(f'No input found for {sample_path / args.input}')
                image_path = matches[0]
                if args.verbose:
                    print(f'    Using {image_path} as input image.')
                img = load_3D_img(image_path, channel=args.channel, verbose=args.verbose)
                if img.ndim != 3:
                    raise ValueError(f'Expected 3D input, got {img.shape} at {image_path}')
                input_z_size = img.shape[2]

            if input_z_size == 0:
                raise ValueError(f'No input TIFF slices found for {sample_path / args.input}')

            output_z_size = len(tif_files_in(output_tif_dir))
            if output_z_size == input_z_size:
                print(f'\n    Found {output_z_size} completed segmentation TIFFs in {output_tif_dir}.')
                if labels:
                    save_labels_as_masks(output_tif_dir, labels, segmentation_dir, args.output, verbose=args.verbose)
                if args.rm_out_tifs:
                    shutil.rmtree(output_tif_dir)
                progress.update(task_id, advance=1)
                continue

            if output_z_size > 0:
                raise RuntimeError(
                    f'Incomplete segmentation in {output_tif_dir}: '
                    f'found {output_z_size}/{input_z_size} TIFFs. '
                    'Remove incomplete outputs before rerunning.'
                )

            # Stage temporary input TIFFs only when needed; always clean up on exit,
            # including when Ilastik or label conversion raises an exception.
            with ExitStack() as stack:
                if input_tifs and not needs_plain_tif_conversion(input_tifs[0]):
                    input_tif_dir = input_path
                else:
                    temp_dir = stack.enter_context(
                        TemporaryDirectory(prefix='ilastik_input_', dir=segmentation_dir)
                    )
                    input_tif_dir = Path(temp_dir)
                    if input_tifs:
                        print(f'\n    Converting {input_z_size} OME-TIFF slices to temporary plain TIFFs...')
                        convert_ome_slices_to_plain_tifs(input_tifs, input_tif_dir)
                    else:
                        save_as_tifs(img, input_tif_dir)
                        del img

                output_tif_dir.mkdir(exist_ok=True, parents=True)
                pixel_classification(
                    str(input_tif_dir), str(project_path),
                    str(output_tif_dir), str(ilastik_exe)
                )

                output_z_size = len(tif_files_in(output_tif_dir))
                if output_z_size != input_z_size:
                    raise RuntimeError(
                        f'Expected {input_z_size} segmented TIFFs, '
                        f'but found {output_z_size} in {output_tif_dir}.'
                    )

                if labels:
                    save_labels_as_masks(
                        output_tif_dir, labels, segmentation_dir,
                        args.output, verbose=args.verbose
                    )

            if args.rm_out_tifs:
                shutil.rmtree(output_tif_dir)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()
