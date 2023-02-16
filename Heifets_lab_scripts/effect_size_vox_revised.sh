#!/bin/bash
# (c) Austen Brooks Casey, Boris Heifets @ Stanford University, 2022-2023

#This script computes the effect size for the average of each cluster in an index
#This script is set up to run inside of validate_clusters.sh
#mv $indexDir/*_rev_cluster_index.nii.gz $3/effect_sizes
#mv $GLMfolder/stats/*_revID_*.nii.gz $3/effect_sizes

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
From cluster_validation_summary/<GLM_foldername> folder run:

effect_size_vox.sh <path to GLM folder containing reverse warp images in atlas space> 

Run after glm_*_rev_cluster_index.nii.gz has been generated in the stats folder

This script computes average intensity within each cluster for each sample
Subtracts the mean intensity in Group 1 from mean intensity of Group2, then divides the difference by the pooled standard deviation
Outputs a csv file in ./cluster_outputs reporting the effect sizes

'
  exit 1
fi


orig_dir=$PWD
GLMfolder=$1
indexpath=$1/stats/$(basename $orig_dir)/glm*_rev_cluster_index.nii.gz
index=$(basename $indexpath)
float=$(fslstats $indexpath -R | awk '{print $2;}') # get 2nd word of output (max value in volume)
num_of_clusters=${float%.*} # convert to integer
clusters_to_process="{1.."$num_of_clusters"}"
cluster_nums=($(for i in $clusters_to_process ; do echo $i ; done))
rev_warps_array=($(for i in $GLMfolder/*.nii.gz ; do echo $i ; done))
group1=$(cd $GLMfolder ; find *.nii.gz -maxdepth 0 -type f | head -n 1 | cut -d _ -f 1) #get prefix for group1
group2=$(cd $GLMfolder ; find *.nii.gz -maxdepth 0 -type f | tail -n 1 | cut -d _ -f 1) #get prefix for group2

mkdir -p $orig_dir/effect_sizes

cp $indexpath $orig_dir/effect_sizes
cp $GLMfolder/stats/$(basename $orig_dir)/*_revID_*.nii.gz $orig_dir/effect_sizes

cd $orig_dir/effect_sizes

if [ $(ls *_revID_*.nii.gz | wc -l) != $num_of_clusters ] ; then
 rm -f *_revID_*.nii.gz ; fi

for i in $(eval echo $clusters_to_process); do
    fslmaths $index -thr $i -uthr $i -bin ${index::-7}_revID_"$i".nii.gz
done

for i in ${rev_warps_array[@]} ;
 do cp $i $orig_dir/effect_sizes
done


#make 4D volumes for each condition and all
if [ ! -f full_"$group1"_4D.nii.gz ] && [ ! -f full_"$group2"_4D.nii.gz ] && [ ! -f all_4D.nii.gz ]; then 
fslmerge -t full_"$group1"_4D.nii.gz "$group1"_*.nii.gz
fslmaths full_"$group1"_4D.nii.gz -s 0.05 full_"$group1"_4D.nii.gz
fslmerge -t full_"$group2"_4D.nii.gz "$group2"_*.nii.gz
fslmaths full_"$group2"_4D.nii.gz -s 0.05 full_"$group2"_4D.nii.gz
fslmerge -t all_4D.nii.gz full_"$group1"_4D.nii.gz full_"$group2"_4D.nii.gz
fslmaths all_4D.nii.gz -s 0.05 all_4D.nii.gz
fi

#Calculate group means and pooled SDs
for i in $(eval echo $clusters_to_process) ; do
	echo $(fslstats full_"$group1"_4D.nii.gz -k *_revID_"$i".nii.gz -M > cluster_"$i"_"$group1"_mean.csv)
	echo $(fslstats full_"$group2"_4D.nii.gz -k *_revID_"$i".nii.gz -M > cluster_"$i"_"$group2"_mean.csv)
	echo $(fslstats all_4D.nii.gz -k *_revID_"$i".nii.gz -S > cluster_"$i"_pooled_SD.csv)
	numerator=$(echo "scale=5;"$(cat cluster_"$i"_"$group1"_mean.csv)" - "$(cat cluster_"$i"_"$group2"_mean.csv)"" | bc)
	demonimator=$(echo $(cat cluster_"$i"_pooled_SD.csv))
	echo $((echo "scale=5;$numerator/$demonimator" | bc) > cluster_"$i"_effect_size.csv)
done

#mv cluster_*_effect_size.csv $3/cluster_outputs

#rm *4D.nii.gz "$group1"*nii.gz "$group2"*nii.gz *_revID_*.nii.gz

cluster_array=("${cluster_nums[@]/#/cluster_}")

if [ -f clusters.csv ] ; then rm clusters.csv ; fi >2 dev/null
for i in ${cluster_array[@]}; do echo $i >> clusters.csv ; done

#Generate string with the full range of possible clusters
max_cluster_num=($(ls crop_* | sort -n -t '_' -k6 | awk -F_ '{if ( num<$1 ){num = $1; file = $0}}END{print $6}')) ; for num in $(eval echo "{1..$max_cluster_num}") ; do uniq_cluster_nums[$num]=0 ; done

#Create empty files where cluster has no count data
for i in ${cluster_array[@]}; do
    if [ ! -f cluster_"$i"_effect_size.csv ]; then echo "NO_DATA" > cluster_"$i"_effect_size.csv ; fi 
 done 

#make comma separated string of counts for each sample and cluster
#(SampleX,Count[Cluster1],Count[ClusterN])
#https://dzone.com/articles/shell-create-a-comma-separated-string

if [ -f effects.csv ] ; then rm effects.csv ; fi >2 dev/null
for i in ${cluster_nums[@]}; do
  combined=""
      for csv in cluster_"$i"_effect_size.csv; do 
      token=$(cat $csv)
      combined="${combined}${combined:+,}$token"
    done 
  echo $combined >> effects.csv
done

#Add sample ID to 3D_counts.csv
paste -d, clusters.csv effects.csv > effect_sizes.csv


##########exploratory##################
#orig_dir=$PWD
#glm_name=$(basename $orig_dir)
#ROIs=($(for i in $glm_name_cluster_index_revID_*.nii.gz ; do echo $i ; done)

#for i in *z-scored.nii.gz ; do fslmaths $i -s 50 ${i::-7}_s50.nii.gz ; done

#for i in *_s50.nii.gz ; do 
# for ROI in ${ROIs[@]} ; do
#  fslmaths $i -mul $ROI  ${i::-7}_s50_$ROI.nii.gz ; 
# done
#done

#for i in *_s50_$ROI.nii.gz ; do fslstats $i -M > "${i::-7}"_mean.csv ; done

#cd .. ; rm -d effect_sizes

#use a for statement to grab sample numbers for each group, create an array of them, and use that array to pull density data in groups to get effect size for cell densities

#Austen Brooks Casey 07/26/22 08/2/2022 (Heifets Lab)
