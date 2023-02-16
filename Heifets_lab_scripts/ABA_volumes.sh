#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo "
ABA_volumes.sh <path/image.nii.gz (w/ same dim as atlas)> [xy voxel size in um] [z voxel size] [path/custom_atlas]

Output: <image_w_atlas_intensities>_region_volumes.csv 

Default_atlas=usr/local/miracl/atlases/ara/gubra/gubra_ano_combined_25um.nii.gz
"
  exit 1
fi

echo " " ; echo "Running ABA_volumes.sh from $PWD " ; echo " " 

image=$(echo $1 | sed "s/['\"]//g") #remove ' if dropping image into terminal 
if [ ! -d ${image%/*} ]; then image=$PWD/$image ; fi #add path to image if needed

if [ ! -f ${image::-7}_bin.nii.gz ]; then fslmaths $image -bin ${image::-7}_bin.nii.gz -odt char ; fi

if [ $# == 4 ]; then 
  xy_res=$2
  z_res=$3
  if [ ! -f ${image::-7}_ABA.nii.gz ]; then fslmaths ${image::-7}_bin.nii.gz -mul $4 ${image::-7}_ABA.nii.gz ; fi
else
  xy_res=25 #voxel size in microns
  z_res=25
  if [ ! -f ${image::-7}_ABA.nii.gz ]; then fslmaths ${image::-7}_bin.nii.gz -mul /usr/local/miracl/atlases/ara/gubra/gubra_ano_combined_25um.nii.gz ${image::-7}_ABA.nii.gz ; fi
fi

rm ${image::-7}_bin.nii.gz

####### Generate histogram CSVs #######
fslstats ${image::-7}_ABA.nii.gz -H 65535 0 65535 > ${image::-7}_ABA_region_volumes.csv

####### Generate *region_volumes.csv #######
if [ "$4" == "split" ]; then atlas_type="split" ; else atlas_type="combined" ; fi
python3 /usr/local/miracl/miracl/seg/ABA_volumes.py ${image::-7}_ABA_region_volumes.csv $xy_res $z_res $atlas_type

echo " " ; echo "  Made ${image::-7}_ABA_region_volumes.csv" ; echo " " 

#Daniel Ryskamp Rijsketic 10/26-27/22 (Heifets lab)
