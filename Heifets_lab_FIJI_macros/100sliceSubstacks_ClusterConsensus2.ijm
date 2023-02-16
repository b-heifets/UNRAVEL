// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023
// 100sliceSubstacks (Daniel Rijsketic May 6, 2022; Heifets lab)
//===================================================

setBatchMode(true);

inputlist = getArgument();
input = split(inputlist,'#');

//open cropped consensus ////////////////////////////////////////
open(input[0]); 
dir = input[1];
ClusterConsensus=getTitle();

//Add padding to avoid excluding cells touching edges of stack
X=getWidth();
Y=getHeight();
X_padded=X+2
Y_padded=Y+2

//Add 1 pixel of padding around xy borders
run("Canvas Size...", "width="+X_padded+" height="+Y_padded+" position=Center");
setSlice(nSlices);
run("Add Slice");

//Add empty slice to  of padding around z borders
run("Duplicate...", " ");
run("Select All");
run("Clear");
rename("Empty slice");
run("Concatenate...", "keep open image1=[Empty slice] image2=["+ClusterConsensus+"]");
close("Empty slice");
padded_ClusterConsensus = getTitle();
close(ClusterConsensus);

//Save as substacks (with 1 pixel overlap for alternating between exclude pixels on edges and include pixels on egdes during the 3D object counting on GPU)

//102e 100i (aka 100 slices)
NumberOfSubstacks=-floor(-nSlices/200); //rounds up 
for (i = 1; i < NumberOfSubstacks + 1; i++) {
	a = (200*i-199); //1-102 	   201-302
	b = (a+101);
	run("Duplicate...", "duplicate range="+a+"-"+b);
	//saveAs("Tiff", dir+"/"+consensus+"_"+a+"_"+b+"_ExcludeEdges");
        run("NIfTI-1", "save="+dir+"/"+ClusterConsensus+"_"+a+"_"+b+"_ExcludeEdges.nii");
	close();
};
NumberOfSubstacks=round(nSlices/200);
for (i = 1; i < NumberOfSubstacks + 1; i++) {
	a = (200*i-199);
	b = (a+101);
	c = b+99;            //102-201    302-401
	run("Duplicate...", "duplicate range="+b+"-"+c);
	//saveAs("Tiff", dir+"/"+consensus+"_"+b+"_"+c+"_IncludeEdges");
        run("NIfTI-1", "save="+dir+"/"+ClusterConsensus+"_"+b+"_"+c+"_IncludeEdges.nii");
	close();
};
close();

setBatchMode(false);

run("Quit");


