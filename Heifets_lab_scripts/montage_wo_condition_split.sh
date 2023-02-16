#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets @ Stanford University, 2022-2023

#https://legacy.imagemagick.org/Usage/montage/ 

if [ $# == 0 ] || [ $1 == help ]; then
  echo '
Run montage.sh [all or list sample numbers] [cluster to process] [a to auto flip tiles, list sample numbers for flipping, or leave blank] from cluster_validation_summary/output_folder

Automatic flipping of montage tiles (so that clusters have uniform orientation) requires experiment_summary/sample_overview.sh and running montage.sh for all samples. 
'
fi

echo " " ; echo "Running montage.sh from $PWD " ; echo " " 

orig_dir=$PWD
mkdir -p montages
cd ../..
exp_summary_dir=$PWD

border_size=+2+2
prefix=most_sig_slice_crop
suffix=native_cluster
radius=$(cd $exp_summary_dir/ ; cat rolling_ball_radius.txt)

####### Get sample IDs from sample_overview.csv or by manual input #######
if [ $# -ne 0 ]; then 
  samples_to_process=$1
else 
  read -p "Which samples to process? all or list sample numbers: " samples_to_process ; echo " "
fi 
if [ "$samples_to_process" != "all" ]; then 
  sample_nums=($(echo $samples_to_process)) 
else 
  sample_nums=($(tail -n+2 sample_overview.csv | cut -d',' -f1))
fi
sample_array=("${sample_nums[@]/#/sample}")

####### Determine what clusters to process #######
if [ $# -ne 0 ]; then 
  clusters_to_process=$2
else 
  read -p "Which clusters to process? all, {1..4} (range), or 1 2 4: (just process one cluster at a time for now) " clusters_to_process ; echo " "
fi 
if [ "$clusters_to_process" == "all" ] && [ -f all_clusters ]; then 
  clusters_to_process=$(cat all_clusters)
elif [ "$clusters_to_process" == "all" ] && [ ! -f all_clusters ]; then 
  float=$(fslstats cluster_index/${orig_dir##*/}_rev_cluster_index.nii.gz -R | awk '{print $2;}')
  num_of_clusters=${float%.*} # convert to integer
  clusters_to_process="{1..$num_of_clusters}"
  echo $clusters_to_process > $orig_dir/all_clusters
fi

####### Determine whether to use ABAconsensus_cropped or consensus_cropped #######
num_of_files_in_consensus=$(cd $orig_dir/consensus_cropped/3D_counts 2>/dev/null ; ls -d crop* 2>/dev/null | wc -l)
num_of_files_in_ABAconsensus=$(cd $orig_dir/ABAconsensus_cropped/3D_counts 2>/dev/null ; ls -d crop* 2>/dev/null | wc -l)
if [ "$num_of_files_in_consensus" -gt "$num_of_files_in_ABAconsensus" ] ; then 
  consensusDir=$orig_dir/consensus_cropped
else 
  consensusDir=$orig_dir/ABAconsensus_cropped
fi
consensus=$(basename $consensusDir | awk -F "_" '{print $1}')

####### Determine average aspect ratio for resizing tiles (to make dims uniform for all tiles) #######
cd $orig_dir/ochann_cropped 
ochann_array=($(for s in ${sample_array[@]}; do for c in $(eval echo "$clusters_to_process"); do echo "$prefix"_ochann_"$s"_"$suffix"_"$c".tif ; done ; done))
rm -f x_dim y_dim
for tif in ${ochann_array[@]}; do 
  x_dim=$(identify -quiet $tif | cut -f 3 -d " " | cut -dx -f1) ; echo $x_dim >> x_dim
  y_dim=$(identify -quiet $tif | cut -f 3 -d " " | cut -dx -f2) ; echo $y_dim >> y_dim 
done 
y_max=$(echo $(awk '{s+=$1} END {print s}' y_dim))
x_dim_ave=$(echo $(awk '{ total += $1; count++ } END { print total/count }' x_dim))
y_dim_ave=$(echo $(awk '{ total += $1; count++ } END { print total/count }' y_dim))
ave_dim_txt=average_dim_cluster_$(date "+%F-%T")
echo x_dim_ave: $x_dim_ave > $orig_dir/montages/$ave_dim_txt
echo y_dim_ave: $y_dim_ave >> $orig_dir/montages/$ave_dim_txt
rm -f x_dim y_dim
ave_aspect_ratio=$(echo "scale=5 ; $x_dim_ave/$y_dim_ave" | bc | sed 's/^\./0./') #sed adds a 0 before the . if the result<1
if (( $y_max > 12000 )); then #This will scale down large image tiles if needed so that montages can still be made
  declare new_y_dim=$((12000/${#ochann_array[@]}))
else
  declare new_y_dim=$y_dim_ave
fi
declare new_x_dim_float=$(echo "scale=5 ; $ave_aspect_ratio*$new_y_dim" | bc)
declare new_x_dim=$(echo "($new_x_dim_float+0.5)/1" | bc) #rounds


############################################
####### Flip divergent montage tiles #######
############################################
if [ $# -ne 0 ]; then 
  auto_or_manual_flip=$3
else 
  read -p "When processing all samples, enter a to automatically flip montage tiles (for samples w/ diff ort/hemi), list sample numbers for flipping, or leave blank (no flipping): " auto_or_manual_flip ; echo " " 
fi
if [ "$auto_or_manual_flip" == "a" ]; then
  common_ort=$(cd $exp_summary_dir ; awk -F, '{print $5}' sample_overview.csv | sort -n | uniq -c | sort -r  | awk 'NR==1{print $2}')
  common_hemi=$(cd $exp_summary_dir ; awk -F, '{print $2}' sample_overview.csv | sort -n | uniq -c | sort -r | awk 'NR==1{print $2}')
  samples_with_uncommon_ort=$(cd $exp_summary_dir ; grep -v ,"$common_ort", sample_overview.csv | awk -F, '{if (NR!=1) {print $1}}')
  samples_with_uncommon_hemi=$(cd $exp_summary_dir ; grep -v ,"$common_hemi", sample_overview.csv | awk -F, '{if (NR!=1) {print $1}}')
  samples_to_flip=($(echo $samples_with_uncommon_ort $samples_with_uncommon_hemi))
  echo samples_with_uncommon_ort: $samples_with_uncommon_ort ; echo " " ; echo samples_with_uncommon_hemi: $samples_with_uncommon_hemi ; echo " "
  echo 'If a sample has both an uncommon orientation and hemi, it will flipped, so pay attention to this and use manual flipping if needed' ; echo " " 
else 
  samples_to_flip=($(echo $auto_or_manual_flip))
fi
flip_array=("${samples_to_flip[@]/#/sample}")
if [ "${flip_array[0]}" == "sample" ]; then flip_array="" ; fi

flip_slices () {
for i in ${flip_array[@]}; do 
  if [ ! -f $1/$2_flipped.txt ]; then
    cp $1/$2.tif $1/$2_orig.tif
    convert -flop $1/$2.tif $1/$2.tif
    touch $1/$2_flipped.txt
  fi
done
}

for s in ${flip_array[@]}; do for c in $(eval echo "$clusters_to_process"); do
  flip_slices $orig_dir/ochann_cropped "$prefix"_ochann_"$s"_"$suffix"_"$c"
  flip_slices $orig_dir/ochann_rb"$radius"_cropped "$prefix"_ochann_rb"$radius"_"$s"_"$suffix"_"$c"
  flip_slices $consensusDir "$prefix"_"$consensus"_"$s"_"$suffix"_"$c"
  flip_slices $orig_dir/stats_cropped "$prefix"_stats_thr_"$s"_"$suffix"_"$c"
done ; done


##################################################################
####### Make montage(s) for requested samples and clusters #######
##################################################################
columnar_montage () {
image_array=($(for s in ${sample_array[@]}; do for c in $(eval echo "$clusters_to_process"); do echo "$prefix"_$1_"$s"_"$suffix"_"$c".tif ; done ; done))
for c in $(eval echo "$clusters_to_process"); do
  montage ${image_array[@]} -resize "$new_x_dim"x"$new_y_dim"\! -geometry $border_size -tile 1x${#image_array[@]} -background white $1_montage_cluster_"$c".tif  
done
}

cd $orig_dir
if [ "$samples_to_process" != "all" ]; then 
  ####### Make montage for each sample/cluster #######
  for s in ${sample_array[@]}; do for c in $(eval echo "$clusters_to_process"); do
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro draw_cluster_outline $orig_dir/stats_cropped/"$prefix"_stats_thr_"$s"_"$suffix"_"$c".tif#$consensusDir/"$prefix"_"$consensus"_"$s"_"$suffix"_"$c".tif#$consensusDir/"$prefix"_"$consensus"_"$s"_"$suffix"_"$c".tif#$consensusDir/"$prefix"_"$consensus"_"$s"_"$suffix"_"$c".tif

    montage $orig_dir/ochann_cropped/"$prefix"_ochann_"$s"_"$suffix"_"$c".tif $orig_dir/ochann_rb"$radius"_cropped/"$prefix"_ochann_rb"$radius"_"$s"_"$suffix"_"$c".tif $consensusDir/outline_"$prefix"_"$consensus"_"$s"_"$suffix"_"$c".tif -geometry $border_size -tile 3x1 -background white $orig_dir/montages/montage_"$s"_cluster_"$c".tif
  done ; done 
else
  ####### Make columnar montages #######
  cd $orig_dir/ochann_cropped ; columnar_montage ochann
  cd $orig_dir/ochann_rb"$radius"_cropped ; columnar_montage ochann_rb"$radius"
  cd $consensusDir ; columnar_montage "$consensus"
  cd $orig_dir/stats_cropped ; columnar_montage stats_thr

  ####### Make full montage from columnar montages #######
  cd $orig_dir
  for c in $(eval echo "$clusters_to_process"); do
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro draw_cluster_outline $orig_dir/stats_cropped/stats_thr_montage_cluster_"$c".tif#$orig_dir/ochann_cropped/ochann_montage_cluster_"$c".tif#$orig_dir/ochann_rb"$radius"_cropped/ochann_rb"$radius"_montage_cluster_"$c".tif#$consensusDir/"$consensus"_montage_cluster_"$c".tif

    montage $orig_dir/ochann_cropped/outline_ochann_montage_cluster_"$c".tif $orig_dir/ochann_rb"$radius"_cropped/outline_ochann_rb"$radius"_montage_cluster_"$c".tif $consensusDir/outline_"$consensus"_montage_cluster_"$c".tif -geometry $border_size -tile 3x1 -background white $orig_dir/montages/full_montage_w_outlines_cluster_"$c".tif 
  done 
fi 

#Daniel Ryskamp Rijsketic ~6/22, 7/12/22, 9/1-7/22  & Austen Casey 7/18/22 8/4/22 (Heifets Lab)
