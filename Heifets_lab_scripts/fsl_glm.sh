#!/bin/bash 
# (c) Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets @ Stanford University, 2021-2023

if [ $# -ne 0 ]; then 
  if [ $1 == "help" ]; then
    echo " " 
    echo " For a two-sample unpaired t-test (takes a few min):  "
    echo " 1) run from glm folder named succiently (e.g., glm_<EXP>) "
    echo " 2) add <condition1/2>_sample*_gubra_space.nii.gz files and follow prompts "
    echo " 3) open inputs in fsleyes & the atlas to check alignment and that sides are correct: " ; echo " " 
    echo "fsleyes $(for i in *gz ; do echo <dollar>i -dr <min> <max> -d ; done) /usr/local/miracl/atlases/ara/gubra/gubra_ano_combined_25um.nii.gz -ot label -o" ; echo " " 
    echo " 4) run fsl_glm.sh from glm folder and follow prompts (outputs to ./fsl_glm_stats/) " ; echo " " 
    echo " tstat1 =  group 1 activity > group 2 (group order is alphabetical [use ls to check order]) " 
    echo " tstat2 =  group 2 activity > group 1 " ; echo " " 
    echo " " 
    exit 1
  fi
fi 

group1=$(find *.nii.gz -maxdepth 0 -type f | head -n 1 | cut -d _ -f 1) #get prefix for group1
group2=$(find *.nii.gz -maxdepth 0 -type f | tail -n 1 | cut -d _ -f 1) #get prefix for group2
group1_N=$(find "$group1"_* -maxdepth 0 -type f | wc -l) #get N for group1
echo " " 
echo "Group 1 and N: $group1 $group1_N"
group2_N=$(find "$group2"_* -maxdepth 0 -type f | wc -l) #get N for group2
echo "Group 2 and N: $group2 $group2_N"
echo " "

GLMFolderName=${PWD##*/}

out=fsl_"$GLMFolderName"_"$group1"-"$group1_N"_"$group2"-"$group2_N" #output_name

if [ ! -d fsl_glm_stats ]; then mkdir fsl_glm_stats ; fi #output folder

#User inputs
read -p "Enter side of the brain to process (l, r, or both): " side
read -p "Enter additional fsl_glm options or just press enter (for help run: fsl_glm -h): " options
read -p "Enter kernel radius for smoothing w/ fslmaths in mm (e.g., 0.05): " kernel
kernel_in_um=$(echo "($kernel*1000+0.5)/1" | bc) #(x+0.5)/1 is used for rounding in bash and bc handles floats

#save inputs
echo "Side: $side" > fsl_glm_params ; echo "Smoothing in mm: $kernel" >> fsl_glm_params ; echo "Extra fsl_glm options: $options" >> fsl_glm_params

#copy atlas and template mask to ./fsl_glm_stats
if [ $side == "l" ]; then 
  cp /usr/local/miracl/atlases/ara/gubra/gubra_template_wo_OB_25um_full_bin_left.nii.gz ./fsl_glm_stats/
  mask=gubra_template_wo_OB_25um_full_bin_left.nii.gz #voxels within mask included in fsl_glm
fi

if [ $side == "r" ]; then 
  cp /usr/local/miracl/atlases/ara/gubra/gubra_template_wo_OB_25um_full_bin_right.nii.gz ./fsl_glm_stats/
  mask=gubra_template_wo_OB_25um_full_bin_right.nii.gz
fi

if [ $side == "both" ]; then 
  cp /usr/local/miracl/atlases/ara/gubra/gubra_template_25um_thr30_bin.nii.gz ./fsl_glm_stats/
  mask=gubra_template_25um_thr30_bin.nii.gz
fi

cp /usr/local/miracl/atlases/ara/gubra/gubra_ano_combined_25um.nii.gz ./fsl_glm_stats/

#make single volume with all subject volumes
if [ ! -f ./fsl_glm_stats/all.nii.gz ] ; then cp ./stats/all.nii.gz ./fsl_glm_stats ; if [ ! -f ./fsl_glm_stats/all.nii.gz ] ; then fslmerge -t fsl_glm_stats/all.nii.gz *.nii.gz ; fi ; fi 

#make t-test design
cd fsl_glm_stats
design_ttest2 design "$group1_N" "$group2_N" 

#Run fsl_glm 
if (( $kernel_in_um > 0 )); then 
  
  if [ ! -f all_s$kernel_in_um.nii.gz ] ; then cd .. ; cp ./stats/all_s$kernel_in_um.nii.gz ./fsl_glm_stats ; cd fsl_glm_stats ; if [ ! -f all_s$kernel_in_um.nii.gz ] ; then fslmaths all.nii.gz -s $kernel all_s$kernel_in_um.nii.gz ; fi ; fi

fsl_glm -i all_s$kernel_in_um.nii.gz -m $mask -d design.mat -c design.con -o "$out"_fsl_glm_betas --out_cope="$out"_cope.nii.gz --out_z="$out"_z.nii.gz --out_t="$out"_t.nii.gz --out_p="$out"_p.nii.gz --out_f="$out"_F-val_for_full_model.nii.gz --out_pf="$out"_p-val_for_full_model.nii.gz --out_res=res.nii.gz

  echo " " ; echo " Running fsl_glm -i all_s$kernel_in_um.nii.gz -m $mask -d design.mat -c design.con -o "$out"_fsl_glm_betas --out_cope="$out"_cope.nii.gz --out_z="$out"_z.nii.gz --out_t="$out"_t.nii.gz --out_p="$out"_p.nii.gz --out_f="$out"_F-val_for_full_model.nii.gz --out_pf="$out"_p-val_for_full_model.nii.gz --out_res=res.nii.gz $options"  ; echo Start: $(date) ; echo " "
  echo "fsl_glm -i all_s$kernel_in_um.nii.gz -m $mask -d design.mat -c design.con -o "$out"_fsl_glm_betas --out_cope="$out"_cope.nii.gz --out_z="$out"_z.nii.gz --out_t="$out"_t.nii.gz --out_p="$out"_p.nii.gz --out_f="$out"_F-val_for_full_model.nii.gz --out_pf="$out"_p-val_for_full_model.nii.gz --out_res=res.nii.gz $options" > fsl_glm_params

  fsl_glm -i all_s$kernel_in_um.nii.gz -m $mask -d design.mat -c design.con -o "$out"_fsl_glm_betas --out_cope="$out"_cope.nii.gz --out_z="$out"_z.nii.gz --out_t="$out"_t.nii.gz --out_p="$out"_p.nii.gz --out_f="$out"_F-val_for_full_model.nii.gz --out_pf="$out"_p-val_for_full_model.nii.gz --out_res=res.nii.gz $options

else

  echo " " ; echo " Running fsl_glm -i all.nii.gz -m $mask -d design.mat -c design.con -o "$out"_fsl_glm_betas --out_cope="$out"_cope.nii.gz --out_z="$out"_z.nii.gz --out_t="$out"_t.nii.gz --out_p="$out"_p.nii.gz --out_f="$out"_F-val_for_full_model.nii.gz --out_pf="$out"_p-val_for_full_model.nii.gz --out_res=res.nii.gz $options" ; echo Start: $(date) ; echo " "
  echo "fsl_glm -i all.nii.gz -m $mask -d design.mat -c design.con -o "$out"_fsl_glm_betas --out_cope="$out"_cope.nii.gz --out_z="$out"_z.nii.gz --out_t="$out"_t.nii.gz --out_p="$out"_p.nii.gz --out_f="$out"_F-val_for_full_model.nii.gz --out_pf="$out"_p-val_for_full_model.nii.gz --out_res=res.nii.gz $options" > fsl_glm_params

  fsl_glm -i all.nii.gz -m $mask -d design.mat -c design.con -o "$out"_fsl_glm_betas --out_cope="$out"_cope.nii.gz --out_z="$out"_z.nii.gz --out_t="$out"_t.nii.gz --out_p="$out"_p.nii.gz --out_f="$out"_F-val_for_full_model.nii.gz --out_pf="$out"_p-val_for_full_model.nii.gz --out_res=res.nii.gz $options

fi

echo " " ; echo " fsl_glm finished at " $(date) ; echo " "

if [ ! -f "$out"_1-p.nii.gz ]; then 
  echo " " ; echo " p to 1-p conversion starting at " $(date) ; echo " "

  fslmaths "$out"_p.nii.gz -mul -1 "$out"_p_times-1.nii.gz
  fslmaths "$out"_p_times-1.nii.gz -add 1 "$out"_1-p_wOnes.nii.gz
  fslmaths "$out"_1-p_wOnes.nii.gz -thr 1 -uthr 1 -bin ones_mask.nii.gz
  fslmaths "$out"_1-p_wOnes.nii.gz -sub ones_mask.nii.gz "$out"_1-p.nii.gz
  rm "$out"_p_times-1.nii.gz "$out"_1-p_wOnes.nii.gz ones_mask.nii.gz

  echo " " ; echo " p to 1-p conversion finished at " $(date) ; echo " "
fi


cd ..

#Daniel Ryskamp Rijsketic & Austen Casey 9/21/21 & 06/08/22
