#!/bin/bash

if [ $# == 0 ] || [ "$1" == "-h" ] || [ "$1" == "--help" ] || [ "$1" == "help" ]; then
  echo '
Run this from sample folder: 
 
to_native2.sh <path/image.nii.gz to warp to native space and/or scale> <xy voxel size (um) or m (metadata)> <z voxel size or m><clusters_folder> <output_folder> [tifs folder (Default: 488)] 

Outputs: ./clusters/<clusters_folder>/<output_folder>/native_<image>.nii.gz
'
  exit 1
fi
echo " " ; echo "Running to_native2.sh $@ from ${PWD##*/}" ; echo " " 

# Set tifs dir default if not specified and check if it exists (used for scaling to these dims)
tifs_dir=$6
if [[ -z $tifs_dir ]]; then
  tifs_dir="488" 
fi 
if (( $(ls $tifs_dir | wc -l) < 1 )); then echo " " ; echo "./$tifs_dir/tifs MISSING" ; echo " " ; exit 1 ; fi

lower_bit_depth() {
  local image=$1
  local dtype=$2

  # Lower bit depth of output (--float is the lowest output bit depth in prior step)
  if [ "$dtype" == "FLOAT32" ]; then
    local float=$(fslstats $image -R | cut -d' ' -f2)
    local int=${float%.*}
    if (( "$int" < "255" )); then 
      echo "  Lowering bit-depth from $dtype to UINT8" ; echo " " 
      fslmaths $image $image -odt char # -odt char converts to 8-bit
    elif (( "$int" < "32767" )); then 
      echo "  Lowering bit-depth from $dtype to INT16" ; echo " " 
      fslmaths $image $image -odt short # -odt char converts to 16-bit
    fi 
  fi
}

path_img=$(echo $1 | sed "s/['\"]//g")
image=${1##*/}

output_dir=$PWD/$4/$5
mkdir -p clusters $4 $output_dir

sample=${PWD##*/}

if [ $image == gubra_ano_split_10um_clar_downsample.nii.gz ]; then
  output=$PWD/reg_final/"$sample"_native_gubra_ano_split.nii.gz
else
  output=$output_dir/native_$image
fi

if [ ! -f $output ]; then 
  echo " " ; echo "  Warping $path_img to native space for $sample" ; echo Start: $(date) ; echo " " 

  # Lower bit depth of input ((--float is lowest output bit depth in prior step)
  dtype=$(fslinfo $path_img | head -1 | cut -f2)
  lower_bit_depth $path_img $dtype    

  if [ $path_img == $PWD/reg_final/gubra_ano_split_10um_clar_downsample.nii.gz ]; then 
    warped_img=$path_img #warped atlas (10um res w/ padding)
  else 
    warped_img=$PWD/clar_allen_reg/$image 
    if [ -f $warped_img ]; then rm $warped_img ; fi 
    # Warp from Gubra to native space (output has padding and 10 um resolution)
    antsApplyTransforms -d 3 -r reg_final/clar_downsample_res10um.nii.gz -i $path_img -n NearestNeighbor -t clar_allen_reg/allen_clar_ants1Warp.nii.gz clar_allen_reg/allen_clar_ants0GenericAffine.mat clar_allen_reg/init_tform.mat -o $warped_img --float # NearestNeighbor is ~6x faster than MultiLabel, which smooths cluster edges.
    echo " "  
    # Lower bit depth of output 
    lower_bit_depth $warped_img "FLOAT32" #lowest output bit depth in prior step
  fi

  # Padding added to all sides of 50 um autofl image during registration.sh: c3d $biasclar -pad 15% 15% 0 -o ${padclar} 
  # Inputs for calculating how to remove padding
  res_of_reg_final_outputs=$(fslinfo reg_final/clar_downsample_res10um.nii.gz | sed -n '7 p' | cut -f3) # In mm
  res_of_clar_allen_reg=$(fslinfo clar_allen_reg/clar.nii.gz | sed -n '7 p' | cut -f3)
  reg_file_pre_padding=clar_allen_reg/clar_res0.05_bias.nii.gz
  reg_file_post_padding=clar_allen_reg/clar_res0.05_pad.nii.gz

  # Get dims of 50 um autofl img... 
  xsize_wo_padding_50um=$(fslinfo $reg_file_pre_padding | sed -n '2 p' | cut -f3) 
  ysize_wo_padding_50um=$(fslinfo $reg_file_pre_padding | sed -n '3 p' | cut -f3) 
  zsize_wo_padding_50um=$(fslinfo $reg_file_pre_padding | sed -n '4 p' | cut -f3) 

  # and autofl img w/ 15% padding
  xsize_w_padding_50um=$(fslinfo $reg_file_post_padding | sed -n '2 p' | cut -f3) 
  ysize_w_padding_50um=$(fslinfo $reg_file_post_padding | sed -n '3 p' | cut -f3) 
  zsize_w_padding_50um=$(fslinfo $reg_file_post_padding | sed -n '4 p' | cut -f3) 

  # Get # of pixels of padding for clar_res0.05_pad.nii.gz
  xmin_50um=$((( ($xsize_w_padding_50um - $xsize_wo_padding_50um)/2 ))) 
  ymin_50um=$((( ($ysize_w_padding_50um - $ysize_wo_padding_50um)/2 )))
  zmin_50um=$((( ($zsize_w_padding_50um - $zsize_wo_padding_50um)/2 )))

  # Find zoom factor of reverse warped image relative to 50 um autofl image
  zf=$(printf "%.0f" $(echo "($res_of_clar_allen_reg / $res_of_reg_final_outputs)" | bc -l)) # bc eeded for math w/ floats; printf for int

  # Get # of pixels to trim with new res
  xmin_rev_warped_img=$((( $xmin_50um * $zf )))
  ymin_rev_warped_img=$((( $ymin_50um * $zf )))
  zmin_rev_warped_img=$((( $zmin_50um * $zf )))

  # Find img dims at new res
  xsize_rev_warped_img=$((( $xsize_wo_padding_50um * $zf )))
  ysize_rev_warped_img=$((( $ysize_wo_padding_50um * $zf )))
  zsize_rev_warped_img=$((( $zsize_wo_padding_50um * $zf )))

  # Trim padding from rev warped image
  echo " " ; echo "  Crop padding for $warped_img"

  fslroi $warped_img ${warped_img::-7}_wo_padding $xmin_rev_warped_img $xsize_rev_warped_img $ymin_rev_warped_img $ysize_rev_warped_img $zmin_rev_warped_img $zsize_rev_warped_img

  # Native image size:
  cd $tifs_dir ; shopt -s nullglob ; for f in *\ *; do mv "$f" "${f// /_}"; done ; shopt -u nullglob ; cd .. #replace spaces with _ in tif series if needed
  tif=$(ls -1q $PWD/$tifs_dir/*.tif | head -1) #change to other full res input if needed
  tif_x_dim=$(identify -quiet $tif | cut -f 3 -d " " | cut -dx -f1)
  tif_y_dim=$(identify -quiet $tif | cut -f 3 -d " " | cut -dx -f2)
  tif_z_dim=$(ls -1q $PWD/$tifs_dir/*.tif | wc -l) 

  echo " " ; echo "  Reorient warped image and scale to native res" ; echo " " 
  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro to_native2 $warped_img#$tif_x_dim#$tif_y_dim#$tif_z_dim > /dev/null 2>&1

  # Determine xyz voxel size in microns
  if [ "$2" == "m" ]; then 
    metadata.sh
    xy_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f1)
    z_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f3)
  else
    xy_res=$2
    z_res=$3
  fi 

  # Make tmp img for copying resolution
  fslcreatehd $tif_x_dim $tif_y_dim $tif_z_dim 1 $xy_res $xy_res $z_res 1 0 0 0 4 to_native_tmp_img

  echo "  gzip compressing .nii output" ; echo " " 
  if [ $path_img == $PWD/reg_final/gubra_ano_split_10um_clar_downsample.nii.gz ]; then
    output=reg_final/"$sample"_native_gubra_ano_split.nii
    mv reg_final/native_$image.nii $output
    gzip -f -9 $output #nii to nii.gz
    fslcpgeom to_native_tmp_img $output.gz
    rm to_native_tmp_img.nii.gz
    cp $output.gz $output_dir/"$sample"_native_gubra_ano_split.nii.gz
  else 
    mv clar_allen_reg/native_$image.nii $output_dir/native_${image::-7}.nii
    gzip -f -9 $output_dir/native_${image::-7}.nii 
    fslcpgeom to_native_tmp_img $output_dir/native_${image::-7}.nii 
    rm to_native_tmp_img.nii.gz
    ### rm -f $warped_img 
  fi

  echo " " ; echo "  Made full res $output_dir/native_$image" ; echo End: $(date) ; echo " " 
else 
  echo " " ; echo "  Full res $output_dir/native_$image exists, skipping" ; echo " " 
fi


#Daniel Ryskamp Rijsketic 08/26/2021, 05/10/22-05/23/22, 07/28/22, & 09/19/23 (Heifets lab)
#Austen Casey 08/01/23 (Heifets lab)
#Partly adapted from miracl_reg_clar-allen_whole_brain.sh (Maged Goubran) and Miracl_get_roi_danb.py (Dan Barbosa from Halpern lab)
