# flood-mapper

Within this script SAR Sentinel-1 is being used to generate a flood extent map. A change detection 
approach was chosen, where a before- and after-flood event image will be compared. Sentinel-1 GRD 
imagery is being used. Ground Range Detected imagery includes the following preprocessing steps: 
Thermal-Noise Removal, Radiometric calibration, Terrain-correction hence only a Speckle filter needs 
to be applied in the preprocessing.  

URL: https://un-spider.org/advisory-support/recommended-practices/recommended-practice-google-earth-engine-flood-mapping/step-by-step#Step%202:%20Time%20frame%20and%20sensor%20parameters%20selection

