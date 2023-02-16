// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023
// consensus_part1 (Daniel Rijsketic Jan. 17, 2022; Heifets lab)
//===================================================

//Inputs: 1) seg_ilastik_XX/IlastikSegmentation_XX/<1st_tif> for 5 raters 
//Outputs: sampleX/consensus/consensus.tif

//setBatchMode(true); 

filelist = getArgument();
file = split(filelist,'#');

//Convert background (label 2 in intensity from 2 to 0)
function binarize() {
run("Out [-]");
run("Out [-]");
setThreshold(2, 2);
for (i = 1; i <= nSlices; i++) { 
setSlice(i); 
run("Create Selection"); 
run("Set...", "value=0");
run("Select None");
} 
resetThreshold;
}

//************ Open seg_ilastik_XX/IlastikSegmentation_XX/<1st_tif> *******************************************
for (i=0; i<2; i++) {
run("Image Sequence...", "open=["+file[i]+"] sort"); // select first segmentation tif in series
rater=i+1;
rename("seg_ilastik_"+rater+".tif");
binarize();
}

Dir = getDirectory("image"); 
Parent_Dir=File.getParent(Dir);
Sample_Dir=File.getParent(Parent_Dir);
consensusDir= Sample_Dir + "/consensus/";

imageCalculator("Add create stack", "seg_ilastik_1.tif","seg_ilastik_2.tif");

saveAs("Tiff", consensusDir+"Result_of_seg_ilastik_1.tif");

setBatchMode(false);

run("Quit");

