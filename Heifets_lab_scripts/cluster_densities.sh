#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo "
From cluster_validation_summary/unique_folder/ run: 
cluster_densities.sh <all or 'list sample numbers'> <cluster(s) to process (all, '{1..4}', or '1 2 4')>

Requires sample_overview.csv in experiment_summary_folder (exp_folder/cluster_summary_folder/unqiue_folder). Generate w/ overview.sh

If you copy/paste from terminal into excel, use =TEXTSPLIT(A1,\",\")
"
  exit 1
fi

orig_dir=$PWD
mkdir -p cluster_outputs
exp_summary=$(cd ../.. ; echo $PWD)
output_folder=$(basename $orig_dir)

####### Get sample IDs from sample_overview.csv or by manual input #######
if [ "$1" == "all" ]; then sample_nums=($(tail -n+2 $exp_summary/sample_overview.csv | cut -d',' -f1)) ; else sample_nums=($(echo $1)) ; fi
sample_array=("${sample_nums[@]/#/sample}") #concats "sample" with "01" and so on

####### Determine what clusters to process #######
if [ "$2" == "all" ] && [ -f all_clusters ]; then 
  clusters_to_process=$(cat all_clusters)
elif [ "$2" == "all" ] && [ ! -f all_clusters ]; then 
  float=$(fslstats cluster_index/"$output_folder"_rev_cluster_index.nii.gz -R | awk '{print $2;}') # get 2nd word of output (max value in volume)
  num_of_clusters=${float%.*} # convert to integer
  clusters_to_process="{1..$num_of_clusters}"
  echo $clusters_to_process > all_clusters
else 
  clusters_to_process=$2
fi

###########################################################################
####### Generate table with cell counts for each cluster and sample #######
###########################################################################

####### Determine whether to use ABAconsensus_cropped or consensus_cropped #######
num_of_files_in_consensus=$(cd consensus_cropped/3D_counts 2>/dev/null ; ls -d crop* 2>/dev/null | wc -l)
num_of_files_in_ABAconsensus=$(cd ABAconsensus_cropped/3D_counts 2>/dev/null ; ls -d crop* 2>/dev/null | wc -l)
if [ "$num_of_files_in_consensus" -gt "$num_of_files_in_ABAconsensus" ] ; then 
  consensusDir=$orig_dir/consensus_cropped
else 
  consensusDir=$orig_dir/ABAconsensus_cropped
fi
consensus=$(basename $consensusDir | awk -F "_" '{print $1}')

setup_table () {
####### Make column with sample numbers and column with conditions #######
echo Samples > samples
echo Conditions > conditions
for s in ${sample_array[@]}; do
  echo $s >> samples
  grep ${s: -2} $exp_summary/sample_overview.csv | cut -d',' -f4 >> conditions
done

####### Make cluster number header for data columns #######
for c in $(eval echo "$clusters_to_process"); do
  echo Cluster_$c >> tmp_$c
done
}

setup_table

####### Make table w/ cluster counts for each sample and cluster #######
for s in ${sample_array[@]}; do
  for c in $(eval echo "$clusters_to_process"); do
    file_w_count=$consensusDir/3D_counts/crop_"$consensus"_"$s"_native_cluster_"$c"_3dc/crop_"$consensus"_"$s"_native_cluster_"$c"_3D_cell_count.txt
    if [ ! -f $file_w_count ] || [ ! -s $file_w_count ] ; then 
      x="NA"
    else 
      x=$(cat $file_w_count)
    fi 
    echo $x >> tmp_$c
  done
done 
order=($(ls -v1 tmp_*)) #numerical sorting (rather than 1 10 11 ... 19 2 20 21) 
paste -d, ${order[@]} > all_counts
rm -f tmp_*
paste -d, samples conditions all_counts > counts
cat counts | head -n 1 > cluster_counts.csv ; cat counts | tail -n +2 | sort -t"," -k2,2 -s >> cluster_counts.csv  #header > newfile, rest sort by column 2 (-k2,2), preserving sample order with duplicate conditions (-s) 
rm -f samples conditions all_counts #counts

echo " " ; echo  "Cell counts in clusters: " ; cat cluster_counts.csv ; echo " "


###################################################
####### Generate table with cluster volumes #######
###################################################

setup_table

####### Make table w/ cluster volumes for each sample and cluster #######
for s in ${sample_array[@]}; do
  for c in $(eval echo "$clusters_to_process"); do
    file_w_volume=cluster_volumes/crop_"$s"_native_cluster_"$c"_volume.csv
    if [ ! -f $file_w_volume ] || [ ! -s $file_w_volume ] ; then 
      x="NA"
    else 
      x=$(cat $file_w_volume | cut -d' ' -f2) #get volumes in mm^3 (from fslstats <input.nii.gz> -V)
    fi 
    echo $x >> tmp_$c
  done
done 
order=($(ls -v1 tmp_*)) #numerical sorting (rather than 1 10 11 ... 19 2 20 21) 
paste -d, ${order[@]} > all_volumes
rm -f tmp_*
paste -d, samples conditions all_volumes > volumes
cat volumes | head -n 1 > cluster_volumes.csv ; cat volumes | tail -n +2 | sort -t"," -k2,2 -s >> cluster_volumes.csv
rm -f samples conditions all_volumes #volumes

echo  "Cluster volumes: " ; cat cluster_volumes.csv ; echo " "


##################################################################
####### Generate table with cluster densities (cells/mm^3) #######
##################################################################

cat counts | head -n 1 > cluster_densities.csv

tail -n+2 cluster_counts.csv > cluster_counts_wo_header.csv
tail -n+2 cluster_volumes.csv > cluster_volumes_wo_header.csv

mapfile -t counts_array < cluster_counts_wo_header.csv
mapfile -t volumes_array < cluster_volumes_wo_header.csv

for line in "${!counts_array[@]}" ; do 
  IFS=',' read -ra counts_line_array <<< "${counts_array[$line]}" 
  IFS=',' read -ra volumes_line_array <<< "${volumes_array[$line]}" 
  allinput= #https://stackoverflow.com/questions/69806126/how-to-combine-for-loop-values-in-one-variable-separated-by-comma-unix-scriptin
  for i in "${!counts_line_array[@]}"; do
    #https://stackoverflow.com/questions/29851918/bash-if-variable-is-an-integer
    input=$([[ ${counts_line_array[i]} =~ ^[0-9]+$ ]] && echo $(echo "scale=2 ; ${counts_line_array[i]}/${volumes_line_array[i]}" | bc -l) || echo ${counts_line_array[i]})
    allinput+="${input},"
  done
  allinput=${allinput%,}
  echo $allinput >> cluster_densities.csv
done

echo  "Cluster densities: " ; cat cluster_densities.csv ; echo " "

mv cluster_counts.csv cluster_outputs/counts_$output_folder.csv
mv cluster_volumes.csv cluster_outputs/volumes_$output_folder.csv
mv cluster_densities.csv cluster_outputs/densities_$output_folder.csv
rm -f cluster_counts_wo_header.csv counts cluster_volumes_wo_header.csv volumes 

#Daniel Ryskamp Rijsketic 05/05/2022, 05/13/2022, 05/17/22, 06/21/22, 10/19-21/22 and Austen Casey 06/21/22, 07/26/22 (Heifets lab)
