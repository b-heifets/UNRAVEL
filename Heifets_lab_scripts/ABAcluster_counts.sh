#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ "$1" == "" ] || [ "$1" == "help" ]; then 
  echo '
Run ABAcluster_counts.sh from ./cluster_validation_summary/<glm_name>
Inputs: ./cluster_validation_summary/<glm_name>/ABAconsensus_cropped/3D_counts/crop_ABAconsensus_sample??/sample_??_cluster_*_ABAconsensus_3Dcounts.csv
Main output: cluster_"$i"_ABA_counts_$glm_name.csv reporting the fractional cell count for each brain region in each cluster
' 
  exit 1
fi


output_dir=$PWD
glm_name=$(basename $output_dir)
cd $output_dir/ABAconsensus_cropped/3D_counts
max_cluster_num=$(ls -d crop_ABAconsensus_sample* | sort -n -t '_' -k6 | awk -F_ '{if ( num<$1 ){num = $1; file = $0}}END{print $6}') ; for num in $(eval echo "{1..$max_cluster_num}") ; do uniq_cluster_nums[$num]=0 ; done
samples=($(ls -d crop_ABAconsensus_sample* | sort -n -t '_' -k3 | awk -F_ '{print $3}' | sort -u))
#sample_nums=($(for i in $(find . -name " crop_ABAconsensus_sample*" | cut -d'_' -f 3); do echo ${i: -2} ; done)) ; for i in ${sample_nums[@]} ; do uniq_sample_nums[$i]=0 ; done 
ABAintensities=($(eval echo "{20001..21142}"))

mkdir -p ABA_counts

find . -name "sample_*_cluster_*_ABAconsensus_3Dcounts.csv" -exec rsync -au {} ./ABA_counts \;

cd $output_dir/ABAconsensus_cropped/3D_counts/ABA_counts

#rename to remove delimiter separate field of "sample" and its number
for i in sample_*_cluster_*_ABAconsensus_3Dcounts.csv ; do mv "$i" "${i/_/}" ; done

#Generate .txt file for the sum total of cells in each region for each sample and cluster
for s in ${samples[@]} ; do
 for i in  ${!uniq_cluster_nums[@]} ; do 
  for intensity in ${ABAintensities[@]} ; do  
    awk -F ',' '$2=='$intensity'{print $3}' "$s"_cluster_"$i"_ABAconsensus_3Dcounts.csv  | paste -sd+ | bc > "$s"_cluster_"$i"_"$intensity"_ID1.csv 2> /dev/null
    awk -F ',' '$4=='$intensity'{print $5}' "$s"_cluster_"$i"_ABAconsensus_3Dcounts.csv  | paste -sd+ | bc > "$s"_cluster_"$i"_"$intensity"_ID2.csv
    awk -F ',' '$6=='$intensity'{print $7}' "$s"_cluster_"$i"_ABAconsensus_3Dcounts.csv  | paste -sd+ | bc > "$s"_cluster_"$i"_"$intensity"_ID3.csv
  done
 done
done

#Fill in files where no cells are present with "0" 
for i in *ID*.csv ; do if [ $(cat $i | wc -w) == 0 ] ; then echo "0" >> $i ; fi ; done #enter 0 for IDs that have no counts

#Sum the fractional cell counts for a given intensity
for s in ${samples[@]} ; do
 for i in  ${!uniq_cluster_nums[@]} ; do 
  for intensity in ${ABAintensities[@]} ; do  
    echo "scale=4;"$(cat "$s"_cluster_"$i"_"$intensity"_ID1.csv)" + "$(cat "$s"_cluster_"$i"_"$intensity"_ID2.csv)" + "$(cat "$s"_cluster_"$i"_"$intensity"_ID3.csv)"" | bc > "$s"_cluster_"$i"_"$intensity"_sum.csv 2> /dev/null
  done
 done
done

#Numerically sort the csv files by intensity for each sample and cluster 
for s in ${samples[@]} ; do 
 for i in ${!uniq_cluster_nums[@]} ; do
  for ID in $(ls "$s"_cluster_"$i"_*_sum.csv | sort -n -t '_' -k4) ; do
   $(cat $ID >> "$s"_cluster_"$i"_summary.csv)
  done
 done
done

#Make csv with ABA intensities
for i in ${ABAintensities[@]} ; do echo "$i", "" > ABAintensities.csv ; done

#Make sample headers
for i in ${!uniq_cluster_nums[@]}; do 
combined=""
for sample in ${samples[@]}; do 
  token=$sample
  combined="${combined}${combined:+,}$token"
done
echo ABA_Intensity,$combined >> cluster_"$i"_ABA_counts_$glm_name.csv
echo $combined >> cluster_"$i"_samples.csv
done

for i in ${!uniq_cluster_nums[@]}; do csv_array=($(find . -name "sample*_cluster_"$i"_summary.csv" -exec echo {} \; | sort -n -t '_' -k1)) ; echo ${csv_array[@]##*/} > cluster_"$i"_ABA_counts.csv ; readarray -t sorted_csv_array < <(for csv in "${csv_array[@]##*/}"; do echo "$csv"; done | sort) ; paste -d, ${sorted_csv_array[@]} > cluster_"$i"_ABA_counts_wo_headers.csv ; done

#Add ABA intensity labels to lefthand column
for i in ${!uniq_cluster_nums[@]}; do paste -d, ABAintensities.csv cluster_"$i"_ABA_counts_wo_headers.csv > cluster_"$i"_ABA_counts.csv

#Add headers
for i in ${!uniq_cluster_nums[@]}; do cat cluster_"$i"_ABA_counts.csv | while read line; do echo $line >> cluster_"$i"_ABA_counts_$glm_name.csv ; done ; done

rm *ID*.csv 
rm *sum.csv 
rm *summary.csv 
rm *counts.csv


 
