//FIRST determine threshold for 488 mask

//run via ABA_histo_in_tissue_full_res.sh

setBatchMode(true);
inputlist = getArgument();
input = split(inputlist,'#');

open(input[0]); //Full res ABA
ABA=getTitle();
dir = getDirectory("image");

//Make mask based on tissue (488 autofl)
run("Image Sequence...", "open=["+input[1]+"] sort"); // path/1st_tif
autofl=getTitle();
autoflDir=getDirectory("image");
ParentFolderPath=File.getParent(autoflDir);
sample=File.getName(ParentFolderPath);
setThreshold(input[2], 65535); 
print(input[2]);
selectWindow("Log");
saveAs("Text", "["+ParentFolderPath+"/Thres_for_volume_in_tissue]");
run("Close");
run("Convert to Mask", "method=Default background=Dark black");

//Remove ABA labels outside of tissue
imageCalculator("Divide create 32-bit stack", autofl, autofl);
autofl_mask_divided=getTitle();
imageCalculator("Multiply create 32-bit stack", autofl_mask_divided, ABA);
ABA_in_tissue=getTitle();
selectWindow(autofl);
close();
selectWindow(autofl_mask_divided);
close(); 
selectWindow(ABA);
close(); 
selectWindow(ABA_in_tissue); 
setOption("ScaleConversions", false);
run("16-bit"); //For ABA within tissue, only run to this point and //BatchMode
run("NIfTI-1", "save="+dir+sample+"_native_gubra_ano_split_in_tissue.nii");

setBatchMode(false);
run("Quit");

//Daniel Ryskamp Rijsketic 6/20/21, 09/29/22, & 09/20/23 (Heifets lab)
