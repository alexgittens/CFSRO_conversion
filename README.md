Pipeline for converting NCEP Climate Forecast System Reanalysis (CFSR) 6-hourly Ocean Potential Temperature Dataset from January 1979 to December 2010 into
a large matrix in HDF5 format. Meant to be run on NERSC's Cori system.

Steps:
1. retrieve all the ocnh01.\* files from the ds093.0 dataset (https://rda.ucar.edu/datasets/ds093.0/) -- I used Globus to transfer the files in around 5 chunks of 500 (since
the interface shows 500 files at a time). You can submit multiple Globus transfers at once; I did 2 at a time to not use too much space on Cori
2. convert these files to netcdf format using TaskFarmer (detailed below) (https://www.nersc.gov/users/data-analytics/workflow-tools/taskfarmer/)
3. run the MPI-Py conversion script to read in those files and write out the matrix and associate metadata needed to go back from the matrix to the original dataset (detailed below)

To save on disk space (the raw datafiles from RDA contain many variables, so the total comes out to be around 11 TB, which I can't download all at once), I downloaded
the dataset in chunks, and used TaskFarmer on those as described here, then repeated the process until all the files were processed:
- download the current set of files into a directory
- edit generate\_task\_list.sh as needed to point to the data and output directory
- run generate\_task\_list.sh
- edit batch.sl as needed
- module load taskfarmer
- sbatch batch.sl
- verify that done.tasks.txt.fin is present, which mean all the tasks have been completed
- remove the progress and done files before running the next batch 

To convert the netcdf files to a large HDF5 matrix and the associated metadata:
-mkdir outputs
-lfs setstripe --size 72 outputs (see http://www.nersc.gov/users/storage-and-file-systems/i-o-resources-for-scientific-applications/optimizing-io-performance-for-lustre/ for why)
-edit the CFSRO\_converter.py script to change the basePath
-sbatch doconversion.sl

TODO:
-test the metadata output
