#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
From and experiment summary folder run: 
overview.sh <list all path/experiment_folders seperated by spaces>

Outputs: ./exp_dirs/parameters.csv (local info w/ no headers) ./exp_summary/sample_overview.csv (global info w/ headers)

Prompts are conditional in that if all samples in experiment have same antigen, shape, orientation, 488 display range min, and/or xyz voxel size, then these only need to be entered once for the whole experiment. Otherwise, they can be entered either uniformly for samples in each experiment folder or individually. 
'
  exit 1
fi

exp_summary=$PWD

######### Input(s) for which experiment directories to process: ########### 
if [ $# == 0 ] ; then 
  dir_array=($PWD) 
else
  dirs=$(echo $@ | sed "s/['\"]//g")
  dir_array=($dirs) 
fi 

echo " " ; echo "Running overview.sh $@" ; echo " " 

if [ ! -f sample_overview.csv ]; then

  echo ' 
Determine 3 letter orientation codes (A/P=Anterior/Posterior, L/R=Left/Right, S/I=Superior/Interior):

  Open z-stack in FIJI -> 1st letter is side facing up, 2nd is side facing left, 3rd is side at stack start

  Examples:
  Zeiss LS7: ALS in agarose (axial images w/ dorsal z-stack start, dorsal toward LSFM front, & anterior up; in z-stacks A is up, L is left, S is at stack start) 
  Zeiss LS7: PLS if glued (axial images w/ dorsal z-stack  start, dorsal toward LSFM front & anterior down; in z-stacks P is up, L is left, S is at stack start)
  UltraII: AIL=LH (sagittal images w/ lateral z-stack start, medial side down, & anterior toward LSFM back; in z-stacks A is up, I is left, L is at stack start) 
  UltraII: ASR=RH (sagittal images w/ lateral z-stack start, medial side down, & anterior toward LSFM back; in z-stacks A is up, S is left, R is at stack start) 


'

  #Determine same or mixed parameters are needed for the experiment
  echo "  ####### Input parameters for whole experiment #######" ; echo " " 
  echo "  Do all samples in the experiment have the same ... "
  read -p "  antigen? (<antigen> or n): " antigen
  read -p "  brain shape (whole (w) or left (l)/right (r) hemisphere)? (w, l, r, or n): " side 
  read -p "  orientation? (<3 letter ORT> or n): " ort
  read -p "  488 min display range? (0, <new min>, or n): " autofl_min
  read -p "  xy voxel size? (<xy voxel size in microns> or <m to use metadata from 1 sample for all> or <n to use metadata from each sample>): " xy_res
  if [ "$xy_res" != "m" ] && [ "$xy_res" != "n" ] ; then
    read -p "  Enter <z voxel size in microns>: " z_res
  fi
  read -p "  presence (1) or absence (0) of an olfactory bulb? (or: n): " OB ; echo " " ; echo " " ; echo " " 

else 

  echo "  sample_overview.csv exists in $PWD, skipping."
  echo "  For small changes, edit it and corresponding exp_dir/parameters.csv manually before rerunning find_clusters.sh "
  echo "  To remake it and parameters.csv, delete $PWD/sample_overview.csv and: "
  for i in ${dir_array[@]}; do echo "  $i/parameters.csv" ; done 
  echo "  Then, rerun find_clusters.sh or overview.sh "
  echo " " 
  exit 1

fi

#Generate exp_folder/parameters.csv (used to make ./exp_summary/overview.sh)
for d in ${dir_array[@]}; do cd $d 

  #Generate parameters.csv
  if [ ! -f parameters.csv ]; then

    rm -f samples samples_sorted Sample_numbers Side Marker Condition Ort_code 488min olf_bulb Exp_Dir columns.csv 

    #Determine same or mixed parameters are needed for samples in each experiment folder
    if [ "$antigen" == "n" ] || [ "$side" == "n" ] || [ "$side" == "n" ] || [ "$ort" == "n" ] || [ "$autofl_min" == "n" ] || [ "$OB" == "n" ]; then 
      echo "  ####### Input parameters for experiment folder #######" ; echo " " 
      echo "  Do all samples in $PWD have the same ... "
    fi 
    if [ "$antigen" == "n" ]; then read -p "  antigen? (<antigen> or n): " antigen_dir ; fi
    if [ "$side" == "n" ]; then read -p "  brain shape? (w, l, r, or n): " side_dir ; fi 
    if [ "$ort" == "n" ]; then read -p "  orientation? (<3 letter ORT> or n): " ort_dir ; fi
    if [ "$autofl_min" == "n" ]; then read -p "  488 display range min? (0, <new min>, or n): " autofl_min_dir ; fi
    if [ "$OB" == "n" ]; then read -p "  presence (1) or absence (0) of an olfactory bulb? (or n): " OB_dir ; fi
    echo " " ; echo " " 

    #Make Sample column
    ls -d sample?? >> samples
    cat samples | sort > samples_sorted
    cat samples_sorted | while read line; do echo ${line: -2} >> Sample_numbers ; done
    sample_array=($(cat samples_sorted))
    if [ ${#sample_array[@]} == 0 ]; then echo '  To make sample folders (w/ 488 and ochann folders) for 10 samples, run this in the experiment folder:
for i in {01..10}; do mkdir -p sample$i sample$i/488 sample$i/ochann ; done
' ; fi 

    #Make Marker column
    if [ "$antigen" == "n" ] && [ "$antigen_dir" == "n" ]; then
      for s in ${sample_array[@]}; do 
        read -p "  Enter antigen (e.g., cFos) for $s: "
        echo $REPLY >> Marker
      done
      echo " "  
    elif [ "$antigen" == "n" ]; then
      for i in ${!sample_array[@]}; do echo $antigen_dir >> Marker ; done
    else
      for i in ${!sample_array[@]}; do echo $antigen >> Marker ; done
    fi 

    #Make Side column
    if [ "$side" == "n" ] && [ "$side_dir" == "n" ] ; then
      for s in ${sample_array[@]}; do 
        read -p "  Enter (w) for whole brain or (l)/(r) for left/right hemisphere for $s: " #left, right, or wholebrain
        echo $REPLY >> Side 
      done
      echo " " 
    elif [ "$side" == "n" ]; then
      for i in ${!sample_array[@]}; do echo $side_dir >> Side ; done
    else
      for i in ${!sample_array[@]}; do echo $side >> Side ; done 
    fi 

    #Make Ort_code column. 
    if [ "$ort" == "n" ] && [ "$ort_dir" == "n" ]; then
      for s in ${sample_array[@]}; do  
        read -p "  Enter 3 letter orientation code for $s: "
        echo $REPLY >> Ort_code 
      done
      echo " "
    elif [ "$ort" == "n" ]; then
      for i in ${!sample_array[@]}; do echo $ort_dir >> Ort_code ; done
    else
      for i in ${!sample_array[@]}; do echo $ort >> Ort_code ; done 
    fi

    #Make 488min column (For more info run: 488min.sh help OR czi_to_tif.sh help)
    if [ "$autofl_min" == "y" ] && [ "$autofl_min_dir" == "n" ]; then
      for s in ${sample_array[@]}; do  
        read -p "  Enter 0 (original 488 min) or number for 488 min display range for $s: "
        echo $REPLY >> 488min 
      done
      echo " "
    elif [ "$autofl_min" == "n" ]; then
      for i in ${!sample_array[@]}; do echo $autofl_min_dir >> 488min ; done
    else
      for i in ${!sample_array[@]}; do echo $autofl_min >> 488min ; done 
    fi

    #Make column for presence or absense of olfactory bulb for reg.sh
    if [ "$OB" == "n" ] && [ "$OB_dir" == "n" ]; then
      for s in ${sample_array[@]}; do  
        read -p "  Enter 0 for no olfactory bulb or 1 if OB exists for $s: "
        echo $REPLY >> olf_bulb 
      done
      echo " " 
    elif [ "$OB" == "n" ]; then
      for i in ${!sample_array[@]}; do echo $OB_dir >> olf_bulb ; done
    else
      for i in ${!sample_array[@]}; do echo $OB >> olf_bulb ; done 
    fi 

    #Make Condition column
    for s in ${sample_array[@]}; do 
      read -p "  Enter condition for $s: "
      echo $REPLY >> Condition
    done
    echo " " ; echo " " ; echo " " 

    #Experiment folder locations
    for i in ${!sample_array[@]}; do echo $PWD >> Exp_Dir ; done 

  else 
    echo "  parameters.csv exists in $PWD, skipping" ; echo " "
  fi
  
done

#Determine uniform xy and z voxel size in microns for experiment
if [ ! -f sample_overview.csv ]; then
  if [ "$xy_res" == "m" ]; then
    echo " " ; echo "  Getting metadata to determine xy and z res for $exp_summary " ; echo " "
    cd ${dir_array[0]} 
    cd $(ls -d sample?? | head -1)
    metadata.sh
    xy_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f1)
    z_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f3)
  fi
fi

#Generate exp_folder/parameters.csv (used to make ./exp_summary/overview.sh)
for d in ${dir_array[@]}; do cd $d 

  #Generate parameters.csv
  if [ ! -f parameters.csv ]; then

    rm -f xy_res z_res
    sample_array=($(cat samples_sorted))

    #Determine xyz voxel sise in microns for each sample
    if [ "$xy_res" == "n" ]; then
     for s in ${sample_array[@]}; do
        cd $s
        metadata.sh
        xy_res_sample=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f1)
        z_res_sample=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f3)
        cd ..
        echo $xy_res_sample >> xy_res
        echo $z_res_sample >> z_res
      done
    else
      for i in ${!sample_array[@]}; do echo $xy_res >> xy_res ; done 
      for i in ${!sample_array[@]}; do echo $z_res >> z_res ; done 
    fi

    #Combine columns
    paste -d, Sample_numbers Side Marker Condition Ort_code 488min xy_res z_res olf_bulb Exp_Dir > columns.csv #join columns with comma delimiter 

    #Add columns below headers
    cat columns.csv | while read line; do echo $line >> parameters.csv ; done
      
    rm -f samples samples_sorted Sample_numbers Side Marker Condition Ort_code 488min xy_res z_res olf_bulb Exp_Dir columns.csv 

  fi
done 

#Make sample_overview.csv
cd $exp_summary

if [ ! -f sample_overview.csv ]; then 

  for i in ${!dir_array[@]}; do 
    rsync -au ${dir_array[$i]}/parameters.csv parameters_$i.csv #copy parameters_*.csv to current working directory
  done 

  for i in parameters_*.csv; do #append parameters_*.csv from all directories
    cat $i >> sample_overview
    rm -f $i 
  done
  
  echo Sample,Side,Marker,Condition,Ort_code,488min,xy_res,z_res,olf_bulb,Exp_Dir > sample_overview.csv #headers
  sort -k1 -t, sample_overview | while read line; do echo $line >> sample_overview.csv ; done #sort -k1=1st_column -t,=comma_separated 
  rm -f sample_overview

fi


#Daniel Ryskamp Rijsketic 07/12/22-07/22/22 (Heifets lab)
