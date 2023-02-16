#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets @ Stanford University, 2022-2023

if [ "$1" == "help" ]; then
  echo "
From cluster_validation_summary/unique_folder/ run: 
ABAcluster_volumes.sh

Output : CSV with intensity histogram that can be used to caldulate regional volumes from voxels counts for each cluster -> ./cluster_outputs/cluster_#_ABA_histogram.csv

First run ABAcluster.sh and crop_cluster.sh
Requires sample_overview.csv in experiment_summary_folder (exp_folder/cluster_summary_folder/unqiue_folder). Generate w/ overview.sh
"
  exit 1
fi

echo " " ; echo "Running ABAcluster_volumes.sh from $PWD " ; echo " " 

orig_dir=$PWD
mkdir -p cluster_outputs
exp_summary=$(cd ../.. ; echo $PWD)
output_folder=$(basename $orig_dir)

####### Get sample IDs from sample_overview.csv or by manual input #######
sample_nums=($(tail -n+2 $exp_summary/sample_overview.csv | cut -d',' -f1))
sample_array=("${sample_nums[@]/#/sample}") #concats "sample" with "01" and so on

####### Generate histogram CSVs #######
cd ABAcluster_cropped
for i in *gz ; do if [ ! -f ${i::-7}_histo.csv ] || [ ! -s ${i::-7}_histo.csv ] ; then fslstats $i -H 21142 0 21142 > ${i::-7}_histo.csv ; fi ; done

####### Join histogram CSVs into one CSV per cluster #######
cluster_array=($(for i in *gz; do echo "${i}" | cut -d'_' -f6 | cut -d'.' -f1 ; done | sort -u))
echo ${sample_array[@]} | tr ' ' , > header
for c in ${cluster_array[@]}; do 
  for s in ${sample_array[@]}; do if [ ! -f crop_ABA_"$s"_native_cluster_"$c"_histo.csv ]; then touch crop_ABA_"$s"_native_cluster_"$c"_histo.csv ; fi ; done #tmp blank file if missing input for empty column in final output
  cat header > crop_ABA_native_cluster_"$c"_histo.csv 
  paste -d, $(for s in ${sample_array[@]}; do echo crop_ABA_"$s"_native_cluster_"$c"_histo.csv ; done) >> crop_ABA_native_cluster_"$c"_histo.csv 
  cp crop_ABA_native_cluster_"$c"_histo.csv $orig_dir/cluster_outputs/
  for s in ${sample_array[@]}; do if [ ! -s crop_ABA_"$s"_native_cluster_"$c"_histo.csv ]; then rm crop_ABA_"$s"_native_cluster_"$c"_histo.csv ; fi ; done #blank file deleted
done
rm header
cd ..

#Austen Casey 07/13/22, 8/8/2022 & Daniel Ryskamp Rijsketic 10/19-21/22 (Heifets lab)
