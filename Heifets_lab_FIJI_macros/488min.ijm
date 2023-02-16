// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023
setBatchMode(true); //comment this out to make images visible during macro execution

inputlist = getArgument();
input = split(inputlist,'#');

//************ Open 488 image sequence *************************************************
run("Image Sequence...", "open=["+input[0]+"] sort"); //select first image in 488 folder
dir = getDirectory("image");
ParentFolderPath=File.getParent(dir);
SampleFolder=File.getName(ParentFolderPath);

//************ Adjust display range ****************************************************
setMinAndMax(input[1], 65535); //input[1] = 488 min passed from 488min.sh   #setMinAndMax
run("Apply LUT", "stack");
run("Image Sequence... ", "format=TIFF name="+SampleFolder+"_Ch1_ save="+ParentFolderPath+"/488/"+SampleFolder+"_Ch1_0000.tif");
close();

//************ Save 488_min to log it and prevent reprocessing *************************
print(input[1]);
selectWindow("Log");
saveAs("Text", "["+ParentFolderPath+"/488_min]");
run("Close");

setBatchMode(false);

run("Quit");

// Daniel Ryskamp Rijsketic 6/20/21 & 12/07/21 & 7/07/22 (Heifets lab)
