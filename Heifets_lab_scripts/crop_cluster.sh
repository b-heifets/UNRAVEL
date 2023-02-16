#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
Run this from sample folder:  
crop_cluster.sh <./clusters_folder/bounding_boxes/sample??_native_cluster_x_fslstats_w.txt> <image_type> <path/image_to_crop.nii.gz or path/first_tif_in_series_to_crop> 

crop cluster in 3D
'
  exit 1
fi

echo " " ; echo "Running crop_cluster.sh $@ from $PWD" ; echo " " 

txt=${1##*/}
bounding_boxes_path=${1%/*}
output_path=${bounding_boxes_path%/*}/$2_cropped
mkdir -p $output_path ${bounding_boxes_path%/*}/cluster_volumes

image=${3##*/}
image_path=${3%/*}

#Define output filenames
suffix=${txt::-15} #trim _fslstats_w.txt to make suffix: sample??_native_cluster_*
if [ $2 == "clusters" ]; then output=crop_$suffix 
elif [ $2 == "consensus" ]; then output=crop_consensus_$suffix
elif [ $2 == "ABAconsensus" ]; then output=crop_ABAconsensus_$suffix
elif [ $2 == "ABAcluster" ]; then output=crop_ABA_$suffix
elif [ $2 == "stats" ]; then output=crop_stats_thr_$suffix 
else output=crop_$2_$suffix #ochann or ochann_rb*
fi

#3D crop cluster 
if [ ! -f $output_path/$output.nii.gz ]; then
  echo " " ; echo "  Making $output_path/crop_"$image"" ; echo Start: $(date) ; echo " " 
  xmin=$(cat $1 | awk '{print $1;}') #echo bounding box text (<xmin>#<xsize>#<ymin>#<ysize>#<zmin>#<zsize>) | first word
  xsize=$(cat $1 | awk '{print $2;}')
  ymin=$(cat $1 | awk '{print $3;}')
  ysize=$(cat $1 | awk '{print $4;}')
  zmin=$(cat $1 | awk '{print $5;}')
  zsize=$(cat $1 | awk '{print $6;}')
  zmin_plus_1=$((zmin+1))
  zmax=$((zmin+zsize))

if [ ${3: -7} == ".nii.gz" ]; then
  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro crop_cluster $3#$xmin#$xsize#$ymin#$ysize#$zmin_plus_1#$zmax
  mv $image_path/crop_$image.nii $output_path/$output.nii 
  gzip -f -9 $output_path/$output.nii #nii to nii.gz
elif [ ${3: -4} == ".tif" ]; then
  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro crop_cluster_image_sequence $3#$xmin#$xsize#$ymin#$ysize#$zmin_plus_1#$zmax#$output_path
  mv $output_path/crop_$2.nii $output_path/$output.nii 
  gzip -f -9 $output_path/$output.nii 
fi
  echo " " ; echo "  Made $output_path/$output.nii.gz" ; echo End: $(date) ; echo " " 
else
  echo " " ; echo "  $output_path/$output.nii.gz exists, skipping" ; echo " " 
fi 

#Get cluster volume 
if [ $2 == "clusters" ]; then 
  if [ ! -f ${bounding_boxes_path%/*}/cluster_volumes/crop_"$suffix"_volume.csv ]; then
    echo " " ; echo "  Making crop_"$suffix"_volume.csv" ; echo Start: $(date) ; echo " " 
    fslstats $output_path/$output.nii.gz -V > ${bounding_boxes_path%/*}/cluster_volumes/crop_"$suffix"_volume.csv
    echo " " ; echo "  Made crop_"$suffix"_volume.csv" ; echo End: $(date) ; echo " " 
  else
    echo " " ; echo "  crop_"$suffix"_volume.csv exists, skipping" ; echo " " 
  fi 
fi 


#Daniel Ryskamp Rijsketic 05/05/2022 & 05/13/2022 & 05/17/22 & 07/29/22 (Heifets lab)
