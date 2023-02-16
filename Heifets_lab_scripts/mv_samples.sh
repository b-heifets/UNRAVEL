#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo "
From experiment summary folder run:
mv_samples.sh <destination path> <Enter space separated list of experiment folder paths (to process all samples) OR sample folder paths (to process specific samples)>

Move samples and auto update sample_overview.csv and parameters.csv files accordingly 
"
  exit 1
fi

echo " " ; echo "Running mv_samples.sh $@ from $PWD" ; echo " " 

exp_summary=$PWD

###### Input(s) for which experiment folders or samples to process: ####### 
destination=$(echo $1 | sed "s/['\"]//g")
source_path_array=($(echo "${@:2}" | sed "s/['\"]//g")) 

#Check if first path in path_array is for an experiment folder or a sample folder
path1_basename=$(basename ${source_path_array[0]}) 
if [ "${path1_basename::-2}" == "sample" ]; then 
  samples=${source_path_array[@]%/} #path/sample?? array
else 
  #make array with all paths/samples from exp_dir array
  samples=($(for d in ${source_path_array[@]%/}; do cd $d ; for s in $(ls -d sample??); do cd $s ; echo $PWD ; cd .. ; done ; done))
fi

for s in ${samples[@]}; do

  new_location=$(echo ${1%/} | sed "s/['\"]//g")

  #move sample?? from to 
  mv $s $new_location/ 

  #update and move row in parameters.csv
  cd ${s%/*} #path/exp_dir
  #https://stackoverflow.com/questions/45444988/sed-editing-specific-column-and-row-in-a-csv-file
  #https://stackoverflow.com/questions/12061410/how-to-replace-a-path-with-another-path-in-sed
  sed -i "/^${s: -2},/s#[^,]*#$new_location#10" parameters.csv #if sample digits in 1st column, replace 10th cell in that row with $new_location
  row=$(grep ${s: -2} parameters.csv) 
  sed -i "s/^${s: -2}.*$//" parameters.csv #delete row 
  empty_var_if_empty_csv=$(grep . parameters.csv)
  if [ -z "$empty_var_if_empty_csv" ]; then rm -f parameters.csv ; fi #delete csv if empty
  cd $new_location 
  echo $row >> parameters.csv
  sort -k1 -t, parameters.csv > tmp ; mv tmp parameters.csv #sort by 1st column

  #update row in sample_overview.csv
  cd $exp_summary
  sed -i "/^${s: -2},/s#[^,]*#$new_location#10" sample_overview.csv
done


#Daniel Ryskamp Rijsketic 07/22/2022-07/26/2022 (Heifets lab)
