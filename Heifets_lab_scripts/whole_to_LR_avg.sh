#!/bin/bash

if [[ $# == 0 || "$1" == "-h" || "$1" == "--help" || "$1" == "help" ]] ; then
  echo '
To z-score whole brains, then average the L and R hemispheres together to obtain a new L hemisphere for each sample run from experiment folder containing gubra space images: whole_to_LR_avg.sh <path/whole brain mask for z scoring> <path/LH_mask> <path/RH mask> <gubra space images separated by spaces>

Input: ./sample??/sample??*gubra_space.nii.gz
Output: ./sample??/sample??_*_gubra_space_LR_avg.nii.gz

'
  exit 1
fi

echo " " ; echo "Running whole_to_LR_avg.sh $@ from $PWD" ; echo " " 

if [ $# -gt 3 ]; then 
  sample_array=($(echo "${@:4}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample*rb4_gubra_space.nii.gz) 
fi


z_mask=($(echo $1 | sed "s/['\"]//g"))
LH_mask=($(echo $2 | sed "s/['\"]//g"))
RH_mask=($(echo $3 | sed "s/['\"]//g"))
max_value=$(echo $(ls sample??_* | sort -t'_' -k1,1n | tail -n 1 | sed 's/sample//' | cut -d'_' -f1))

mkdir og_gubra_space z_scored_whole_brains LH RH mirrored_RH masks


for i in "${sample_array[@]}"; do
    z_sample="${i::-19}_z_gubra_space.nii.gz"
    if [ ! -f "$z_sample" ] ; then
        z_brain_mask.sh "$z_mask"
    fi
done

z_array=(sample*rb4_z_gubra_space.nii.gz) 

for i in ${z_array[@]} ; do 
	fslmaths $i -mas $LH_mask ${i::-7}_LH.nii.gz
	fslmaths $i -mas $RH_mask ${i::-7}_RH.nii.gz
	done

mirror.sh *RH.nii.gz 

for i in mirror* ; do 
	mv "$i" "${i/mirror_/}" 
done

for id in $(seq -w 1 $max_value); do 
    # Create the output and input filenames
    output="sample${id}_cfos_rb4_z_gubra_space_LR_4D.nii.gz"
    lh_file="sample${id}_cfos_rb4_z_gubra_space_LH.nii.gz"
    rh_file="sample${id}_cfos_rb4_z_gubra_space_RH.nii.gz"
    
    # Check if both LH and RH files exist before running fslmerge
    if [ -f "$lh_file" ] && [ -f "$rh_file" ]; then
        fslmerge -t "$output" "$lh_file" "$rh_file"
    else
        echo "Files for sample${id} are missing."
    fi
done

for i in *LR_4D.nii.gz ; do 
	fslmaths $i -Tmean ${i::-9}avg.nii.gz 
done

cp "$z_mask" "$LH_mask" "$RH_mask" "$PWD/masks/"
cp sample*rb4_gubra_space.nii.gz "$PWD/og_gubra_space/"
cp *z_gubra_space.nii.gz "$PWD/masks/"
cp *_LH.nii.gz "$PWD/LH/"
cp *_RH.nii.gz "$PWD/RH/"
cp mirror*.nii.gz "$PWD/mirrored_RH/"

#rm *_RH.nii.gz *_LH.nii.gz sample*rb4_gubra_space.nii.gz *z_gubra_space.nii.gz


# Austen Casey 10/26/23
