// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023
// divide_Include_substack_into_3 (Daniel Rijsketic Jan. 29, 2021)
//opens 100_slice_include_substack and splits into 3 substacks and saves. Shell script deletes original csv and tif having 3dc error.

//Inputs: 1) if csv has error, process corresponding tif file 

//3d_count_cluster3.sh at /usr/local/miracl/miracl/seg

setBatchMode(true);

filelist = getArgument();
file = split(filelist,'#');

//************ 1) Open tif substack ************************************************
open(file[0]); 
dir = getDirectory("image");
substack=getTitle();

//100i split into 34i 34e 34i -floor(100/3)=34
//i1-34      e34-67     i67-100
run("Duplicate...", "duplicate range=1-34");
run("NIfTI-1", "save="+dir+"/"+substack+"_1_34_IncludeMid.nii"); //This is an Include objects on edges substack Mid level split
close();
selectWindow(substack);
run("Duplicate...", "duplicate range=34-67");
run("NIfTI-1", "save="+dir+"/"+substack+"_34_67_ExcludeMid.nii"); //This is an Exclude objects on edges substack Mid level split
close();
selectWindow(substack);
run("Duplicate...", "duplicate range=67-100");
run("NIfTI-1", "save="+dir+"/"+substack+"_67_100_IncludeMid.nii"); //This is an Include objects on edges substack Mid level split
close();
selectWindow(substack);
close();

setBatchMode(false);
EndTime=getTime();

run("Quit");
 

