// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023
//FIRST determine threshold for 488 mask

//run via ABA_histo_in_tissue_full_res.sh

setBatchMode(true);
inputlist = getArgument();
input = split(inputlist,'#');

open(input[0]); //2xDS_ABA.tif
ABA=getTitle();

//Make mask based on tissue (488 autofl)
open(input[1]); //2xDS_488.tif
run("Image Sequence...", "open=["+input[1]+"] sort"); // path/1st_tif
autofl=getTitle();
dir=getDirectory("image");
ParentFolderPath=File.getParent(dir);
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
//run("NIfTI-1", "save="+ParentFolderPath+"/reg_final/"+sample+"_native_gubra_ano_split_in_tissue.nii");

setBatchMode(false);


CSVdir= dirABA + "/ABA_histogram_of_pixel_intensity_counts_in_tissue/";
nBins = 65535;
hMin = 0;
hMax = 65535;
row=0;
run("Clear Results");
for (slice=1; slice<=nSlices; slice++) {
	if (nSlices>1) run("Set Slice...", "slice=" + slice);
 	getHistogram(values,counts,nBins,hMin,hMax);
 	          for (i=0; i<nBins; i++) {
              if (nSlices>1) setResult("Slice", row, slice);
              setResult("Value", row, values[i]);
              setResult("Count", row, counts[i]);
              row++;
          }
};
updateResults(); 
saveAs("Results", CSVdir+"ABA_histogram_in_tissue.csv");


run("Quit");

//Daniel Ryskamp Rijsketic 6/20/21 & 09/29/22 (Heifets lab)
