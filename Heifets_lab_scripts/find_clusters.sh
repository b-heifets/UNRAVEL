#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

echo '
################################# Summary ######################################
This script from Boris Heifets'\''s lab at Stanford automatically preps 3D images of immunostained and cleared mouse brains or hemispheres for voxel-wise analysis in atlas space to find clusters of voxels with significantly different intensities between groups (e.g., hot/cold spots in cFos+ cell density from an experimental treatment). 

For more details and tips, run: find_clusters.sh help
For more info on subscripts, run: <subscript> help
Subscripts: overview.sh, czi_to_tif.sh or prep_tifs.sh, 488_to_nii.sh, reg.sh, rb.sh (or ochann_to_nii.sh), z_brain_template_mask.sh, fsleyes.sh

Additional outputs: ./exp_dirs/parameters.csv (local info w/ no headers) ./exp_summary/sample_overview.csv (global info w/ headers)


######################## Steps for find_clusters.sh ###########################
. activate miracl 

#Make experiment folder(s) and 
cd <./EXP_folder> 

#To make sample folders for 99 samples, run:
for i in {01..99}; do mkdir -p sample$i sample$i/488 sample$i/ochann ; done

#If starting with a tif series for 488 and ochann, move it to respective folders. If starting with .czi, move it to sample?? folder

#Determine & note the new min for the 488 display range for all samples. If an approximate value works uniformly, use that.

#Make an experiment summary folder and
cd <EXP_summary>

#Follow prompts in terminal after running: 
find_clusters.sh [Enter space seperated list of experiment folder paths (to process all samples) OR sample folder paths (to process specific samples)]

################################################################################
'

if [ "$1" == "help" ]; then
  echo '

################################# Summary ######################################
This script automatically preps 3D images for voxel-wise analysis. Inputs are z-stacks of immunolabeled mouse brains cleared with iDISCO+ and imaged with a lightsheet microscope. MIRACL (Maged Goubran) is used to warp the Gubra version of the Allen brain atlas (ABA) to each mouse brain or hemisphere by aligning the autofluorescence channel (488 nm excitation) with an averaged template brain. The other channel (ochann) is of fluorescent immunostaining (e.g., rabbit anti-cFos & donkey anti-rabbit Alexa Fluor® 647 antibodies). The min display range of the 488 channel can be adjusted to zero out most voxels outside of the brain to improve registration (open 488 virtual stack in FIJI-> control+shift+t -> use sliders to find new 488 min). Tif image sequences (./sample??/488/tifs & ./sample??/ochann/tifs) or a /sample??/.czi file are converted to ./sample??/niftis/sample??_02x_down_autofl_chan.nii.gz and ./sample??/niftis/sample??_02x_down_ochann_chan.nii.gz. To improve sensitivity of voxel-wise analysis, background is rolling ball subtracted from ochann before warping brains to atlas space. These image volumes are smoothed to account for  inaccuracies in registration prior to running voxel-wise t-tests and/or ANOVAs using randomise (an fMRI data analysis tool for GLM-based, permutation testing from FSL) to identify significant changes in intensity (e.g., cluster of voxels with increases or decreases in cFos+ cell density from an experimental treatment) thoughout the brain. 

For more details and tips, run: find_clusters.sh help
For more info on subscripts, run: <subscript> help
Subscripts: overview.sh, czi_to_tif.sh or prep_tifs.sh, 488_to_nii.sh, reg.sh, rb.sh (or ochann_to_nii.sh), z_brain_template_mask.sh, fsleyes.sh

Additional outputs: ./exp_dirs/parameters.csv (local info w/ no headers) ./exp_summary/sample_overview.csv (global info w/ headers)


####################### Steps for find_clusters.sh #############################

#activate the virtual environment for MIRACL (Do this before running scripts in case dependencies are needed)
. activate miracl 

#Make experiment folder(s). Data is often stored in a few locations for parallel processing or because of space on drives.
cd <./EXP_dir> 

#To make sample folders (w/ 488 and ochann folders) for 99 samples (limit to 2 digits for sample numbers), run:
for i in {01..99}; do mkdir -p sample$i sample$i/488 sample$i/ochann ; done

#If starting with a tif series for 488 and ochann, move it to respective folders. If starting with .czi, move it to sample?? folder

