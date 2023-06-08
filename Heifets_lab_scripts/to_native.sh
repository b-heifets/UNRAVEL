#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
Run this from sample folder: 
 
to_native.sh <path/image.nii.gz to warp to native space and/or scale> <xy voxel size (um) or m (metadata)> <z voxel size or m> <clusters_folder> <output_folder>

Outputs: ./clusters/clusters_folder/output_folder/native_<image>.nii.gz
'
  exit 1
fi
echo " " ; echo "Running to_native.sh $@ from ${PWD##*/}" ; echo " " 

if (( $(ls 488 | wc -l) < 1 )); then echo " " ; echo "./488/tifs MISSING" ; echo " " ; exit 1 ; fi

image=${1##*/}
path=${1%/*}
output_dir=$PWD/$4/$5
mkdir -p clusters $4 $output_dir
sample=${PWD##*/}

if [ $1 == $PWD/reg_final/gubra_ano_split_10um_clar_downsample.nii.gz ]; then
  output=$PWD/reg_final/"$sample"_native_gubra_ano_split.nii.gz
else 
  output=$output_dir/native_$image
fi

if [ ! -f $output ]; then 
  echo " " ; echo "  Warping $1 to native space for $sample" ; echo Start: $(date) ; echo " " 

  if [ $1 == $PWD/reg_final/gubra_ano_split_10um_clar_downsample.nii.gz ]; then
    image=gubra_ano_split_10um_clar_downsample_16-bit.nii.gz
    folder_w_warped_image=reg_final #warped atlas (10um res w/ padding)
    fslmaths $folder_w_warped_image/gubra_ano_split_10um_clar_downsample.nii.gz $folder_w_warped_image/$image -odt short
  else 
    folder_w_warped_image=clar_allen_reg #warped atlas (10um res w/ padding)

    # Warp from Gubra to native space (output has padding and 10 um resolution) and convert to 8-bit
    if [ -f clar_allen_reg/$image ]; then rm clar_allen_reg/$image ; fi
    antsApplyTransforms -d 3 -r reg_final/clar_downsample_res10um.nii.gz -i "$1" -n NearestNeighbor -t clar_allen_reg/allen_clar_ants1Warp.nii.gz clar_allen_reg/allen_clar_ants0GenericAffine.mat clar_allen_reg/init_tform.mat -o clar_allen_reg/$image --float # NearestNeighbor is ~6x faster than MultiLabel, which smooths cluster edges 
    float=$(fslstats clar_allen_reg/$image -R | cut -d' ' -f2)
    int=${float%.*}
    if (( "$int" < "255" )); then 
      fslmaths clar_allen_reg/$image clar_allen_reg/$image -odt char #-odt char converts to 8-bit
    fi
  fi

  #################   Calulate cropping  #################

  # Native image size:
  cd 488 ; shopt -s nullglob ; for f in *\ *; do mv "$f" "${f// /_}"; done ; shopt -u nullglob ; cd .. #replace spaces with _ in tif series if needed
  tif=$(ls -1q $PWD/488/*.tif | head -1) #change to other full res input if needed
  tif_x_dim=$(identify -quiet $tif | cut -f 3 -d " " | cut -dx -f1)
  tif_y_dim=$(identify -quiet $tif | cut -f 3 -d " " | cut -dx -f2)
  tif_z_dim=$(ls -1q $PWD/488/*.tif | wc -l) 

  # 2x downsample dim:
  tif_x_dim_2xDS=$(echo "scale=1;$tif_x_dim/2" | bc -l) #scale=1 means 1 # after the decimal and | bc -l enables floats
  tif_y_dim_2xDS=$(echo "scale=1;$tif_y_dim/2" | bc -l)
  tif_z_dim_2xDS=$(echo "scale=1;$tif_z_dim/2" | bc -l)

  # $folder_w_warped_image/$image has a different orientation than the native tissue
  #y for warped atlas is x for full 
  #x for warped atlas is y for full 
  #z for warped atlas is z for full

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
    xy_res=$2
    z_res=$3
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

  echo " " ; echo "  Scale to 2xDS native, crop padding, reorient $image and scale native res for $sample" ; echo " " 
  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro to_native $PWD/$folder_w_warped_image/$image#$x_dim_10um#$y_dim_10um#$z_dim_10um#$xmin#$DS_atlas_x#$ymin#$DS_atlas_y#$zmin#$zmax#$tif_x_dim#$tif_y_dim#$tif_z_dim > /dev/null 2>&1

  rm -f $folder_w_warped_image/$image 
  
  # Convert to .nii.gz and move
  if [ $1 == $PWD/reg_final/gubra_ano_split_10um_clar_downsample.nii.gz ]; then
    mv $folder_w_warped_image/native_$image.nii $folder_w_warped_image/"$sample"_native_gubra_ano_split.nii
    gzip -f -9 $folder_w_warped_image/"$sample"_native_gubra_ano_split.nii #nii to nii.gz
    cp $folder_w_warped_image/"$sample"_native_gubra_ano_split.nii.gz $output_dir/"$sample"_native_gubra_ano_split.nii.gz
  else 
    mv $folder_w_warped_image/native_$image.nii $output_dir/native_${image::-7}.nii
    gzip -f -9 $output_dir/native_${image::-7}.nii 
  fi

  echo " " ; echo "  Made full res $output_dir/native_$image" ; echo End: $(date) ; echo " " 
else 
  echo " " ; echo "  Full res $output_dir/native_$image exists, skipping" ; echo " " 
fi


#Daniel Ryskamp Rijsketic 08/26/2021 & 05/10/22-05/23/22 & 07/28/22 (Heifets lab)
#Partly adapted from miracl_reg_clar-allen_whole_brain.sh (Maged Goubran) and Miracl_get_roi_danb.py (Dan Barbosa from Halpern lab)
