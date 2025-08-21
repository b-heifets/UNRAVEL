#!/usr/bin/env python3

"""
Use ``unravel_commands`` (``uc``) to print a list of commands available in the UNRAVEL package. 

For help on a ``command``, run: 
<command> -h

Note: 
    - Documentation: https://b-heifets.github.io/UNRAVEL/
    - Commands are roughly organized by the order of the workflow and/or the relatedness of the commands.
    - Aliases are provided for most commands to make them easier to type.
    - Filtering is case-insensitive and matches substrings in the printed lines (regex).
    - For example, use of -f with -d will find matches in the command name and/or description, preserving those lines.

Next steps:
    - Start with ``io_metadata`` (``m``) for most workflows (e.g., to extract or specify raw voxel sizes and image dimensions).
    - Many scripts are designed for batch processing of sample directories, which can be tested using ``utils_get_samples`` (``s``).

Usage to print common commands, aliases, and descriptions:
----------------------------------------------------------
    uc -cad

Usage to print all commands matching a specific string:
-------------------------------------------------------
    uc -ad -f vstats  # Find voxel-wise stats commands

Usage to print all commands and module names:
---------------------------------------------
    uc -m
"""

extended_help = """
If you encounter a situation where a command from the UNRAVEL package has the same name as a command from another package or system command, follow these steps to diagnose and fix the issue:

1. Check the conflicting command:
    - Use the `which` command to determine the location of the executable being called: which <command>
    - This will show the path to the executable that is being invoked when you run the command.

2. Diagnose the conflict:
    - If the path does not point to the UNRAVEL package's command, it means there is a conflict with another package or system command.
    - For example, if you run `which reg` and it points to `/usr/bin/reg` instead of the expected path in your UNRAVEL package's environment, you have identified the conflict.

3. Resolve the conflict:
    - Rename the UNRAVEL command: One way to resolve the conflict is to rename the conflicting command in the `pyproject.toml` file of your UNRAVEL package by adding a unique prefix or suffix.
    - For instance, rename `reg` to `unravel_reg` in the `[project.scripts]` section (i.e., reg = "unravel.register.unravel_reg:main")
    - After making this change, reinstall the package (cd <path/to/clone/of/repo> ; pip install -e .)

4. Re-run the renamed command:
    - Use the new command name to avoid the conflict: unravel_reg -h

5. Create aliases (optional):
    - If you prefer to keep using the original command names, you can create shell aliases in your `.bashrc` or `.zshrc` file to point to the UNRAVEL commands: alias reg="path/to/unravel_env/bin/reg"
    - Reload your shell configuration: source ~/.bashrc  # or source ~/.zshrc

6. Verify the fix:
    - Use the `which` command again to verify that the correct command is being invoked: which unravel_reg  # or which reg if using an alias
"""

import re
from rich import print

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-c', '--common', help='Only print common commands', action='store_true', default=False)
    opts.add_argument('-m', '--module', help='Print the module (script name and location in the unravel package) for each command', action='store_true', default=False)
    opts.add_argument('-d', '--description', help="Print the description of each command's purpose", action='store_true', default=False)
    opts.add_argument('-f', '--filter', help='Filter commands by a string (e.g., -f reg)', type=str, action=SM)
    opts.add_argument('-a', '--aliases', help='Print shorter aliases of the commands', action='store_true', default=False)
    opts.add_argument('--extended-help', help='Help on diagnosing and fixing command conflicts', action='store_true', default=False)

    if parser.parse_known_args()[0].extended_help:
        print(extended_help)
        import sys ; sys.exit()
    return parser.parse_args()


