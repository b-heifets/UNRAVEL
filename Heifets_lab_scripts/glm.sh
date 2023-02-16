#!/bin/bash 
# (c) Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets @ Stanford University, 2021-2023

if [ "$1" == "help" ]; then
  echo '

glm.sh [non-template mask in 25 um Gubra atlas space]

if glm_folder/stats/design.fts exists, run ANOVA, else run t-test

With whole brains, left and right sides can 1st be overlayed with mirror.sh, then use the left template mask for non-lateral data

For a two-sample unpaired t-test based on permutation testing (takes a few days to run): 
1) make glm folder named succiently (e.g., glm_<EX>_rb<4>_z_<contrast> for t-test or anova_<EX>_rb<4>_z)
2) add <condition1/2>_sample*_gubra_space.nii.gz files and follow prompts
3) open inputs in fsleyes & the atlas to check alignment and that sides are correct: 
fsleyes.sh <display range min> <display range max> [leave blank to process all .nii.gz files or enter specific files separated by spaces]
4) run glm.sh from glm folder and follow prompts (outputs to ./stats)
tstat1 = group 1 intensities > group 2 (group order is alphabetical [use ls to check order]) 
tstat2 = group 1 < group 2  
vox_p images are uncorrected p value maps
https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/GLM 
https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/Randomise/UserGuide

For a 2x2 ANOVA, before running this script make ./anova_<EX>_rb<4>_z/stats/design
open terminal from ./stats and run: fsl
Misc -> GLM Setup
GLM Setup window: 
  Higher-level / non-timeseries design 
  # inputs: <total # of samples> 
EVs tab in GLM window: 
  # of main EVs: 4 
  Name EVs (e.g., EV1 = group 1) 
  Group should be 1 for all 
  Make design matrix: 
    Under EV1 enter 1 for each subject in group 1 (1 row/subject). EV2-4 are 0 for these rows 
    Under EV2 enter 1 for each subject in group 2, starting w/ row after the last row for group 1  
    Follow this pattern for EV3 and EV4 
Contrasts & F-tests tab in GLM window: 
  Contrasts: 3 
  C1: Main_effect_<e.g.,drug> 1 1 -1 -1 (e.g., EV1/2 are drug groups and EV3/4 are saline groups) 
  C2: Main_effect_<e.g., context> 1 -1 1 -1 (e.g., EV1/3 were in context1 and EV2/4 were in context2 )
  C3: Interaction 1 -1 -1 1 
  F-tests: 3
  F1: click upper left box 
  F2: click middle box
  F3: click lower right box
GLM Setup window: 
  Save -> click design -> OK 
run: glm.sh from anova folder
vox_p_fstat1=1st main effect 1-p values
vox_p_fstat2=2nd main effect
vox_p_fstat3=interaction


If outside of Heifets lab, update path to template mask: /usr/local/miracl/atlases/ara/gubra/
'
  exit 1
fi

