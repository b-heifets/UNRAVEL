#!/bin/bash

if [[ $# == 0 || "$1" == "-h" || "$1" == "--help" || "$1" == "help" ]] ; then
  echo '
Run from experiment folder:
to_gubra3.sh <orient code> <x/y res or m> <z res or m> <IF folder name> <ds factor> [sample?? list]


Detailed command info: 
to_gubra3.sh <orientation code> <x/y voxel size in microns or m for metadata> <z voxel size or m> <input folder name> <downsample factor used w/ prep_reg.sh> [leave blank to process all samples or enter sample?? separated by spaces]

Input: ./sample??/"$4"/tifs 
Output: ./sample??/sample??_"$4"_gubra_space.nii.gz

For help on ortientation code, run: reg3.sh -h

If using for voxel-wise stats (glm.sh), consider z-scoring outputs, move them to folder and run fsleyes.sh to confirm alignment
Use mirror.sh to flip samples
'
  exit 1
fi

echo " " ; echo "Running to_gubra3.sh $@ from $PWD" ; echo " " 

if [ $# -gt 5 ]; then 
  sample_array=($(echo "${@:6}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample

  cd "$4" ; shopt -s nullglob ; for f in *\ *; do mv "$f" "${f// /_}"; done ; shopt -u nullglob ; cd .. #replace spaces w/ _ in tif series file names

  # Load tifs, downsample, reorient image, and save as .nii.gz
  if [ "$2" == "m" ]; then 
    metadata.sh
    xy_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f1)
    z_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f3)
  else
    xy_res=$2
    z_res=$3
  fi 
  if (( $5 > 9 )); then x_down=${6}x_down ; else x_down=0${6}x_down ; fi
  ds_nifti=$PWD/niftis/"$sample"_${x_down}_"$4"_chan.nii.gz
  if [ ! -f $ds_nifti ] ; then
    echo "  Converting "$4" tifs to .nii.gz, downsampling, and reorienting for $sample"
    miracl_conv_convertTIFFtoNII_simplified.py -f "$4" -d $5 -o "$sample"_${x_down}_"$4"_chan -vx $xy_res -vz $z_res
  else
    echo "  $ds_nifti exists, skipping "
  fi

  # Warp "$4" to atlas space
  if [ ! -f "$sample"_"$4"_gubra_space.nii.gz ] ; then
    echo " " ; echo "  Warping $ds_nifti to Gubra space" ; echo " "
    mkdir -p parameters
    echo "  Creating ort2std.txt with $1"
    echo "tifdir=$PWD/488" > parameters/ort2std.txt 
    echo "ortcode=$1" >> parameters/ort2std.txt

    # Delete intermediate files in clar_allen_reg in case something was not correct w/ previous run 
    cd clar_allen_reg
    rm -f vox_seg_"$4"_res.nii.gz vox_seg_"$4"_swp.nii.gz reo_"$sample"_0${6}x_down_"$4"_chan_ort.nii.gz reo_"$sample"_0${6}x_down_"$4"_chan_ort_cp_org.nii.gz clar_allen_comb_def.nii.gz clar_res_org_seg.nii.gz
    cd ../ 

    # Make empty volume for copying header
    x_size=$(fslinfo $ds_nifti | head  -2 | tail -1 | cut -f3)
    y_size=$(fslinfo $ds_nifti | head  -3 | tail -1 | cut -f3)
    z_size=$(fslinfo $ds_nifti | head  -4 | tail -1 | cut -f3)
    xy_res=$(fslinfo $ds_nifti | head  -7 | tail -1 | cut -f3)
    z_res=$(fslinfo $ds_nifti | head  -9 | tail -1 | cut -f3)
    fslcreatehd $z_size $x_size $y_size 1 $z_res $xy_res $xy_res 1 0 0 0 4 empty

    # Reorient "$sample"_"$4"_gubra_space.nii.gz
    reo_ds_nii=$PWD/niftis/reo_"$sample"_${x_down}_"$4"_chan.nii.gz
    if [ ! -f $reo_ds_nii ]; then
      echo " " ; echo "  Reorienting $reo_ds_nii"
        fslswapdim $ds_nifti z x y $reo_ds_nii
        fslcpgeom empty.nii.gz $reo_ds_nii
    fi

    echo "  Warping $reo_ds_nii to atlas space"
    miracl_reg_warp_clar_data_to_gubra.sh -r clar_allen_reg -i $reo_ds_nii -o parameters/ort2std.txt -s "$4"

    mv reg_final/reo_"$sample"_${x_down}_"$4"_chan_"$4"_channel_allen_space.nii.gz "$sample"_"$4"_gubra_space.nii.gz

    # rm -f $reo_ds_nii empty.nii.gz
  else 
    echo " " ; echo "  "$sample"_"$4"_gubra_space.nii.gz exists, skipping" ; echo " "
  fi

  cd ..
done 

# Daniel Ryskamp Rijsketic 12/7/21, 07/07/22, 08/25/23, 01/04/24 (Heifets lab)
# Austen Casey adapted to run with any directory name 7/1/23
