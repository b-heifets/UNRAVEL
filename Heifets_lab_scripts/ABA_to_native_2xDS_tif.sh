#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
Run from sample folder
ABA_histo_2xDS_tif.sh <xy voxel size (um) or m (metadata)> <z voxel size or m>

Inputs:
reg_final/gubra_ano_split_10um_clar_vox.nii.gz

Outputs: 
sample??/reg_final/"$sample"_2xDS_native_gubra_ano_split.nii.gz
'
  exit 1
fi

#Inputs for ABAseg
SampleDir="$PWD"
sample="$(basename $SampleDir)"
SegDir="$PWD"/consensus
Seg="$SegDir"/"$sample"_consensus.nii.gz
ABA="$PWD"/reg_final/gubra_ano_split_10um_clar_downsample_16-bit.nii.gz
image=gubra_ano_split_10um_clar_downsample_16-bit.nii.gz
output_dir=$PWD/reg_final


########################################
####### Atlas to 2xDS res native #######
########################################
if [ ! -f $output_dir/"$sample"_2xDS_native_gubra_ano_split.tif ]; then 

  echo " " ; echo "  Making $output_dir/"$sample"_2xDS_native_gubra_ano_split.tif " ; echo Start: $(date) ; echo " " 

  #Scale native atlas to 2xDS res
  if (( $(ls 488 | wc -l) < 1 )); then echo " " ; echo "./488/tifs MISSING" ; echo " " ; exit 1 ; fi  

  folder_w_warped_image=reg_final #warped atlas (10um res w/ padding)
  fslmaths $folder_w_warped_image/gubra_ano_split_10um_clar_downsample.nii.gz $folder_w_warped_image/$image -odt short

  #################   Calulate cropping  #################

  # Native image size:
  cd 488 ; shopt -s nullglob ; for f in *\ *; do mv "$f" "${f// /_}"; done ; shopt -u nullglob ; cd .. #replace spaces with _ in tif series if needed
  tif=$(ls -1q $PWD/488/*.tif | head -1) #change to other 2xDS res input if needed
  tif_x_dim=$(identify -quiet $tif | cut -f 3 -d " " | cut -dx -f1)
  tif_y_dim=$(identify -quiet $tif | cut -f 3 -d " " | cut -dx -f2)
  tif_z_dim=$(ls -1q $PWD/488/*.tif | wc -l) 

  # 2x downsample dim:
  tif_x_dim_2xDS=$(echo "scale=1;$tif_x_dim/2" | bc -l) #scale=1 means 1 # after the decimal and | bc -l enables floats
  tif_y_dim_2xDS=$(echo "scale=1;$tif_y_dim/2" | bc -l)
  tif_z_dim_2xDS=$(echo "scale=1;$tif_z_dim/2" | bc -l)

  # $folder_w_warped_image/$image has a different orientation than the native tissue
  #y for warped atlas is x for 2xDS 
  #x for warped atlas is y for 2xDS 
  #z for warped atlas is z for 2xDS

  # Calculate dim of output (2xDS native res):
  DS_atlas_x=$(echo "($tif_y_dim_2xDS+0.5)/1" | bc) #rounds
  DS_atlas_y=$(echo "($tif_x_dim_2xDS+0.5)/1" | bc) #rounds
  DS_atlas_z=$(echo "($tif_z_dim_2xDS+0.5)/1" | bc) #rounds

  # Get dim of warped image (10um res w/ padding)
  if [ $(fslinfo $folder_w_warped_image/$image | sed -n '1 p' | awk '{print $1;}') == "filename" ] ; then  #If filename in header, then
    xdim=$(fslinfo $folder_w_warped_image/$image | sed -n '3 p' | awk '{print $2;}') #fslinfo | 3rd line | 2nd word 
    ydim=$(fslinfo $folder_w_warped_image/$image | sed -n '4 p' | awk '{print $2;}')
    zdim=$(fslinfo $folder_w_warped_image/$image | sed -n '5 p' | awk '{print $2;}')
  else
    xdim=$(fslinfo $folder_w_warped_image/$image | sed -n '2 p' | awk '{print $2;}') 
    ydim=$(fslinfo $folder_w_warped_image/$image | sed -n '3 p' | awk '{print $2;}')
    zdim=$(fslinfo $folder_w_warped_image/$image | sed -n '4 p' | awk '{print $2;}')
  fi
  
  # Determine xyz voxel size in microns
  if [ "$2" == "m" ]; then 
    metadata.sh
    xy_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f1)
    z_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f3)
  else
    xy_res=$1
    z_res=$2
  fi 

  # Parameters for resampling $image from 10 um res to 2x downsampled (2xDS) native res: 
  # (10um/2xDS_native_xyres_in_um)*xy_dim and (10um/2xDS_native_zres_in_um)*z_dim
  xy_voxel_size=$(echo "scale=5; ($xy_res)/1000" | bc | sed 's/^\./0./') #3.53 for Zeiss
  z_voxel_size=$(echo "scale=5; ($z_res)/1000" | bc | sed 's/^\./0./') #3.5 for Zeiss
  xy_voxel_size_2xDS=$(echo "scale=5; ($xy_res*2)/1000" | bc | sed 's/^\./0./') #sed adds a 0 before the . if the result<1
  z_voxel_size_2xDS=$(echo "scale=5; ($z_res*2)/1000" | bc | sed 's/^\./0./')

  x_dim_10um_float=$(echo "(0.01/$xy_voxel_size_2xDS)*$xdim" | bc -l) #0.01 mm = 10 um
  y_dim_10um_float=$(echo "(0.01/$xy_voxel_size_2xDS)*$ydim" | bc -l)
  z_dim_10um_float=$(echo "(0.01/$z_voxel_size_2xDS)*$zdim" | bc -l)

  x_dim_10um=$(echo "($x_dim_10um_float+0.5)/1" | bc) #rounds
  y_dim_10um=$(echo "($y_dim_10um_float+0.5)/1" | bc)
  z_dim_10um=$(echo "($z_dim_10um_float+0.5)/1" | bc)
 
  # Determine xyzmin for cropping with fslroi 
  xmin=$((($x_dim_10um-$DS_atlas_x)/2))
  ymin=$((($y_dim_10um-$DS_atlas_y)/2))
  zmin=$((($z_dim_10um-$DS_atlas_z)/2))
  zmax=$(echo "($DS_atlas_z+$zmin-1)" | bc )

  echo " " ; echo "  Scale to 2xDS native, crop padding, reorient $image for $sample" ; echo " " 
  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro to_native_2xDS_tif $PWD/$folder_w_warped_image/$image#$x_dim_10um#$y_dim_10um#$z_dim_10um#$xmin#$DS_atlas_x#$ymin#$DS_atlas_y#$zmin#$zmax#$tif_x_dim#$tif_y_dim#$tif_z_dim

  rm -f $folder_w_warped_image/$image 
  
  mv $folder_w_warped_image/2xDS_native_$image.tif $output_dir/"$sample"_2xDS_native_gubra_ano_split.tif

  echo "  Made 2xDS res $output_dir/"$sample"_2xDS_native_gubra_ano_split.tif" ; echo End: $(date) ; echo " " 
else 
  echo " " ; echo "  2xDS res $output_dir/"$sample"_2xDS_native_gubra_ano_split.tif exists, skipping" ; echo " " 
fi

#Daniel Ryskamp Rijsketic 08/26/2021, 05/10/22-05/23/22, 07/28/22, & 09/23/22 (Heifets lab)
