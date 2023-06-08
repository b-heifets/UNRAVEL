#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

#Find 100 slice substack counting errors, split substacks with errors, rerun 3D count 
for f in *.nii.gz_*.csv; do
	case $f in 
	*_IncludeEdges.nii.gz_I.csv)
	error=$(awk 'FNR == 3 {print}' $f)
	if [[ $error == *"error"* ]]; then
		echo "ERROR" in $f
		ImageCausingError=$PWD/${f::-6}
		java -jar /usr/local/miracl/depends/Fiji.app/jars/ij-1.53c.jar -ijpath /usr/local/miracl/depends/Fiji.app -macro 100_Include_slices_split "$ImageCausingError"
		gzip -f -9 "$ImageCausingError"_1_34_IncludeMid.nii
		gzip -f -9 "$ImageCausingError"_34_67_ExcludeMid.nii
		gzip -f -9 "$ImageCausingError"_67_100_IncludeMid.nii
		rm $f
		rm "$ImageCausingError"
		/usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_IncludeEdges "$ImageCausingError"_1_34_IncludeMid.nii.gz
		/usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_ExcludeEdges "$ImageCausingError"_34_67_ExcludeMid.nii.gz
		/usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_IncludeEdges "$ImageCausingError"_67_100_IncludeMid.nii.gz
	fi
	;;
	*_ExcludeEdges.nii.gz_E.csv)
	error=$(awk 'FNR == 3 {print}' $f)
	if [[ $error == *"error"* ]]; then
	echo "ERROR" in $f
	ImageCausingError=$PWD/${f::-6}
	java -jar /usr/local/miracl/depends/Fiji.app/jars/ij-1.53c.jar -ijpath /usr/local/miracl/depends/Fiji.app -macro 102_Exclude_slices_split "$ImageCausingError"
	gzip -f -9 "$ImageCausingError"_1_35_ExcludeMid.nii
	gzip -f -9 "$ImageCausingError"_35_68_IncludeMid.nii
	gzip -f -9 "$ImageCausingError"_68_102_ExcludeMid.nii
	rm $f
	rm "$ImageCausingError"
	/usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_ExcludeEdges "$ImageCausingError"_1_35_ExcludeMid.nii.gz
	/usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_IncludeEdges "$ImageCausingError"_35_68_IncludeMid.nii.gz
	/usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_ExcludeEdges "$ImageCausingError"_68_102_ExcludeMid.nii.gz
	fi
	;;
	esac
done

echo " " 
echo "Errors after recounting (no errors if blank):"
grep -rq clij 
echo " " 

#rm all.csv
#cat *csv > all.csv
#cat all.csv | wc -l 

#Daniel Ryskamp Rijsketic 04/28/2022-06/26/2022 12/12/22ss (Heifets lab)