def main():
    args = parse_args()

    commands = {
        "Registration": {
            "reg_prep": {
                "module": "unravel.register.reg_prep",
                "description": "Prepare registration (resample the autofluo image).",
                "common": True,
                "alias": "rp"
            },
            "reg": {
                "module": "unravel.register.reg",
                "description": "Perform registration (register the autofluo image to an average template).",
                "common": True
            },
            "reg_check": {
                "module": "unravel.register.reg_check",
                "description": "Check registration (aggregate the autofluo and warped atlas images).",
                "common": True,
                "alias": "rc"
            },
            "reg_check_fsleyes": {
                "module": "unravel.register.reg_check_fsleyes",
                "description": "Check registration (aggregate the autofluo and warped atlas images).",
                "common": True,
                "alias": "rcf"
            },
            "reg_check_brain_mask": {
                "module": "unravel.register.reg_check_brain_mask",
                "description": "Check brain mask for over/under segmentation.",
                "common": False,
                "alias": "rcbm"
            },
            "reg_affine_initializer": {
                "module": "unravel.register.affine_initializer",
                "description": "Perform affine initialization using ANTsPy.",
                "common": False,
                "alias": "rai"
            },
            "reg_affine_initializer_check": {
                "module": "unravel.register.affine_initializer_check",
                "description": "Check initially aligned template.",
                "common": False,
                "alias": "rai"
            },
        },
        "Warping": {
            "warp_to_atlas": {
                "module": "unravel.warp.to_atlas",
                "description": "Warp images to atlas space.",
                "common": True,
                "alias": "w2a"
            },
            "warp_to_fixed": {
                "module": "unravel.warp.to_fixed",
                "description": "Warp images to native space.",
                "common": False,
                "alias": "w2f"
            },
            "warp_to_native": {
                "module": "unravel.warp.to_native",
                "description": "Warp images to native space.",
                "common": True,
                "alias": "w2n"
            },
            "warp_points_to_atlas": {
                "module": "unravel.warp.points_to_atlas",
                "description": "Warp cell centroids in tissue space to atlas space.",
                "common": True,
                "alias": "wp2a"
            },
            "warp": {
                "module": "unravel.warp.warp",
                "description": "Warp between moving and fixed images.",
                "common": False
            }
        },
        "Segmentation": {
            "seg_copy_tifs": {
                "module": "unravel.segment.copy_tifs",
                "description": "Copy TIF images (copy select tifs to target dir for training ilastik).",
                "common": True,
                "alias": "sct"
            },
            "seg_brain_mask": {
                "module": "unravel.segment.brain_mask",
                "description": "Create brain mask (segment resampled autofluo tifs).",
                "common": True,
                "alias": "sbm"
            },
            "seg_ilastik": {
                "module": "unravel.segment.ilastik_pixel_classification",
                "description": "Perform pixel classification w/ Ilastik to segment features of interest.",
                "common": True,
                "alias": "si"
            },
            "seg_labels_to_masks": {
                "module": "unravel.segment.labels_to_masks",
                "description": "Convert each label to a binary .nii.gz.",
                "common": False,
                "alias": "sl2m"
            }
        },
        "Voxel-wise stats": {
            "vstats_apply_mask": {
                "module": "unravel.voxel_stats.apply_mask",
                "description": "Apply mask to image (e.g., nullify artifacts or isolate signals).",
                "common": False,
                "alias": "apply_mask"
            },
            "vstats_prep": {
                "module": "unravel.voxel_stats.vstats_prep",
                "description": "Prepare immunofluo images for voxel statistics (e.g., background subtract and warp to atlas space).",
                "common": True,
                "alias": "vp"
            },
            "vstats_z_score": {
                "module": "unravel.voxel_stats.z_score",
                "description": "Z-score images.",
                "common": True,
                "alias": "zs"
            },
            "vstats_z_score_cwd": {
                "module": "unravel.voxel_stats.z_score_cwd",
                "description": "Z-score images in the current working directory.",
                "common": True,
                "alias": "zsc"
            },
            "vstats_whole_to_avg": {
                "module": "unravel.voxel_stats.whole_to_LR_avg",
                "description": "Average left and right hemispheres together",
                "common": True,
                "alias": "lr_avg"
            },
            "vstats_hemi_to_avg": {
                "module": "unravel.voxel_stats.hemi_to_LR_avg",
                "description": "If left and right hemispheres were processed separately (less common), average them together.",
                "common": False,
                "alias": "h2a"
            },
            "vstats_check_fsleyes": {
                "module": "unravel.voxel_stats.vstats_check_fsleyes",
                "description": "Check vstats inputs with fsleyes.",
                "common": True,
                "alias": "vcf"
            },
            "vstats": {
                "module": "unravel.voxel_stats.vstats",
                "description": "Compute voxel statistics.",
                "common": True,
                "alias": "vs"
            },
            "vstats_mirror": {
                "module": "unravel.voxel_stats.mirror",
                "description": "Flip and optionally shift content of images in atlas space.",
                "common": False,
                "alias": "mirror"
            }
        },
        "Cluster-wise stats": {
            "cstats_fdr_range": {
                "module": "unravel.cluster_stats.fdr_range",
                "description": "Get FDR q value range yielding clusters.",
                "common": True,
                "alias": "fr"

            },
            "cstats_fdr": {
                "module": "unravel.cluster_stats.fdr",
                "description": "FDR-correct 1-p value map --> cluster map.",
                "common": True,
                "alias": "f"
            },
            "cstats_fstat_sig_vx_mask": {
                "module": "unravel.cluster_stats.fstat_sig_vx_mask",
                "description": "Make FDR mask by thresholding and combining f-stat 1-p maps.",
                "common": False,
                "alias": "fsvm"
            },
            "cstats_mirror_indices": {
                "module": "unravel.cluster_stats.recursively_mirror_rev_cluster_indices",
                "description": "Recursively mirror cluster maps for validating clusters in left and right hemispheres.",
                "common": True,
                "alias": "mirror_ci"
            },
            "cstats_validation": {
                "module": "unravel.cluster_stats.validation",
                "description": "Validate clusters w/ cell/label density measurements.",
                "common": True,
                "alias": "cv"
            },
            "cstats_summary_config": {
                "module": "unravel.cluster_stats.summary_config",
                "description": "Copy a config file for cstats_summary to the working dir.",
                "common": True,
                "alias": "csc"
            },
            "cstats_summary": {
                "module": "unravel.cluster_stats.summary",
                "description": "Summarize info on valid clusters (run after cluster_validation).",
                "common": True,
                "alias": "css"
            },
            "cstats_org_data": {
                "module": "unravel.cluster_stats.org_data",
                "description": "Organize CSVs from custer_validation.",
                "common": False,
                "alias": "cod"
            },
            "cstats_group_data": {
                "module": "unravel.cluster_stats.group_bilateral_data",
                "description": "Group bilateral cluster data.",
                "common": False,
                "alias": "cgd"
            },
            "cstats": {
                "module": "unravel.cluster_stats.cstats",
                "description": "Compute cluster validation statistics.",
                "common": False,
                "alias": "cs"
            },
            "cstats_index": {
                "module": "unravel.cluster_stats.index",
                "description": "Make a valid cluster map and sunburst plots.",
                "common": False,
                "alias": "ci"
            },
            "cstats_brain_model": {
                "module": "unravel.cluster_stats.brain_model",
                "description": "Make a 3D brain model from a cluster map (for DSI studio)",
                "common": False,
                "alias": "cbm"
            },
            "cstats_table": {
                "module": "unravel.cluster_stats.table",
                "description": "Create a table of cluster validation data.",
                "common": False,
                "alias": "ct"
            },
            "cstats_prism": {
                "module": "unravel.cluster_stats.prism",
                "description": "Generate CSVs for bar charts in Prism.",
                "common": False,
                "alias": "prism"
            },
            "cstats_legend": {
                "module": "unravel.cluster_stats.legend",
                "description": "Make a legend of regions in cluster maps.",
                "common": False,
                "alias": "legend"
            },
            "cstats_sunburst": {
                "module": "unravel.cluster_stats.sunburst",
                "description": "Create a sunburst plot of regional volumes.",
                "common": False,
                "alias": "sunburst"
            },
            "cstats_find_incongruent": {
                "module": "unravel.cluster_stats.find_incongruent_clusters",
                "description": "Find clusters where the effect direction does not match the prediction of cluster_fdr (for validation of non-directional p value maps).",
                "common": False,
                "alias": "cfi"
            },
            "cstats_crop": {
                "module": "unravel.cluster_stats.crop",
                "description": "Crop clusters to a bounding box.",
                "common": False,
                "alias": "crop_cluster"
            },
            "cstats_mean_IF": {
                "module": "unravel.cluster_stats.mean_IF",
                "description": "Compute mean immunofluo intensities for each cluster. ",
                "common": False,
                "alias": "cmi"
            },
            "cstats_mean_IF_summary": {
                "module": "unravel.cluster_stats.mean_IF_summary",
                "description": "Plot mean immunofluo intensities for each cluster.",
                "common": False,
                "alias": "cmis"
            },
                "cstats_clusters": {
                "module": "unravel.cluster_stats.clusters",
                "description": "Make a cluster index image from a .nii.gz image",
                "common": False,
                "alias": "clusters"
            },
            "effect_sizes": {
                "module": "unravel.cluster_stats.effect_sizes.effect_sizes",
                "description": "Calculate effect sizes for clusters.",
                "common": False,
                "alias": "es"
            },
            "effect_sizes_sex_abs": {
                "module": "unravel.cluster_stats.effect_sizes.effect_sizes_by_sex__absolute",
                "description": "Calculate absolute effect sizes by sex.",
                "common": False,
                "alias": "esa"
            },
            "effect_sizes_sex_rel": {
                "module": "unravel.cluster_stats.effect_sizes.effect_sizes_by_sex__relative",
                "description": "Calculate relative effect sizes by sex.",
                "common": False,
                "alias": "esr"
            }
        },
        "Region-wise stats": {
            "rstats": {
                "module": "unravel.region_stats.rstats",
                "description": "Compute regional cell counts, regional volumes, or regional cell densities.",
                "common": True
            },
            "rstats_summary": {
                "module": "unravel.region_stats.rstats_summary",
                "description": "Summarize regional cell densities.",
                "common": True,
                "alias": "rss"
            },
            "rstats_mean_IF": {
                "module": "unravel.region_stats.rstats_mean_IF",
                "description": "Compute mean immunofluo intensities for regions.",
                "common": False,
                "alias": "rmi"
            },
            "rstats_mean_IF_in_seg": {
                "module": "unravel.region_stats.rstats_mean_IF_in_segmented_voxels",
                "description": "Compute mean immunofluo intensities in segmented voxels.",
                "common": False,
                "alias": "rmiis"
            },
            "rstats_mean_IF_summary": {
                "module": "unravel.region_stats.rstats_mean_IF_summary",
                "description": "Plot mean immunofluo intensities for regions.",
                "common": False,
                "alias": "rmis"
            }
        },
        "Image I/O": {
            "io_metadata": {
                "module": "unravel.image_io.metadata",
                "description": "Handle image metadata.",
                "common": True,
                "alias": "m"
            },
            "io_convert_img": {
                "module": "unravel.image_io.convert_img",
                "description": "Image conversion operations.",
                "common": False,
                "alias": "conv"
            },
            "io_nii_info": {
                "module": "unravel.image_io.nii_info",
                "description": "Print info about NIfTI files.",
                "common": True,
                "alias": "i"
            },
            "io_nii_hd": {
                "module": "unravel.image_io.nii_hd",
                "description": "Print NIfTI headers.",
                "common": False,
                "alias": "hd"
            },
            "io_nii": {
                "module": "unravel.image_io.io_nii",
                "description": "NIfTI I/O operations (binarize, convert data type, scale, etc).",
                "common": False,
                "alias": "nii"
            },
            "io_reorient_nii": {
                "module": "unravel.image_io.reorient_nii",
                "description": "Reorient NIfTI files.",
                "common": False,
                "alias": "reorient"
            },
            "io_nii_to_tifs": {
                "module": "unravel.image_io.nii_to_tifs",
                "description": "Convert NIfTI files to TIFFs.",
                "common": False,
                "alias": "n2t"
            },
            "io_nii_to_zarr": {
                "module": "unravel.image_io.nii_to_zarr",
                "description": "Convert NIfTI files to Zarr.",
                "common": False,
                "alias": "n2z"
            },
            "io_zarr_to_nii": {
                "module": "unravel.image_io.zarr_to_nii",
                "description": "Convert Zarr format to NIfTI.",
                "common": False,
                "alias": "z2n"
            },
            "io_h5_to_tifs": {
                "module": "unravel.image_io.h5_to_tifs",
                "description": "Convert H5 files to TIFFs.",
                "common": False,
                "alias": "h5t"
            },
            "io_tif_to_tifs": {
                "module": "unravel.image_io.tif_to_tifs",
                "description": "Convert TIF to TIFF series.",
                "common": False,
                "alias": "t2t"
            },
            "io_img_to_npy": {
                "module": "unravel.image_io.img_to_npy",
                "description": "Convert images to Numpy arrays.",
                "common": False,
                "alias": "i2np"
            },
            "io_img_to_points": {
                "module": "unravel.image_io.img_to_points",
                "description": "Convert and image into points coordinates.",
                "common": False,
                "alias": "i2p"
            },
            "io_points_to_img": {
                "module": "unravel.image_io.points_to_img",
                "description": "Populate an empty image with point coordinates.",
                "common": False,
                "alias": "p2i"
            },
            "io_zarr_compress": {
                "module": "unravel.image_io.zarr_compress",
                "description": "Compress .zarr or decompress .zarr.tar.gz files.",
                "common": False,
                "alias": "zc"
            }
        },
        "Image tools": {
            "img_math": {
                "module": "unravel.image_tools.math",
                "description": "Perform mathematical operations on 3D images.",
                "common": True,
                "alias": "math"
            },
            "img_avg": {
                "module": "unravel.image_tools.avg",
                "description": "Average NIfTI images.",
                "common": True,
                "alias": "avg"
            },
            "img_unique": {
                "module": "unravel.image_tools.unique_intensities",
                "description": "Find unique intensities in images.",
                "common": True,
                "alias": "unique"
            },
            "img_max": {
                "module": "unravel.image_tools.max",
                "description": "Print the max intensity value in an image.",
                "common": True,
                "alias": "max"
            },
            "img_bbox": {
                "module": "unravel.image_tools.bbox",
                "description": "Compute bounding box of non-zero voxels in an image.",
                "common": False,
                "alias": "bbox"
            },
            "img_spatial_avg": {
                "module": "unravel.image_tools.spatial_averaging",
                "description": "Perform spatial averaging on images.",
                "common": True,
                "alias": "spatial_avg"
            },
            "img_rb": {
                "module": "unravel.image_tools.rb",
                "description": "Apply rolling ball filter to TIF images.",
                "common": True,
                "alias": "rb"
            },
            "img_DoG": {
                "module": "unravel.image_tools.DoG",
                "description": "Apply Difference of Gaussian filter to TIF images.",
                "common": False,
                "alias": "DoG"
            },
            "img_pad": {
                "module": "unravel.image_tools.pad",
                "description": "Pad images.",
                "common": False,
                "alias": "pad"
            },
            "img_resample": {
                "module": "unravel.image_tools.resample",
                "description": "Resample image.nii.gz.",
                "common": False,
                "alias": "resample"
            },
            "img_resample_points": {
                "module": "unravel.image_tools.resample_points",
                "description": "Resample a set of points [and save as an image].",
                "common": False,
                "alias": "resample_points"
            },
            "img_extend": {
                "module": "unravel.image_tools.extend",
                "description": "Extend images (add padding to one side).",
                "common": False,
                "alias": "extend"
            },
            "img_transpose": {
                "module": "unravel.image_tools.transpose_axes",
                "description": "Transpose image axes.",
                "common": False,
                "alias": "transpose"
            },
            "img_modify_labels": {
                "module": "unravel.image_tools.modify_labels",
                "description": "Modify labels (drop or keep IDs and optionally binarize the result).",
                "common": False,
                "alias": "ml"
            },
        },
        "Atlas tools": {
            "atlas_relabel": {
                "module": "unravel.image_tools.atlas.relable_nii",
                "description": "Relabel atlas IDs.",
                "common": False,
                "alias": "relabel"
            },
            "atlas_wireframe": {
                "module": "unravel.image_tools.atlas.wireframe",
                "description": "Make an atlas wireframe.",
                "common": False,
                "alias": "wf"
            },
        },
        "Utilities": {
            "utils_get_samples": {
                "module": "unravel.utilities.get_samples:main",
                "description": "Test --pattern and --dirs args of script that batch process sample?? dirs.",
                "common": True,
                "alias": "s"
            },
                "utils_process_samples": {
                "module": "unravel.utilities.process_samples:main",
                "description": "Use this for batch processing when commands lack that functionality.",
                "common": False,
                "alias": "ups"
            },
            "utils_region_info": {
                "module": "unravel.utilities.region_info:main",
                "description": "Look up region info (e.g., find ACB to see its region name and ID).",
                "common": True,
                "alias": "region"
            },
            "utils_agg_files": {
                "module": "unravel.utilities.aggregate_files_from_sample_dirs",
                "description": "Aggregate files from sample directories.",
                "common": True,
                "alias": "agg"
            },
            "utils_agg_files_rec": {
                "module": "unravel.utilities.aggregate_files_recursively",
                "description": "Recursively aggregate files.",
                "common": False,
                "alias": "agg_rec"
            },
            "utils_prepend": {
                "module": "unravel.utilities.prepend_conditions",
                "description": "Prepend conditions to files using sample_key.csv.",
                "common": True,
                "alias": "prepend"
            },
            "utils_rename": {
                "module": "unravel.utilities.rename",
                "description": "Rename files.",
                "common": False,
                "alias": "name"
            },
            "utils_toggle": {
                "module": "unravel.utilities.toggle_samples",
                "description": "Toggle sample?? folders for select batch processing.",
                "common": False,
                "alias": "toggle"
            },
            "utils_clean_tifs": {
                "module": "unravel.utilities.clean_tif_dirs",
                "description": "Clean TIF directories (no spaces, move non-tifs).",
                "common": False,
                "alias": "clean_tifs"
            },
            "utils_points_compressor": {
                "module": "unravel.utilities.points_compressor",
                "description": "Pack or unpack point data in a CSV file or summarize the number of points per region.",
                "common": False,
                "alias": "points_compressor"
            }
        },
        "Allen Brain Cell Atlas (ABCA)": {
            "abca_cache": {
                "module": "unravel.allen_institute.abca.cache",
                "description": "Download data from the Allen Brain Cell Atlas.",
                "common": True,
                "alias": "points_compressor"
            },
            "abca_merfish": {
                "module": "unravel.allen_institute.abca.merfish.merfish",
                "description": "Plot MERFISH data from the ABCA.",
                "common": True,
                "alias": "mf"
            },
            "abca_merfish_filter": {
                "module": "unravel.allen_institute.abca.merfish.merfish_filter",
                "description": "Filter MERFISH data from the ABCA and output CSV.",
                "common": True,
                "alias": "mf_filter"
            },
            "abca_merfish_filter_by_mask": {
                "module": "unravel.allen_institute.abca.merfish.merfish_filter_by_mask",
                "description": "Filter MERFISH data using a mask.nii.gz and output CSV.",
                "common": True,
                "alias": "mf_filter_mask"
            },
            "abca_merfish_expression_to_nii": {
                "module": "unravel.allen_institute.abca.merfish.abca_merfish_expression_to_nii",
                "description": "Make a 3D .nii.gz image of ABCA MERFISH expression data.",
                "common": True,
                "alias": "me"
            },
            "abca_merfish_cells_to_nii": {
                "module": "unravel.allen_institute.abca.merfish.abca_merfish_cells_to_nii",
                "description": "Convert ABCA MERFISH cells to a .nii.gz 3D image.",
                "common": False,
                "alias": "mc"
            },
            "abca_sunburst": {
                "module": "unravel.allen_institute.abca.sunburst.sunburst",
                "description": "Make a CSV for a sunburst plot of cell type proportions across all ontological levels.",
                "common": True,
                "alias": "sb"
            },
            "abca_sunburst_expression": {
                "module": "unravel.allen_institute.abca.sunburst.sunburst_expression",
                "description": "Calculate mean expression for all cell types in the ABCA and make a sunburst plot.",
                "common": True,
                "alias": "sbe"
            },
            "abca_sunburst_filter_by_expression": {
                "module": "unravel.allen_institute.abca.sunburst.sunburst_filter",
                "description": "Filter ABCA sunburst data, keeping cells with high expression at any level (class, subclass, etc.).",
                "common": False,
                "alias": "sfbe"
            },
            "abca_sunburst_filter_by_proportion": {
                "module": "unravel.allen_institute.abca.sunburst.sunburst_filter_by_proportion",
                "description": "Filter ABCA sunburst data, keeping prevalent cells at any level.",
                "common": False,
                "alias": "sbfp"
            },
            "abca_mean_expression_color_scale": {
                "module": "unravel.allen_institute.abca.sunburst.mean_expression_color_scale",
                "description": "Save a color scale for mean RNA expression values.",
                "common": False,
                "alias": "mecs"
            },
            "abca_percent_expression_color_scale": {
                "module": "unravel.allen_institute.abca.sunburst.percent_expression_color_scale",
                "description": "Save a color scale for the percent of cells expressing a gene.",
                "common": False,
                "alias": "pecs"
            },
            "abca_scRNA-seq_filter": {
                "module": "unravel.allen_institute.abca.scRNA_seq.filter",
                "description": "Filter ABCA scRNA-seq cells based on columns and values in the cell metadata and save as CSV.",
                "common": True,
                "alias": "s_filter"
            },
        },
        "Genetic Tools Atlas (GTA)": {
            "gta_download": {
                "module": "unravel.allen_institute.genetic_tools_atlas.download_STPT_zarr",
                "description": "Download STPT Zarr files.",
                "common": False,
                "alias": "gta_dl"
            },
            "gta_metadata": {
                "module": "unravel.allen_institute.genetic_tools_atlas.metadata",
                "description": "Simplify metadata from the GTA.",
                "common": False,
                "alias": "gta_m"
            },
            "gta_org_samples": {
                "module": "unravel.allen_institute.genetic_tools_atlas.org_samples",
                "description": "Organize TIFFs dirs from the GTA after conversion.",
                "common": False,
                "alias": "gta_os"
            },
        },
        "Tabular data": {
            "tabular_edit_columns": {
                "module": "unravel.tabular.edit_columns",
                "description": "Edit columns in a tabular dataset.",
                "common": False,
                "alias": "edit_cols"
            },
            "tabular_filter_rows": {
                "module": "unravel.tabular.filter_rows",
                "description": "Filter rows in a tabular dataset.",
                "common": False,
                "alias": "filter_rows"
            },
            "tabular_key_value_to_table": {
                "module": "unravel.tabular.key_value_to_table",
                "description": "Convert key-value pairs to a table format.",
                "common": False,
                "alias": "kv_table"
            },
            "tabular_columns": {
                "module": "unravel.tabular.columns",
                "description": "Print specified columns from a tabular dataset.",
                "common": False,
                "alias": "cols"
            },
            "tabular_unique_values": {
                "module": "unravel.tabular.unique_values",
                "description": "Print unique values in specified column(s) of a tabular dataset.",
                "common": False,
                "alias": "uniq_vals"
            },
        },
    }

    print("\n[magenta bold]Category[/], [cyan bold]Command[/], [green]Alias (-a), [purple3]Module (-m)[/], [grey50]Description (-d), \n")

    for category, cmds in commands.items():
        if args.common:
            cmds = {k: v for k, v in cmds.items() if v.get("common")}
        if args.filter:
            # Apply filtering logic
            filtered_cmds = {}
            for cmd, details in cmds.items():
                output = f"{cmd}"
                if args.module:
                    output += f" {details['module']}"
                if args.aliases:
                    output += f" {details.get('alias', '')}"
                if args.description:
                    output += f" {details['description']}"

                # Perform filtering on the constructed output string
                if re.search(args.filter, output, re.IGNORECASE):
                    filtered_cmds[cmd] = details
            cmds = filtered_cmds
        if not cmds:
            continue

        print(f"[magenta bold]{category}:")
        for cmd, details in cmds.items():
            output = f"  [cyan bold]{cmd}[/]"
            if args.module:
                output += f" [purple3]{details['module']}[/]"
            if args.aliases:
                output += f" [green]{details.get('alias', '')}[/]"
            if args.description:
                output += f" [grey50]{details['description']}[/]"
            print(output)

if __name__ == "__main__":
    main()