#Determine & note the new min for the 488 display range for all samples. If an approximate value works uniformly, use that.

#Make and cd to an experiment summary folder for main outputs and global analyses. It will eventually include
./ochann_rb*_z_gubra_space_z (or ./ochann_z_gubra_space) #samples in Gubra atlas space used for voxel-wise stats
./voxel-wise_stats
./cluster_validation_summary
sample_overview.csv
rolling_ball_radius

#Follow prompts in terminal after running: 
find_clusters.sh 

#Or:
find_clusters.sh [Enter space seperated list of experiment folder paths (to process all samples) OR sample folder paths (to process specific samples)]


############################## Next steps ######################################

#Once ./EXP_dir/sample??/ochann/tifs exist for all samples, you can run validate_clusters.sh for making the ilastik segmentation of cells and consensus.

#Once registration is finished, check quality for each sample

#Once all ./ochann_rb*_z/sample??_ochann_rb*_z_gubra_space.nii.gz are made, check alignment with fsleyes.sh and use mirror.sh or flip.sh and/or shift.sh as needed.

#Then run make glm folder for voxel-wise stats with input files and run glm.sh

#After voxel-wise analyses have finished, remaining steps in validate_clusters.sh can be run.


################################# Notes ########################################

#Outputs from scripts generally skipped if rerunning them. If stopping script with control+c, delete partial outputs if any.

#For batch processing of data in parallel threads (e.g., on different RealVNC virtual desktops), first from the experiment summary folder run: overview.sh <list all path/experiment_folders seperated by spaces>. Then from one virtual desktop run find_clusters.sh with a subset of the data and from another virtual desktop run find_clusters.sh with another subset of the data. Do not run parallel threads on the same desktop, because FIJI macros will have cross talk. Data can be processed on externals, but limit processing to one thread per external. Parallel threads can really bog them down. 

#To move samples and auto update sample_overview.csv and parameters.csv files accordingly use mv_samples.sh


#Note, the path to run FIJI macros is hard coded in several scripts (/usr/local/miracl/depends/Fiji.app/ImageJ-linux64). Macros need to be located in /usr/local/miracl/depends/Fiji.app/macros/

#If running our shell scripts on a new computer or after downloading updated scripts, first install MIRACL, etc. (https://miracl.readthedocs.io/en/latest/index.html) and update the FIJI path in our scripts:
cd <./folder_w_sh_scripts>
sed -i -E "s#/usr/local/miracl/depends/Fiji.app/ImageJ-linux64#<new_FIJI_path/...>#g" *.sh
sed -i -E "s#/usr/local/miracl/depends/Fiji.app/jars/ij-1.53c.jar#<new_FIJI_path/jars/...>#g" *.sh
sed -i -E "s#/usr/local/miracl/depends/Fiji.app#<path/Fiji.app>#g" *.sh

#Similarly, update paths to gubra atlas files
sed -i -E "s#/usr/local/miracl/atlases/ara/gubra/#<new_path>#g" *.sh

################################################################################
'
  exit 1
fi

exp_summary=$PWD

