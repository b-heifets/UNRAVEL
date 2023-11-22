//opens ABAseg_substack and splits into 3 substacks and saves. Shell script deletes original csv and tif having 3dc error.

//Inputs: 1) if csv has error, process corresponding tif file 

//ABAseg_3dc.sh at /usr/local/miracl/miracl/seg

setBatchMode(true);

filelist = getArgument();
file = split(filelist,'#');

//************ 1) Open tif substack ************************************************
open(file[0]); 
dir = getDirectory("image");
substack=getTitle();

//e27 -> e10   i9     e10
//e1-10      i10-18      e18-27
run("Duplicate...", "duplicate range=1-10");
run("NIfTI-1", "save="+dir+substack+"_1_10_ExcludeSmall.nii"); //This is an Exclude objects on edges substack Small level split
close();
selectWindow(substack);
run("Duplicate...", "duplicate range=10-18");
run("NIfTI-1", "save="+dir+substack+"_10_18_IncludeSmall.nii"); //This is an Include objects on edges substack Small level split
close();
selectWindow(substack);
run("Duplicate...", "duplicate range=18-27");
run("NIfTI-1", "save="+dir+substack+"_18_27_ExcludeSmall.nii"); //This is an Exclude objects on edges substack Small level split
close();
selectWindow(substack);
close();

setBatchMode(false);
EndTime=getTime();

run("Quit");


