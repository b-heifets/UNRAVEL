#!/bin/bash

# Alias for sourcing this script added to .bashrc and .zshrc: 
# alias exp=". /path/anes_env_gubra.sh"

# Set environment variables for the current terminal session when this script is sourced
export EXP="exp_name"
export BASE="/path/to/your/experiment"
export DIRS="$BASE/Control/ $BASE/Treatment/"
export PATTERN="sample??"
export LOOP=$(echo "for d in Control Treatment ; do cd \$BASE/\$d ; for s in $PATTERN; do <commands> ; done ; done")
export XY="3.5232063182059137"
export Z="5.0"
export SAMPLE_KEY="$BASE/sample_key.csv"
export BRAIN_MASK_ILP="$BASE/ilastik_brain_mask/brain_mask.ilp"
export ATLAS="$BASE/atlas/gubra_ano_combined_25um.nii.gz"
export SPLIT="$BASE/atlas/gubra_ano_split_25um.nii.gz"
export TEMPLATE="$BASE/atlas/gubra_template_25um.nii.gz"
export MASK="$BASE/atlas/gubra_mask_25um_wo_ventricles_root_fibers_RH.nii.gz"

echo "These environment variables have been set for the current session:" 
echo "EXP: $EXP"
echo "BASE: $BASE"
echo 'DIRS: $BASE/Control/ $BASE/Treatment/'
echo "PATTERN: $PATTERN"
echo "LOOP: $LOOP"
echo "XY: $XY"
echo "Z: $Z"
echo 'SAMPLE_KEY: $BASE/sample_key.csv'
echo 'BRAIN_MASK_ILP: $BASE/ilastik_brain_mask/brain_mask.ilp'
echo 'ATLAS: $BASE/atlas/gubra_ano_combined_25um.nii.gz'
echo 'SPLIT: $BASE/atlas/gubra_ano_split_25um.nii.gz'
echo 'TEMPLATE: $BASE/atlas/gubra_template_25um.nii.gz'
echo 'MASK: $BASE/atlas/gubra_mask_25um_wo_ventricles_root_fibers_RH.nii.gz'