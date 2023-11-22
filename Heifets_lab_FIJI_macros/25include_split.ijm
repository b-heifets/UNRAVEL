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

//i25  -> i8      e10      i9
//i1-8      e8-17      i17-25
run("Duplicate...", "duplicate range=1-8");
run("NIfTI-1", "save="+dir+substack+"_1_8_IncludeSmall.nii"); //This is an Include objects on edges substack Small level split
close();
selectWindow(substack);
run("Duplicate...", "duplicate range=8-17");
run("NIfTI-1", "save="+dir+substack+"_8_17_ExcludeSmall.nii"); //This is an Exclude objects on edges substack Small level split
close();
selectWindow(substack);
run("Duplicate...", "duplicate range=17-25");
run("NIfTI-1", "save="+dir+substack+"_17_25_IncludeSmall.nii"); //This is an Include objects on edges substack Small level split
close();
selectWindow(substack);
close();

setBatchMode(false);
EndTime=getTime();

run("Quit");
 

