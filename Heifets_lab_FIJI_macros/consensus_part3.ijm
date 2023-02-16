// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023
// consensus_part3 (Daniel Rijsketic Jan. 17, 2022; Heifets lab)
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
run("Image Sequence...", "open=["+file[0]+"] sort"); // select first segmentation tif in series
rename("seg_ilastik_4.tif");
binarize();

Dir = getDirectory("image"); 
Parent_Dir=File.getParent(Dir);
Sample_Dir=File.getParent(Parent_Dir);
consensusDir= Sample_Dir + "/consensus/";

open(consensusDir+"Result_of_seg_ilastik_3.tif");
imageCalculator("Add create stack", "seg_ilastik_4.tif","Result_of_seg_ilastik_3.tif");

saveAs("Tiff", consensusDir+"Result_of_seg_ilastik_4.tif");

setBatchMode(false);

run("Quit");
