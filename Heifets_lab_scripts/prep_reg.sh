#!/bin/bash

if [[ $# == 0 || "$1" == "-h" || "$1" == "--help" || "$1" == "help" ]] ; then
  echo '
From experiment folder with ./sample??/dir/tifs, run:
prep_reg.sh <x/y res or m> <z res or m> <dir w/ autofl tifs> <ds factor> [sample?? list]

Detailed command:
prep_reg.sh <x/y voxel size in microns or m for metadata> <z voxel size or m> <name of folder w/ tifs (e.g., 488)> <int: downsample factor> [leave blank to process all samples or enter sample?? separated by spaces]
 
Outputs: ./sample??/niftis/sample??_??x_down_autofl_chan.nii.gz & clar_res0.05.nii.gz

This output is resampled to 50 um res for registration, so maximize downsampling within this constraint for efficiency.
For example, if x/y res is 3.5232 um and z res is 6 um, then 50 / 6 = 8.33, so use 8 for the ds factor
Before registration, digitally fix tissue in the output with 3D slicer
Tutorial: https://drive.google.com/file/d/1-njlkk3oKDtfa_7HF-ognN33iBJNNlod/view?usp=drive_link
'
  exit 1
fi 

echo " " ; echo "Running prep_reg.sh $@ from $PWD" ; echo " "

if [ $# -gt 4 ]; then 
  sample_array=($(echo "${@:5}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample

    # Get voxel sizes
    if [ "$1" == "m" ]; then 
      metadata.sh
      xy_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f1)
      z_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f3)
    else
      xy_res=$1
      z_res=$2
    fi 

    # Load tifs, downsample, reorient image, and save as .nii.gz
    if (( $4 > 9 )); then x_down=${4}x_down ; else x_down=0${4}x_down ; fi
    ds_nifti=$PWD/niftis/"$sample"_${x_down}_autofl_chan.nii.gz
    if [ ! -f $ds_nifti ] ; then
      echo "  Converting tifs to .nii.gz, downsampling, and reorienting for $sample" ; echo " " 
      miracl_conv_convertTIFFtoNII_simplified.py -f $3 -d $4 -o "$sample"_${x_down}_autofl_chan -vx $xy_res -vz $z_res
    else 
      echo "  $ds_nifti exists, skipping" ; echo " " 
    fi

    # Resample autofl image to 50 micron res
    autofl_50um=$PWD/niftis/clar_res0.05.nii.gz
    if [ ! -f $autofl_50um ] ; then
      echo "  Resampling autofl to 50 micron resolution using linear interpolation"
      zoom.sh $ds_nifti m m m 50 uint16 ; mv ${ds_nifti::-7}_50um.nii.gz $autofl_50um
    else 
      echo "  $autofl_50um exists, skipping" ; echo " " 
    fi

    # Convert 50 um autofl img to tif series
    
    if [ ! -d niftis/autofl_50um ]; then
      echo "  Converting 50 um autofl to tif series"
      cd niftis
      mkdir -p autofl_50um
      nii_to_tifs.py -i $autofl_50um -o autofl_50um
      cd ..
    elif (( $(ls niftis/autofl_50um | wc -l) > 1 )); then 
      echo "  niftis/autofl_50um/*.tif exists, skipping" ; echo " " 
    else 
      echo "  CHECK $PWD/niftis/autofl_50um exists, but is empty. Delete and rerun prep_reg.sh"
    fi

  cd ..
done 

#Daniel Ryskamp Rijsketic 09/10/21, 07/07/22, & 08/24-25/23 (Heifets lab)