###### Input(s) for which experiment folders or samples to process: ####### 
if [ $# -eq 0 ]; then #if no positional args provided, then accept user input
  echo " " ; echo "To make list for following input, drag and drop path/exp_dir or path/exp_dir/sample?? folders into the terminal" ; echo " " 
  read -p "Enter space seperated list of experiment folder paths (to process all samples) OR sample folder paths (to process specific samples): " paths ; echo " " 
  path_array=($(echo $paths | sed "s/['\"]//g")) # ' marks removed (can then drag & drop exp folders into terminal to input paths)
else
  path_array=($(echo $@ | sed "s/['\"]//g"))
fi

#Check if first path in path_array is for an experiment folder or a sample folder
path1_basename=$(basename ${path_array[0]}) #get name of last folder in path
if [ "${path1_basename::-2}" == "sample" ]; then #remove last two characters and check if the folder name starts with "sample"
  samples=${path_array[@]%/} #path/sample?? array
else 
  #make array with all paths/samples from exp_dir array
  samples=($(for d in ${path_array[@]%/}; do cd $d ; for s in $(ls -d sample??); do cd $s ; echo $PWD ; cd .. ; done ; done))
fi

cd $exp_summary

#Rerun script with parameters saved in inputs text file (group dirs, samples, and glm paths with ' marks for positional args when rerunning script
echo " " ; echo " " ; echo "Rerun script with: " ; echo " " ; echo "find_clusters.sh '${path_array[@]}' starting at" $(date) ; mkdir -p rerun_find_clusters ; echo "find_clusters.sh '${path_array[@]}'" > ./rerun_find_clusters/rerun_find_clusters_$(date "+%F-%T") ; echo " " ; echo " " ; echo " " 

#Rolling ball background subtraction of ochann (For more info run: rb.sh help)
if [ -f rolling_ball_radius ]; then 
  rb_radius=$(cat rolling_ball_radius)
else
  read -p "Enter number of pixels for rolling ball radius (~radius of largest object of interest) for background subtraction or 0 for using raw data: " rb_radius ; echo $rb_radius > rolling_ball_radius ; echo " " 
fi
if [ "$rb_radius" = "0" ]; then 
  mkdir -p ochann_z_gubra_space
else
  mkdir -p ochann_rb"$rb_radius"_z_gubra_space
fi 

##################################################################
######################## Run scripts #############################
##################################################################

#Make ./exp_dirs/parameters.csv (local info w/ no headers) ./exp_summary/sample_overview.csv (global info w/ headers)
uniq_exp_dir_array=($(tr ' ' '\n' <<<"${samples[@]%/*}" | awk '!u[$0]++' | tr '\n' ' ')) #path/exp_folder array
#https://www.baeldung.com/linux/bash-unique-values-arrays
overview.sh ${uniq_exp_dir_array[@]} 

for s in ${samples[@]}; do
  cd ${s%/*} #path/exp_folder

  #Get parameters:
  side=$(grep ${s: -2} parameters.csv | cut -d, -f2) #(grep sample digits returns its line in parameters.csv | 2nd word)
  ort=$(grep ${s: -2} parameters.csv | cut -d, -f5) #3 letter orientation code
  autofl_min=$(grep ${s: -2} parameters.csv | cut -d, -f6) #display range min for 488 
  xy_res=$(grep ${s: -2} parameters.csv | cut -d, -f7) #xy voxel size in microns
  z_res=$(grep ${s: -2} parameters.csv | cut -d, -f8) #z voxel size in microns
  OB=$(grep ${s: -2} parameters.csv | cut -d, -f9) #presense/absence of olfactory bulb (1/0)

  if ls $s/*.czi 1> /dev/null 2>&1; then #If ./sample??/*.czi exists, split channels and save tifs to ./sample??/488 and ./sample??/ochann
    czi_to_tif.sh $autofl_min ${s##*/} #488_display_range_min sample_folder
  else 
    prep_tifs.sh $autofl_min ${s##*/} 
  fi

  488_to_nii.sh $xy_res $z_res ${s##*/} 

  reg.sh $ort $OB $side ${s##*/} 

  if [ "$rb_radius" == "0" ]; then 
    ochann_to_nii.sh $xy_res $z_res ${s##*/}
    ochann_to_gubra.sh $ort ${s##*/}
    cd ${s##*/} 
    z_brain_template_mask.sh $side ${s##*/}_ochann_gubra_space.nii.gz
    cp ${s##*/}_ochann_z_gubra_space.nii.gz $exp_summary/ochann_z_gubra_space/
    cd ..
  else
    rb.sh $ort $rb_radius $xy_res $z_res ${s##*/} 
    cd ${s##*/} 
    z_brain_template_mask.sh $side ${s##*/}_ochann_rb"$rb_radius"_gubra_space.nii.gz
    cp ${s##*/}_ochann_rb"$rb_radius"_z_gubra_space.nii.gz $exp_summary/ochann_rb"$rb_radius"_z_gubra_space/
    cd ..
  fi

done

######### Visualizing samples in atlas space ##########
if [ "$rb_radius" == "0" ]; then 
  cd $exp_summary/ochann_z_gubra_space ; fsleyes.sh 0 3
else
  cd $exp_summary/ochann_rb"$rb_radius"_z_gubra_space ; fsleyes.sh 0 3 
fi

echo "  find_clusers.sh '${path_array[@]}' finished at" $(date) 


#Daniel Ryskamp Rijsketic 07/12/2022-07/22/2022 (Heifets lab)
