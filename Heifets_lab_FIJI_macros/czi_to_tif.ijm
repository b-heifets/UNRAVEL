// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023

setBatchMode(true); //comment this out to make images visible during macro execution

inputlist = getArgument();
input = split(inputlist,'#');

//************* Open 3D .czi image **************************************************
run("Bio-Formats Importer", "open="+input[0]+" color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT");
dir=getDirectory("image");
sample=File.getName(dir);

getDimensions(width, height, channels, slices, frames)

if (input[2]=="SizeX_odd") {
  width=width-1;
} 

if (input[3]=="SizeY_odd") {
  height=height-1;
}

makeRectangle(0, 0, width, height);
run("Crop");

run("Split Channels");
////run("Image Sequence... ", "format=TIFF name="+sample+"_Ch2_ save="+dir+"/ochann/"+sample+"_Ch2_0000.tif"); //Old line before Fiji update
run("Image Sequence... ", "dir="+dir+"/ochann/ format=TIFF name="+sample+"_Ch2");
close();

if (input[1]=="0") {
  //save full res 488 tif series
////run("Image Sequence... ", "format=TIFF name="+sample+"_Ch1_ save="+dir+"/488/"+sample+"_Ch1_0000.tif"); //Old line before Fiji update
  run("Image Sequence... ", "dir="+dir+"/488/ format=TIFF name="+sample+"_Ch1");
}  else {
  //save full res 488 tif series 
////run("Image Sequence... ", "format=TIFF name="+sample+"_Ch1_ save="+dir+"/488_original/"+sample+"_Ch1_0000.tif"); //Old line before Fiji update
  run("Image Sequence... ", "dir="+dir+"/488_original/ format=TIFF name="+sample+"_Ch1");

  //************ Adjust display range *********************************************
  setMinAndMax(input[1], 65535); //input[1] = 488 "threshold" passed from 488thr.sh
  run("Apply LUT", "stack");
////run("Image Sequence... ", "format=TIFF name="+sample+"_Ch1_ save="+dir+"/488/"+sample+"_Ch1_0000.tif"); //Old line before Fiji update
  run("Image Sequence... ", "dir="+dir+"/488/ format=TIFF name="+sample+"_Ch1");

  //************ Save 488_min to log it *******************************************
  print(input[1]);
  selectWindow("Log");
  saveAs("Text", "["+dir+"/parameters/488_min]");
}

setBatchMode(false);

run("Quit");

//Daniel Ryskamp Rijsketic 06/20/21 & 06/08/22 & 07/07/22 (Heifets lab)
