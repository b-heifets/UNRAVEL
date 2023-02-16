#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ $1 == "help" ]; then
  echo "
Run this from sample folder:
cp_prior_clusters.sh <prefix_for_matching_clusters_folders> <cluster_index_path>
" 
  exit 1
fi

echo " " ; echo "Running cp_prior_clusters.sh from $PWD for $1" ; echo " " 

Dir=$PWD

### If reanalyzing data with new MinCluster criteria, prior cluster data (matching stat map and statThr) will be copied to new MinCluster folder, and prior clusters smaller than MinCluster criteria will be deleted ###

#With cluster order reversed (reverse_cluster_order.sh):
cd clusters

#Copy data that was previously made to this from the folder with the most clusters already processed
for i in $1*; do cd $i ; for j in $(ls -d $PWD/*) ; do rsync -au $j $Dir/clusters/${2##*/} ; done ; cd .. ; done

#Make array of folders to search for prior data
matching_cluster_folders=($(ls -d $1*))

#The rest of the script defines a range of clusters not meeting the new ClusterMin criteria and deletes data for clusters in this range
 
#find smallest cluster to remove for current ClusterMin (assuming extra cluster data was copied)
rm -f tmp
for i in $1*; do find $PWD/$i -name sample*_native_cluster_*.nii.gz | sed 's/.......$//' | rev | cut -d"_" -f1 | rev >> tmp ; done # | sed replaces last 7 characters with nothing | reverse string | cut first word separated by _ | rev >> save list of cluster numbers to tmp  
smallest_cluster_to_rm=$(cat tmp | sort -rn | head -1)

if [ -s tmp ]; then #if tmp is not empty, then 
  
  cd $2
  num_of_clusters_with_current_ClusterMin=$(cat *info.txt | awk '{print $1}' | sort -rn | head -1)
  num_of_clusters_with_current_ClusterMin_plus_one=$(($num_of_clusters_with_current_ClusterMin + 1)) #largest cluster to rm for new ClusterMin

  if (( $smallest_cluster_to_rm > $num_of_clusters_with_current_ClusterMin )); then 

    #range of clusters to remove if needed
    rm_clusters_smaller_than_current_ClusterMin="{$num_of_clusters_with_current_ClusterMin_plus_one..$smallest_cluster_to_rm}"

    #delete extra clusters that don't meet new criteria for MinCluster
    cd $Dir/clusters/${2##*/}
    shopt -s globstar ; for i in $(eval echo $rm_clusters_smaller_than_current_ClusterMin); do for j in **/*_cluster_$i*; do rm -rf $j ; done ; done 
  fi 
fi

cd $Dir/clusters
rm -f tmp

cd $Dir

#Daniel Ryskamp Rijsketic 05/16/2022-06/21/2022 & 08/05/22 (Heifets lab)
