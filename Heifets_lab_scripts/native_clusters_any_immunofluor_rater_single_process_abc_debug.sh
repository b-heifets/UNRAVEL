#!/bin/bash

if [ $# == 0 ] || [ $1 == "help" ]; then
  echo '
Run this from sample folder:
native_clusters.sh <./clusters_folder/native_cluster_index/native_rev_cluster_index.nii.gz> <xy_voxel_size_in_um> <z_voxel_size_in_um> <'\''list clusters to process seperated by spaces'\''> <immunofluor label> <crop segmentation for "consensus" or a specific rater # (e.g., "1") 

List range of clusters like: "$(eval echo {1..10})"

Hard coded: /usr/local/miracl/miracl/seg/fslhd_XML_header.txt

Outputs: 
bounding_boxes/outer_bounds.txt
bounding_boxes/bounding_box_cluster_*.txt
clusters_cropped/crop_sample??_native_cluster_*.nii.gz
'
  exit 1
fi

echo " " ; echo "Running native_clusters_any_immunofluor_rater_abc.sh $@ from $PWD at $(date)" ; echo " " 

orig_dir=$PWD
sample=${PWD##*/}
path_native_index=$(echo $1 | sed "s/['\"]//g")
output_folder=${path_native_index%/*/*}

# Determine xyz voxel size in microns
if [ "$2" == "m" ]; then 
  metadata.sh
  xy_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f1)
  z_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f3)
else
  xy_res=$2
  z_res=$3
fi 

############ ABC added to accomodate consensus or rater specific
if [ $6 != "consensus" ] ; then
  ###seg_nifti=$orig_dir/"$3"_seg_ilastik_$i/"$sample"_"$5"_seg_ilastik_$6.nii.gz
  ###seg_type="$5"_seg_ilastik_$6
  seg_nifti=$orig_dir/"$5"_seg_ilastik_$6/"$sample"_"$5"_seg_ilastik_$6.nii.gz 
  seg_type="$5"_seg_ilastik_$6
else
  seg_nifti=$orig_dir/consensus/"$sample"_consensus.nii.gz
  seg_type=consensus
fi
############

cd $output_folder
mkdir -p bounding_boxes clusters_cropped cluster_volumes "$seg_type"_cropped

#Convert to 8-bit if possible
if [ "$(fslinfo $path_native_index | cut -f2 | head -1)" != "UINT8" ]; then
  float=$(fslstats $path_native_index -R | cut -d' ' -f2)
  int=${float%.*}
  if (( "$int" < "255" )); then 
    fslmaths $path_native_index $path_native_index -odt char #-odt char converts to 8-bit
  fi
fi

python3 /usr/local/miracl/miracl/seg/native_clusters_any_immunofluor_rater_single_process_abc_debug.py $1 $xy_res $z_res $output_folder $sample $seg_nifti $4 ########## edited pos arg to accomodate consensus or rater specific segmentations

#edit headers of output .nii.gz files
xy_res=$(echo "scale=5; ($2)/1000" | bc | sed 's/^\./0./') #covert microns to mm
z_res=$(echo "scale=5; ($3)/1000" | bc | sed 's/^\./0./')

fslhd=/usr/local/miracl/miracl/seg/fslhd_XML_header.txt
fslhd_cluster=$output_folder/clusters_cropped/fslhd_XML_header.txt
for i in $4; do  
  cluster_cropped_output="$output_folder/clusters_cropped/crop_"$sample"_native_cluster_"$i".nii.gz"
  hdr=$output_folder/clusters_cropped/XML_header.txt
  fslhd -x $cluster_cropped_output > $hdr
  sed -i "s/ndim = '3'/ndim = '4'/g" $hdr
  sed -i "s/dx = '1'/dx = '$xy_res'/g" $hdr
  sed -i "s/dy = '1'/dy = '$xy_res'/g" $hdr
  sed -i "s/dz = '1'/dz = '$z_res'/g" $hdr
  sed -i "s/xyz_units = '0'/xyz_units = '2'/g" $hdr
  sed -i "s/sform_code = '2'/sform_code = '0'/g" $hdr
  dim3=$(fslinfo $cluster_cropped_output | head -4 | tail -1 | rev | cut -f1 | rev)
  scl_end=$(expr $dim3 - 1)
  sed -i "s/scl_end = '0'/scl_end = '$scl_end'/g" $hdr
  fslcreatehd $hdr $cluster_cropped_output
  rm $hdr
    
  seg_in_cluster_cropped_output="$output_folder/"$seg_type"_cropped/3D_counts/crop_"$seg_type"_"$sample"_native_cluster_"$i"_3dc/crop_"$seg_type"_"$sample"_native_cluster_"$i".nii.gz" #ABC edited to accomodate consensus or rater specific segmentations
  hdr=$output_folder/"$seg_type"_cropped/3D_counts/crop_"$seg_type"_"$sample"_native_cluster_"$i"_3dc/XML_header.txt #ABC edited to accomodate consensus or rater specific segmentations
  fslhd -x $seg_in_cluster_cropped_output > $hdr
  sed -i "s/ndim = '3'/ndim = '4'/g" $hdr
  sed -i "s/dx = '1'/dx = '$xy_res'/g" $hdr
  sed -i "s/dy = '1'/dy = '$xy_res'/g" $hdr
  sed -i "s/dz = '1'/dz = '$z_res'/g" $hdr
  sed -i "s/xyz_units = '0'/xyz_units = '2'/g" $hdr
  sed -i "s/sform_code = '2'/sform_code = '0'/g" $hdr
  sed -i "s/scl_end = '0'/scl_end = '$scl_end'/g" $hdr
  fslcreatehd $hdr $seg_in_cluster_cropped_output
  rm $hdr

done

cd $orig_dir
     
#Daniel Ryskamp Rijsketic 11/11/22 11/22-23/22 12/9-14/22 (Heifets lab)
