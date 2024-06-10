# Guide

## Stitch z-stacks if needed
   * We use [ZEN (blue edition)](https://www.micro-shop.zeiss.com/en/us/softwarefinder/software-categories/zen-blue/) since we have a [Zeiss Lightsheet 7](https://www.zeiss.com/microscopy/en/products/light-microscopes/light-sheet-microscopes/lightsheet-7.html)
   * Open source options: 
      * [TeraStitcher](https://abria.github.io/TeraStitcher/)
      * [ZetaStitched](https://github.com/lens-biophotonics/ZetaStitcher)

## Organize sample folders and raw data
   * Make a folder named after each condition in the experiment folder(s)
```bash
. # This root level folder is referred to as the experiment directory (exp dir) 
├── Control
└── Treatment
```
   * Make sample?? folders in the folders named after each condition

```bash
.
├── Control
│   ├── sample01
│   └── sample02
└── Treatment
    ├── sample03
    └── sample04
```

```{note}
Naming directories (dirs) like sample01, sample02, etc., makes batch processing easy. 

Use a csv, Google sheet, or whatever else for linking sample IDs to IDs w/ this convention.

Other patterns (e.g., sample???) may be used (commands/scripts have a -p option for that).
```

   * Add raw data (e.g., image.czi, image.h5, or folder(s) with tif series) to each sample?? dir

```bash
.
├── Control
│   ├── sample01
│   │   └── <raw image(s)>
│   └── sample02
│        └── <raw image(s)>
└── Treatment
    ├── sample03
    │   └── <raw image(s)>
    └── sample04
        └── <raw image(s)>
```

```{note}
Multiple exp dirs maybe used (the -e flag in commands/scripts specifies the path to each exp dir).

For example, if there is not enough storage on a drive, consider using multiple drives. 

Spreading data across 2-4 external drives allows for faster parallel processing. 

If SSDs are used, distrubuting data may not speed up processing as much. 
```

## Make an exp_notes.txt
* This helps for keeping track of paths, commands, etc.

```bash
cd <path/exp_dir>  # Change the current working directory to an exp dir

touch exp_notes.txt  # Make the .txt file
```

```{note}
Most scripts log the command used to run them, appending to ./.command_log.txt

This is a hidden file. Use control+h to view it on Linux. 
```

```bash
# View command history for the current working directory
cat .command_log.txt  

# View last 10 lines
cat .command_log.txt | tail -10  
```




## Make a sample_key.csv with this organization: 
   * dir_name,condition
   * sample01,control
   * sample02,treatment

## Define common variables in a shell script
* To make commands easier to run, define common variables in a shell script (e.g., env_var.sh)
* Source the script to load variables in each terminal session
* Copy /UNRAVEL/_other/env_var_gubra.sh to an exp dir and update each variable

```{note}
Add this line to your .bashrc or .zshrc terminal config file: 
alias exp=". /path/env_var.sh" 
```
```bash
# Source the updated config file
. ~/.zshrc

# Run the alias to source the variables before using them to run commands/scripts
exp
```

## Commands/scripts
For help/info on a command/script, run
```
<command> -h

# Or 
<script.py> -h 
```

## Optional: clean tifs
   * If raw data is in the form of a tif series, consider running: 
```bash
clean_tifs -t <dir_name> -v -m -e $DIRS
```

## Typical workflow: 
   * Follow this outline of common commands for analysis steps [Commands](commands.md)


```{todo}
Add support for CCFv3 2020
```



## Registration 
* `iDISCO/LSFM-specific atlas <https://pubmed.ncbi.nlm.nih.gov/33063286/>`_



## Example sample?? folder structure after analysis
```bash
.
├── atlas_space  # Dir with images warped to atlas space
├── cfos_seg_ilastik_1  # Example dir with segmentations from ilastik
├── clusters  # Dir with cell/label density CSVs from validate_clusters.py
├── parameters  # Optional dir for things like metadata.txt
├── reg_inputs  # prep_reg.py (autofl image resampled for reg) and brain_mask.py (mask, masked autofl)
├── regional_cell_densities  # CSVs with regional cell densities data
├── reg_outputs  # Outputs from reg.py. These images are typically padded w/ empty voxels. 
└── <raw image or images>
```

## Example experiment folder structure after analysis
```bash
.
├── notes.txt
├── env_var.sh
├── sample_key.csv
├── Control
│   ├── sample01
│   └── sample02
├── Treatment
│   ├── sample03
│   └── sample04
├── atlas
│   ├── gubra_ano_25um_bin.nii.gz
│   ├── gubra_ano_combined_25um.nii.gz
│   ├── gubra_ano_split_25um.nii.gz
│   ├── gubra_mask_25um_wo_ventricles_root_fibers_LH.nii.gz
│   ├── gubra_mask_25um_wo_ventricles_root_fibers_RH.nii.gz
│   └── gubra_template_25um.nii.gz
├── reg_results
├── ilastik_brain_mask
│   ├── brain_mask.ilp
│   ├── sample01_slice_0000.tif
│   ├── sample01_slice_0005.tif
│   ├── sample01_slice_0050.tif
│   ├── ...
│   └── sample04_slice_0050.tif
├── vstats
│   └── Control_v_Treatment
├── cluster_validation
│   └── Control_v_Treatment
└── regional_cell_densities
    ├── Control_sample01_regional_cell_densities.csv
    ├── ...
    └── Treatment_sample04_regional_cell_densities.csv
```