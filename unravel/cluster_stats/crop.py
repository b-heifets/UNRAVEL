#!/usr/bin/env python3

"""
Use ``cstats_crop`` (``crop``) from UNRAVEL to load image, load bounding box, crop cluster, and save as .nii.gz.

Note:
    - -x and -z need to be provided if the resolution is not extracted from the image metadata.
    - Use -a, -b, or -c to specify the crop method.

Usage with all clusters:
------------------------
    cstats_crop -i path/img.nii.gz -o path/output_img.nii.gz -a [-x $XY] [-z $Z] [-v]

Usage with a bounding box:
--------------------------
    cstats_crop -i path/img.nii.gz -o path/output_img.nii.gz -b path/bbox.txt [-x $XY] [-z $Z] [-v]
    
Usage with a cluster ID:
------------------------
    cstats_crop -i path/img.nii.gz -o path/output_img.nii.gz -c 1 [-x $XY] [-z $Z] [-v]
"""

from rich.traceback import install
from rich import print

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_nii
from unravel.core.img_tools import find_bounding_box, label_IDs, crop
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, load_text_from_file


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/img.czi, path/img.nii.gz, or path/tif_dir', action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-o', '--output', help='path/output_img.nii.gz', action=SM)
    opts.add_argument('-b', '--bbox', help='path/bbox.txt', action=SM)
    opts.add_argument('-c', '--cluster', help='Cluster ID/intensity to get bbox and crop', action=SM)
    opts.add_argument('-a', '--all_clusters', help='Crop each cluster. Default: False', action='store_true', default=False)
    opts.add_argument('-x', '--xy_res', help='xy voxel size in microns for the raw data', type=float, action=SM)
    opts.add_argument('-z', '--z_res', help='z voxel size in microns for the raw data', type=float, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def save_cropped_img(img_cropped, xy_res, z_res, args, cluster=None):
    if args.output:
        save_path = args.output
    elif args.bbox:
        save_path = args.input.replace('.nii.gz', f'_cropped.nii.gz')
    elif cluster is not None:
        save_path = args.input.replace('.nii.gz', f'_cluster{cluster}_cropped.nii.gz')
    else:
        print("    [red1]No output specified. Exiting.")
        exit()

    if max(img_cropped.flatten()) < 255:
        save_as_nii(img_cropped, save_path, xy_res, z_res, data_type='uint8')
    else:
        save_as_nii(img_cropped, save_path, xy_res, z_res, data_type='uint16')


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
   
    if args.xy_res is None or args.z_res is None:
        img, xy_res, z_res = load_3D_img(args.input, return_res=True, verbose=args.verbose)
    else:
        img = load_3D_img(args.input, return_res=True, verbose=args.verbose)
        xy_res, z_res = args.xy_res, args.z_res

    # Crop image
    if args.bbox:
        bbox = load_text_from_file(args.bbox)
        img_cropped = crop(img, bbox)
        save_cropped_img(img_cropped, xy_res, z_res, args)
    elif args.cluster:
        xmin, xmax, ymin, ymax, zmin, zmax = find_bounding_box(img, cluster_ID=args.cluster)
        bbox_str = f"{xmin}:{xmax}, {ymin}:{ymax}, {zmin}:{zmax}"
        img_cropped = crop(img, bbox_str)
        save_cropped_img(img_cropped, xy_res, z_res, args, cluster=args.cluster)
    elif args.all_clusters:
        clusters = label_IDs(img, min_voxel_count=1, print_IDs=False, print_sizes=False)
        for cluster in clusters: 
            xmin, xmax, ymin, ymax, zmin, zmax = find_bounding_box(img, cluster_ID=cluster)
            bbox_str = f"{xmin}:{xmax}, {ymin}:{ymax}, {zmin}:{zmax}"
            img_cropped = crop(img, bbox_str)
            save_cropped_img(img_cropped, xy_res, z_res, args, cluster=cluster)
    else:
        print("    [red1]No bbox or cluster specified. Exiting.")
        exit()

    verbose_end_msg()


if __name__ == '__main__':
    main()