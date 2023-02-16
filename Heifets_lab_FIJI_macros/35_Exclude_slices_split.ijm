// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023
// (Daniel Rijsketic Jan. 29, 2021)
//===================================================

//opens ABAsegsubstack and splits into 3 substacks and saves. Shell script deletes original tif having 3dc error.

//Inputs: 1) if csv has error, process corresponding tif file 

setBatchMode(true); //comment this out to make images visible during macro execution

filelist = getArgument();
file = split(filelist,'#');

//************ 1) Open tif substack ************************************************
open(file[0]); 
dir = getDirectory("image");
substack=getTitle();

//for substacks with 102 slices ("exclude objects on edges") if error -> 
//e1-35 (e35) -floor(35/3)+1=11.6667+1 -> e13   i12     e12
//e1-13      i13-24      e24-35
run("Duplicate...", "duplicate range=1-13");
saveAs("Tiff", dir+substack+"_1_13_ExcludeSmall"); //This is an Exclude objects on edges substack with Small level split
close();
selectWindow(substack);
run("Duplicate...", "duplicate range=13-24");
saveAs("Tiff", dir+substack+"_13_24_IncludeSmall"); //This is an Include objects on edges substack with Small level split
close();
selectWindow(substack);
run("Duplicate...", "duplicate range=24-35");
saveAs("Tiff", dir+substack+"_24_35_ExcludeSmall"); //This is an Exclude objects on edges substack with Small level split
close();
selectWindow(substack);
close();

setBatchMode(false);
EndTime=getTime();

run("Quit");