GLMFolderName=${PWD##*/}

#User inputs
echo " " 
read -p "Enter side of the brain to process (l, r, both) or (m) for mask specified by 1st positional argument: " mask ; echo " "
read -p "Enter additional randomise options (aside from --uncorrp -x) or just press enter (for help run: randomise -h): " options ; echo " " 
read -p "Enter # of permutations (e.g., 6000 [must be divisible by 300]): " permutations ; echo " " 
read -p "Enter kernel radius for smoothing w/ fslmaths in mm (e.g., 0.05): " kernel ; echo " " 

kernel_in_um=$(echo "($kernel*1000+0.5)/1" | bc) #(x+0.5)/1 is used for rounding in bash and bc handles floats

#copy atlas and template mask to ./stats
cp_mask_atlas () {
  if [ "$mask" == "l" ]; then 
    cp /usr/local/miracl/atlases/ara/gubra/gubra_template_wo_OB_25um_full_bin_left.nii.gz ./stats/
    mask=gubra_template_wo_OB_25um_full_bin_left.nii.gz #voxels within mask included in GLM
  fi

  if [ "$mask" == "r" ]; then 
    cp /usr/local/miracl/atlases/ara/gubra/gubra_template_wo_OB_25um_full_bin_right.nii.gz ./stats/
    mask=gubra_template_wo_OB_25um_full_bin_right.nii.gz
  fi

  if [ "$mask" == "both" ]; then 
    cp /usr/local/miracl/atlases/ara/gubra/gubra_template_25um_thr30_bin.nii.gz ./stats/
    mask=gubra_template_25um_thr30_bin.nii.gz
  fi

  if [ "$mask" == "m" ]; then 
    cp $1 ./stats/
    mask=${1##*/}
  fi

  cp /usr/local/miracl/atlases/ara/gubra/gubra_ano_combined_25um.nii.gz ./stats/ 
}

echo "Running glm.sh with mask: $mask, options: '$options', permutations: $permutations, kernel: $kernel, from $PWD " ; echo " " 
echo "Running glm.sh with mask: $mask, options: '$options', permutations: $permutations, kernel: $kernel, from $PWD" > glm_params

#if design.fts for running ANOVA exists, then run ANOVA, else run two group t-test
if [ -f $PWD/stats/design.fts ]; then
  
  if [ ! -d stats ]; then echo "  Make ./stats/design and use fsl to set up ANOVA (run: glm.sh help) " ; fi 

  output_name="$GLMFolderName"

  cp_mask_atlas $1

  #make single volume with all subject volumes
  if [ ! -f ./stats/all.nii.gz ] ; then 
    echo "  Merging volumes" ; fslmerge -t stats/all.nii.gz *.nii.gz ; echo " "
  fi 

  cd stats

  #Run ANOVA GLM 
  if (( $kernel_in_um > 0 )); then 
  
    if [ ! -f all_s$kernel_in_um.nii.gz ] ; then echo "  Smoothing 4D volume with $kernel_in_um micron kernel " ; fslmaths all.nii.gz -s $kernel all_s$kernel_in_um.nii.gz ; echo " " ; fi

    echo " " ; echo "  Running randomise_parallel -i all_s$kernel_in_um.nii.gz -m $mask -o "$output_name" -d design.mat -t design.con -f design.fts --uncorrp -x -n $permutations $options"  ; echo Start: $(date) ; echo " "
    echo "randomise_parallel -i all_s$kernel_in_um.nii.gz -m $mask -o "$output_name" -d design.mat -t design.con -f design.fts --uncorrp -x -n $permutations $options" > glm_params

    randomise_parallel -i all_s$kernel_in_um.nii.gz -m $mask -o "$output_name" -d design.mat -t design.con -f design.fts --uncorrp -x -n $permutations $options

  else

    echo " " ; echo "  Running randomise_parallel -i all.nii.gz -m $mask -o "$output_name" -d design.mat -t design.con -f design.fts --uncorrp -x -n $permutations $options" ; echo Start: $(date) ; echo " "
    echo "randomise_parallel -i all.nii.gz -m $mask -o "$output_name" -d design.mat -t design.con -f design.fts --uncorrp -x -n $permutations $options" > glm_params

    randomise_parallel -i all.nii.gz -m $mask -o "$output_name" -d design.mat -t design.con -f design.fts --uncorrp -x -n $permutations $options

  fi

  echo " " ; echo "  ANOVA GLM finished at " $(date) ; echo " "

  cd ..

else

  group1=$(find *.nii.gz -maxdepth 0 -type f | head -n 1 | cut -d _ -f 1) #get prefix for group1
  group2=$(find *.nii.gz -maxdepth 0 -type f | tail -n 1 | cut -d _ -f 1) #get prefix for group2
  group1_N=$(find "$group1"_* -maxdepth 0 -type f | wc -l) #get N for group1
  echo " " 
  echo "  Group 1 and N: $group1 $group1_N"
  group2_N=$(find "$group2"_* -maxdepth 0 -type f | wc -l) #get N for group2
  echo "  Group 2 and N: $group2 $group2_N"
  echo " "
  
  output_name="$GLMFolderName"_"$group1"-"$group1_N"_"$group2"-"$group2_N"

  mkdir -p stats #output folder

  cp_mask_atlas $1

  #make single volume with all subject volumes
  if [ ! -f ./stats/all.nii.gz ] ; then 
    echo "  Merging volumes" ; fslmerge -t stats/all.nii.gz *.nii.gz ; echo " "
  fi 

  #make t-test design
  cd stats
  design_ttest2 design "$group1_N" "$group2_N" 

  #Run t-test GLM 
  if (( $kernel_in_um > 0 )); then 
  
    if [ ! -f all_s$kernel_in_um.nii.gz ] ; then echo "  Smoothing 4D volume with $kernel_in_um micron kernel " ; fslmaths all.nii.gz -s $kernel all_s$kernel_in_um.nii.gz ; echo " " ; fi

    echo " " ; echo "  Running randomise_parallel -i all_s$kernel_in_um.nii.gz -m $mask -o "$output_name" -d design.mat -t design.con --uncorrp -x -n $permutations $options"  ; echo Start: $(date) ; echo " "
    echo "randomise_parallel -i all_s$kernel_in_um.nii.gz -m $mask -o "$output_name" -d design.mat -t design.con --uncorrp -x -n $permutations $options" > glm_params

    randomise_parallel -i all_s$kernel_in_um.nii.gz -m $mask -o "$output_name" -d design.mat -t design.con --uncorrp -x -n $permutations $options

  else

    echo " " ; echo "  Running randomise_parallel -i all.nii.gz -m $mask -o "$output_name" -d design.mat -t design.con --uncorrp -x -n $permutations $options" ; echo Start: $(date) ; echo " "
    echo "randomise_parallel -i all.nii.gz -m $mask -o "$output_name" -d design.mat -t design.con --uncorrp -x -n $permutations $options" > glm_params

    randomise_parallel -i all.nii.gz -m $mask -o "$output_name" -d design.mat -t design.con --uncorrp -x -n $permutations $options

  fi

  echo " " ; echo " t-test GLM finished at " $(date) ; echo " "

  cd ..

fi 


#Daniel Ryskamp Rijsketic & Austen Casey 9/21/21 & 06/08/22 & 06/22/22 (Heifets Lab)
