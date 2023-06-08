#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo "
sunburst.sh <path/[validated]_cluster_index]> [atlas xy voxel size in um] [atlas z voxel size] [path/custom_atlas]

Output: <path/[validated]_cluster_index>_sunburst.csv and sunburst_RGBs.csv

Default_atlas=usr/local/miracl/atlases/ara/gubra/gubra_ano_combined_25um.nii.gz

For a bilateral brain, first mask out the left or right hemisphere for separate sunburst plots.

Use Flourish Studios to make sunburst plot of region volumes (https://app.flourish.studio/)
Data tab: Paste in data from csv, categories columns = Depth_* columns, Size by = Volumes column, 
Preview tab: Hierarchy -> Depth to 10, Colors -> paste RGB codes into Custom overrides
"
  exit 1
fi

echo " " ; echo "Running sunburst.sh from $PWD " ; echo " " 

index=$(echo $1 | sed "s/['\"]//g")
if [ ! -d ${index%/*} ]; then index=$PWD/$index ; fi #add path to image if needed

if [ ! -f ${index::-7}_bin.nii.gz ]; then fslmaths $index -bin ${index::-7}_bin.nii.gz -odt char ; fi

if [ $# == 4 ]; then 
  xy_res=$2
  z_res=$3
  if [ ! -f ${index::-7}_ABA.nii.gz ]; then fslmaths ${index::-7}_bin.nii.gz -mul $4 ${index::-7}_ABA.nii.gz ; fi
else
  xy_res=25 #voxel size in microns
  z_res=25
  if [ ! -f ${index::-7}_ABA.nii.gz ]; then fslmaths ${index::-7}_bin.nii.gz -mul /usr/local/miracl/atlases/ara/gubra/gubra_ano_combined_25um.nii.gz ${index::-7}_ABA.nii.gz ; fi
fi

rm ${index::-7}_bin.nii.gz

####### Generate histogram CSVs #######
fslstats ${index::-7}_ABA.nii.gz -H 65535 0 65535 > ${index::-7}_sunburst.csv

####### Convert to region volumes and append to sunburst_IDPath_Abbrv.csv #######
python3 /usr/local/miracl/miracl/seg/sunburst.py ${index::-7}_sunburst.csv $xy_res $z_res

cp /usr/local/miracl/miracl/seg/sunburst_RGBs.csv $(dirname $index)

echo " " ; echo "  Made ${index::-7}_sunburst.csv" ; echo " " 

#Daniel Ryskamp Rijsketic 11/03/22 (Heifets lab)
