# (c) Austen B. Casey, Boris Heifets @ Stanford University, 2022-2023

#Take reverse each warp, s50, mask out the CeA cluster, get the average voxel in the ceA cluster, multiple by the binary CeA cluster mask, for each sample:
#Run pearson correlation in the Average CeA cluster for 4D volumes of pslocybin and saline

#Might try correlating average cluster intensity that that of another cluster (defined by an arbitrary extent) based on Pearson r or after Fisher's r to Z transformation 

#See what is correlated ineach treatment volum: validate by scatterplot of density for CeA vs ClusterX for each group

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
sub_average_4D.sh <path/cluster_mask.nii.gz> <path/smoothed_4D_timeseries.nii.gz> <cluster_name>

This script replaces the voxels in a 4D image with the average intensity of voxels in the mask. It is useful for seed based Pearson correlations in FSLeyes, wherein the average voxel intensity in a cluster is used as the seed for each 3D image in a 4D volume. 
'
  exit 1
fi

n=$(fslnvols $2)
timeseries_starter=$(basename $2 .nii.gz)

#Check to see if conflicting or incomplete intermediate files exist, and if not, split 4D timeseries into its component 3D images
if [ $(ls vol????.nii.gz 2>/dev/null | wc -l) != $n ]; then
	rm vol????.nii.gz
	fslsplit $2 -t
fi

if [ $(ls *mean.csv 2>/dev/null | wc -l) != $n ]; then
	rm *mean.csv
	for i in vol????.nii.gz ; do fslstats $i -k $1 -m > "${i::-7}"_mean.csv ; done
fi

#Isolate original cluster from each 3D image
if [ $(ls vol????_cluster.nii.gz 2>/dev/null | wc -l) != $n ]; then
	rm vol????_cluster.nii.gz
	for i in vol????.nii.gz ; do fslmaths $i -mas $1 "${i::-7}"_cluster.nii.gz ; done
fi

#Apply the average voxel intensity to all voxels in the cluster for each 3D image
if [ $(ls vol????_ave_cluster.nii.gz 2>/dev/null | wc -l) != $n ]; then
	rm vol????_ave_cluster.nii.gz
	for i in vol*.nii.gz ; do fslmaths $i -mas $1 -bin -mul $(cat "${i::7}"_mean.csv) "${i::-7}"_ave_cluster.nii.gz ; done
fi

#Remove cluster from each 3D image
if [ $(ls vol????_hole.nii.gz 2>/dev/null | wc -l) != $n ]; then
	rm vol????_hole.nii.gz
	for i in vol????.nii.gz ; do fslmaths $i -sub "${i::-7}"_cluster.nii.gz "${i::-7}"_hole.nii.gz ; done
fi

#Add average cluster intensity to the hole
if [ $(ls vol????_averaged.nii.gz 2>/dev/null | wc -l) != $n ]; then
	rm vol????_averaged.nii.gz
	for i in *_hole.nii.gz ; do fslmaths $i -add "${i::-12}"_ave_cluster.nii.gz "${i::-12}"_averaged.nii.gz ; done
fi

#Generate cloned 4D timeseries with the average cluster intensity substituted in place of the cluster 
if [! -f "$timeseries_starter"_$3.nii.gz ]; then
fslmerge -t "$timeseries_starter"_$3.nii.gz $(echo vol????_averaged.nii.gz)
fi

rm vol*

fsleyes "$timeseries_starter"_$3.nii.gz -dr -2 2

#Austen B. Casey 10/21/22 (Heifets Lab)

