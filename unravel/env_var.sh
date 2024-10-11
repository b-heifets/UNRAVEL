#!/bin/bash

# Set environment variables for the current terminal session when this script is sourced
export BASE="/path/to/your/experiment"  # path to the experiment directory
export DIRS="$BASE/Control/ $BASE/Treatment/"  # sample?? directories should be in these directories
export XY="3.5232"  # xy-pixel size in microns
export Z="5.0"  # z-slice thickness in microns
export SAMPLE_KEY="$BASE/sample_key.csv"  # Column headers: dir_name,condition    Row 2: sample01,control    Row 3: sample02,treatment    ... (conditions should be one word, so use camelCase)
export ATLAS="$BASE/atlas/atlas_CCFv3_2020_30um.nii.gz"  # Allen CCFv3 30um atlas
export SPLIT="$BASE/atlas/atlas_CCFv3_2020_30um_split.nii.gz"  # Allen CCFv3 30um atlas split into left and right hemispheres (left hemisphere region IDs/labels are increased by 20,000. Right hemisphere region IDs/labels are the same as the original atlas)
export TEMPLATE="$BASE/atlas/iDISCO_template_CCFv3_30um.nii.gz"  # Average template. Use iDISCO_template_CCFv3_30um.nii.gz for LSFM or average_template_CCFv3_30um.nii.gz for serial two-photon tomography
export MASK="$BASE/atlas/mask_CCFv3_2020_30um_RH_wo_root_ventricles_fibers_OB.nii.gz"  # Mask for the right hemisphere without root, ventricles, fibers, and olfactory bulb (we exclude fiber tracts for c-Fos)
export LOOP='for d in $DIRS ; do cd $d ; for s in sample??; do echo $s ; done ; done' # This is echoed to the terminal and can be copied to loop through all samples

# Print environment variables when this script is sourced
echo "These environment variables have been set for the current session:" 
echo "BASE: $BASE"
echo 'DIRS: $BASE/Control/ $BASE/Treatment/'
echo "XY: $XY"
echo "Z: $Z"
echo 'SAMPLE_KEY: $BASE/sample_key.csv'
echo 'ATLAS: $BASE/atlas/atlas_CCFv3_2020_30um.nii.gz'
echo 'SPLIT: $BASE/atlas/atlas_CCFv3_2020_30um_split.nii.gz'
echo 'TEMPLATE: $BASE/atlas/average_template_CCFv3_30um.nii.gz'
echo 'MASK: $BASE/atlas/mask_CCFv3_2020_30um_RH_wo_root_ventricles_fibers_OB.nii.gz'
echo "LOOP: $LOOP"  # This can be used to loop through all samples in the Control and Treatment directories

# To source this script, run: 
# . /path/env_var.sh

# To make it easier to source this script, add an alias to .bashrc and .zshrc:
# alias exp=". /path/env_var.sh"

# Then, you can source this script by running:
# exp