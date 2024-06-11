# Guide

## Back up raw data
   * For Heifets lab members, we keep one copy of raw data on an external drive and another on a remote server (Dan and Austen have access)

## Stitch z-stacks if needed
   * We use [ZEN (blue edition)](https://www.micro-shop.zeiss.com/en/us/softwarefinder/software-categories/zen-blue/) since we have a [Zeiss Lightsheet 7](https://www.zeiss.com/microscopy/en/products/light-microscopes/light-sheet-microscopes/lightsheet-7.html)


:::{admonition} Batch stitching settings
:class: note dropdown
```{figure} _static/batch_stitching_1.JPG
:alt: Batch stitching settings
:height: 500px
:align: center
Select a mid-stack reference slice. Ideally, tissue will be present in each tile of the reference slice. 
```
:::

:::{admonition} Running batch stitching
:class: note dropdown
```{figure} _static/batch_stitching_2.JPG
:alt: Batch stitching settings
:align: center
```
* Drag and drop images to be stitched into this section. 
* For each image in the list, apply the stitching settings one by one (do not go back to a prior image, as settings will no longer stick).
* Select all images (control + A or shift and click)
* Click "Check All"
* Click "Run Selected" 
:::

```{admonition} Open source options for stitching
:class: tip dropdown
* [TeraStitcher](https://abria.github.io/TeraStitcher/)
* [ZetaStitched](https://github.com/lens-biophotonics/ZetaStitcher)
```




## Create sample folders 
   * Make a folder named after each condition in the experiment folder(s)
```
. # This root level folder is referred to as the experiment directory (exp dir) 
├── Control
└── Treatment
```
   * Make sample folders in the directories named after each condition

```{admonition} Name sample folders like sample01, sample02, ...
:class: tip dropdown

This makes batch processing easy.

Use a csv, Google sheet, or whatever else for linking sample IDs to IDs w/ this convention.

Other patterns (e.g., sample???) may be used (commands/scripts have a -p option for that).
```

```
.
├── Control
│   ├── sample01
│   └── sample02
└── Treatment
    ├── sample03
    └── sample04
```

## Add raw or stitched images to each sample?? folder

   * For example, image.czi, image.h5, or folder(s) with tif series

```
.
├── Control
│   ├── sample01
│   │   └── <raw image(s)>
│   └── sample02
│       └── <raw image(s)>
└── Treatment
    ├── sample03
    │   └── <raw image(s)>
    └── sample04
        └── <raw image(s)>
```

```{admonition} Data can be distributed across multiple drives 
:class: tip dropdown

Paths to each experiment directory may be passed into scripts using the -e flag for batch processing

This is useful if there is not enough storage on a single drive. 

Also, spreading data across ~2-4 external drives allows for faster parallel processing (minimizes i/o botlenecks) 

If SSDs are used, distrubuting data may not speed up processing as much. 
```

## Make an exp_notes.txt
:::{admonition} exp_notes.txt
:class: tip dropdown
This helps with keeping track of paths, commands, etc..
```bash
cd <path/exp_dir>  # Change the current working directory to an exp dir
touch exp_notes.txt  # Make the .txt file
```
:::

:::{admonition} Automatic logging of commands
:class: tip dropdown
Most scripts log the command used to run them, appending to ./.command_log.txt.

This is a hidden file. Use control+h to view it on Linux or command+shift+. to view it on MacOS.
```bash
# View command history for the current working directory
cat .command_log.txt  

# View last 10 lines
cat .command_log.txt | tail -10  
```
:::


## Make a sample_key.csv with this organization: 
   * dir_name,condition
   * sample01,control
   * sample02,treatment
   * ...

## Define common variables in a shell script

:::{admonition} env_var.sh
:class: note dropdown

* To make commands easier to run, define common variables in a shell script (e.g., env_var.sh)
* Source the script to load variables in each terminal session
* Copy /UNRAVEL/_other/env_var_gubra.sh to an exp dir and update each variable

Add this line to your .bashrc or .zshrc terminal config file: 
```bash
alias exp=". /path/env_var.sh"  # Update the /path/name.sh
```

```bash
# Reopen the terminal or source the updated config file to apply changes
. ~/.zshrc

# Run the alias to source the variables before using them to run commands/scripts
exp
```
:::


## Commands/scripts
For help/info on a command/script, run
```bash
<command> -h
```

or 
```bash
<script>.py -h 
```


## Optional: clean tifs
   * If raw data is in the form of a tif series, consider running: 
```bash
clean_tifs -t <dir_name> -v -m -e $DIRS
```
```{admonition} clean_tifs
:class: tip dropdown
This will remove spaces from files names and move files other than *.tif to the parent directory
```


## Typical analysis workflow: 

This section provides an overview of common commands available in UNRAVEL, ~organized by their respective steps. 

For a complete list of commands, please view the [project.scripts] section of the pyproject.toml in the root directory of the [UNRAVEL repository](https://github.com/b-heifets/UNRAVEL/tree/dev). Also look here for the name of scripts associated w/ each command.  


Variables below (e.g., $XY) can be defined in a script (e.g., env_var.sh) that can be sourced to load them in the current terminal session. See the [Guide](guide.md) for more info.


- [Registration](#registration)
    - metadata 
    - prep_reg
    - copy_tifs
    - brain_mask
    - reg
    - check_reg
- [Segmentation](#segmentation)
    - copy_tifs
    - seg
- [Voxel-wise stats](#voxel-wise-stats)
    - prep_vstats
    - z_score
    - agg_files_from_dirs
    - whole_to_avg
    - avg
    - vstats
- [Cluster correction](#cluster-correction)
    - fdr_range
    - fdr
    - recursive_mirror_index
- [Cluster validation](#cluster-validation)
    - validate_clusters
    - summary
- [Region-wise stats](#region-wise-stats)
    - rstats
    - rstats_summary
- [Other](#other)
    - nii_info
<br>
<br>
<br>



## Registration

### `metadata`
Extract or specify metadata (outputs to ./sample??/parameters/metadata.txt). Add the resolutions to env_var.sh. 
```bash
metadata -i <rel_path/full_res_img>  # Glob patterns work for -i
metadata -i <tif_dir> -x $XY -z $Z  # Specifying x and z voxel sizes in microns
```
:::{admonition} Module Documentation Test
:class: note dropdown

You can find more information about this module in the
:py:mod:`unravel.register.metadata`.
:::

<br>

### `prep_reg` 
Prepare autofluo images for registration (resample to a lower resolution)
```bash
prep_reg -i *.czi -x $XY -z $Z -v  # -i options: tif_dir, .h5, .zarr, .tif
```
<br>

### `copy_tifs`
Copy resampled autofluo .tif files for segmenting the brain with ilastik
```bash
copy_tifs -i reg_inputs/autofl_??um_tifs -s 0000 0005 0050 -o $(dirname $BRAIN_MASK_ILP) -e $DIRS
```  
<br>

### `brain_mask`
Makes reg_inputs/autofl_??um_brain_mask.nii.gz and reg_inputs/autofl_??um_masked.nii.gz
```bash
brain_mask -ilp $BRAIN_MASK_ILP -v -e $DIRS
```
<br>

### `reg`
Register average template brain/atlas to resampled autofl brain. 
```bash
reg -m $TEMPLATE -bc -pad -sm 0.4 -ort RPS -a $ATLAS -v -e $DIRS  # If all samples have the same RPS+ orientation

# If orientations vary, make a ./sample??/parameters/ort.txt with the 3 letter orientation for each sample and run
for d in $DIRS ; do cd $d ; for s in sample?? ; do reg -m $TEMPLATE -bc -pad -sm 0.4 -ort $(cat $s/parameters/ort.txt) -a $ATLAS -v -d $PWD/$s ; done ; done 
```
<br>

### `check_reg`
Check the registration of images by copying the following to a common location: 
* sample??/reg_outputs/autofl_??um_masked_fixed_reg_input.nii.gz
* sample??/reg_outputs/atlas_in_tissue_space.nii.gz
```bash
check_reg -e $DIRS -td $BASE/reg_results
```
* View these images with [FSLeyes](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FSLeyes)
* Allen brain atlas coloring:
    * Replace this /home/user/.config/fsleyes/luts/random.lut (location on Linux) with UNRAVEL/_other/fsleyes_luts/random.lut
    * Select the atlas and change "3D/4D volume" to "Label image"

<br>
<br>
<br>




## Segmentation

### `copy_tifs`
Copy full res tif files to a common location for training Ilastik to segment labels of interest (e.g., 3 tifs from each sample or 3 tifs from 3 samples / condition)
```bash
copy_tifs -i <raw_tif_dir> -s 0100 0500 1000 -o ilastik_segmentation -e $DIRS -v
```
<br>

### `seg`
Perform pixel classification using Ilastik.
```bash
seg -i <*.czi, *.h5, or dir w/ tifs> -o seg_dir -ilp $BASE/ilastik_segmentation/trained_ilastik_project.ilp -l 1 -v -e $DIRS 
# Make binary segmentation for multiple labels like: -l 1 2
```
<br>
<br>
<br>



## Voxel-wise stats

### `prep_vstats`
Preprocess immunofluo images and warp them to atlas space for voxel-wise statistics.
```bash
prep_vstats -i cFos -rb 4 -x $XY -z $Z -o cFos_rb4_atlas_space.nii.gz -v -e $DIRS
# Use -s 3 for 3x3x3 spatial averaging if images are noisey
# Use a larger rolling ball radius if you want to preserve more diffuse signal (e.g., 20)
```
<br>

### `z_score`
Z-score atlas space images using tissue masks (from brain_mask) and/or an atlas mask.
* atlas_space is a folder in ./sample??/
```bash
z-score -i atlas_space/sample??_cFos_rb4_atlas_space.nii.gz -v -e $DIRS
```
<br>

### `agg_files_from_dirs`
Aggregate images for voxel-wise stats
```bash
agg_files_from_dirs -i atlas_space/sample??_cFos_rb4_atlas_space_z.nii.gz -e $DIRS -v
```
<br>

### `whole_to_avg`
Smooth and average left and right hemispheres together
```bash
# Run this in the folder with all of the .nii.gz images
whole_to_LR_avg -k 0.1 -tp -v # A 0.05 mm - 0.1 mm kernel radius is recommended for smoothing
```
<br>

### `prepend_conditions`
Prepend conditions to filenames based on a CSV w/ this organization
* dir_name,condition
* sample01,control
* sample02,treatment
```bash
prepend_conditions -sk $SAMPLE_KEY -f
```
<br>

### `vstats`
Run voxel-wise stats using FSL's randomise_parallel command. 
* Outputs in ./stats/
    * vox_p maps are uncorrected 1 - p value maps
    * tstat1: group1 > group2
    * tstat2: group2 > group1
    * fstat*: f contrast w/ ANOVA design (non-directional p value map)
```bash
vstats -mas mask.nii.gz -v
```
<br>
<br>
<br>




## Cluster correction
These commands are useful for multiple comparison correction of 1 - p value maps to define clusters of significant voxels. 

### `avg`
Average *.nii.gz images 
* Visualize absolute and relative differences in intensity
* Use averages from each group to convert non-directioanl 1 - p value maps into directional cluster indices
```bash
avg -i *.nii.gz # outputs avg.nii.gz (process one group at a time or separate into folders)
```
<br>

### `fdr_range`
Outputs a list of FDR q values that yeild clusters.
```bash
# Basic usage
fdr_range -i vox_p_tstat1.nii.gz -mas mask.nii.gz

# Perform FDR correction on multiple directional 1 - p value maps
for j in *_vox_p_*.nii.gz ; do q_values=$(fdr_range -mas $MASK -i $j) ; fdr_ -mas $MASK -i $j -q $q_values ; done

# Convert a non-directioanl 1 - p value map into a directional cluster index
q_values=$(fdr_range -i vox_p_fstat1.nii.gz -mas $MASK) ; fdr_ -i vox_p_fstat1.nii.gz -mas $MASK -o fstat1 -v -a1 Control_avg.nii.gz -a2 Deep_avg.nii.gz -q $q_values
```
<br>

### `fdr_`
Perform FDR correction on a 1 - p value map to define clusters
```bash
fdr_ -i vox_p_tstat1.nii.gz -mas mask.nii.gz -q 0.05
```
<br>

### `recursive_mirror_index`
Recursively flip the content of rev_cluster_index.nii.gz images
* Run this in the ./stats/ folder to process all subdirs with reverse cluster maps (cluster IDs go from large to small)
```bash
# Use -m RH if a right hemisphere mask was used (otherwise use -m LH)
recursive_mirror_index -m RH -v
```
<br>
<br>
<br>



## Cluster validation

### `validate_clusters`
Warps cluster index from atlas space to tissue space, crops clusters, applies segmentation mask, and quantifies cell/label densities
```bash
# Basic usage:
validate_clusters -e <experiment paths> -m <path/rev_cluster_index_to_warp_from_atlas_space.nii.gz> -s seg_dir -v

# Processing multiple FDR q value thresholds and both hemispheres:
for q in 0.005 0.01 0.05 0.1 ; do for side in LH RH ; do validate_clusters -e $DIRS -m path/vstats/contrast/stats/contrast_vox_p_tstat1_q${q}/contrast_vox_p_tstat1_q${q}_rev_cluster_index_${side}.nii.gz -s seg_dir/sample??_seg_dir_1.nii.gz -v ; done ; done
```
<br>

### `summary`
Aggregates and analyzes cluster validation data from validate_clusters
* Update parameters in /UNRAVEL/unravel/cluster_stats/valid_clusters_summary.ini and save it with the experiment
```bash
summary -c path/valid_clusters_summary.ini -e $DIRS -cvd '*' -vd path/vstats_dir -sk $SAMPLE_KEY --groups group1 group2 -v
```
group1 and group2 must match conditions in the sample_key.csv
<br>
<br>
<br>



## Region-wise stats

### `rstats`
Perform regional cell counting (label density measurements needs to be added)
```bash
# Use if atlas is already in native space from to_native.py
rstats -s rel_path/segmentation_image.nii.gz -a rel_path/native_atlas_split.nii.gz -c Saline --dirs sample14 sample36

# Use if native atlas is not available; it is not saved (faster)
rstats -s rel_path/segmentation_image.nii.gz -m path/atlas_split.nii.gz -c Saline --dirs sample14 sample36
```
<br>

### `rstats_summary`
Plot cell densities for each region and summarize results.
* CSV columns: 
    * Region_ID,Side,Name,Abbr,Saline_sample06,Saline_sample07,...,MDMA_sample01,...,Meth_sample23,...
```bash
rstats_summary --groups Saline MDMA Meth -d 10000 -hemi r
```
<br>
<br>
<br>



## Other

### `nii_info`
Display information about a NIfTI image.
```bash
nii_info -i image.nii.gz
```
<br>



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
└── image.czi # Or other raw/stitched image type
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

```{todo}
Add support for CCFv3 2020
```