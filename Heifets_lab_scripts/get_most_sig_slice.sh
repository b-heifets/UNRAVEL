#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ $1 == "help" ]; then
  echo " 
Run to find most sig slice in stats image volume:
get_most_sig_slice.sh <./path/crop_stats_thr_sample??_native_cluster_*.nii.gz>
" 
  exit 1
fi

echo " " ; echo "Running get_most_sig_slice.sh for $1 " ; echo " "

image=$(basename $1) 
path=$(dirname $1)

if [ ! -f $1_IntDen-Max_most-sig-slice.csv ]; then 

  echo " " ; echo "  Finding most sig slice and outputing to $1_IntDen-Max_most-sig-slice.csv" ; echo Start: $(date) ; echo " "

  #Measure integrated density of all slices in stack for 
  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro integrated_densities_for_stack $1

  #Get slice # with max integrated density (load csv | sort by 3rd, comma separated column | get top row | 1st word | save) 
  cat $path/"$image"_IntDen.csv | sort -t, -k3,3 -nr | head -1 | cut -d ',' -f1 > $path/"$image"_IntDen-Max_most-sig-slice.csv 

  echo " " ; echo "  Made $1_IntDen-Max_most-sig-slice.csv" ; echo End: $(date) ; echo " "

fi

#Daniel Ryskamp Rijsketic 05/31/22 (Heifets lab)




