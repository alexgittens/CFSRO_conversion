Pipeline for converting NCEP Climate Forecast System Reanalysis (CFSR) 6-hourly Ocean Potential Temperature Dataset from January 1979 to December 2010 into
a large matrix in HDF5 format. Meant to be run on NERSC's Cori system

Steps:
1. retrieve all the ocnh\* files from the ds093.0 dataset (https://rda.ucar.edu/datasets/ds093.0/)
2. convert these files to netcdf format using TaskFarmer (https://www.nersc.gov/users/data-analytics/workflow-tools/taskfarmer/)
3. run the MPI-Py conversion script to read in those files and write out the matrix and associate metadata needed to go back from the matrix to the original dataset

To save on disk space (the raw datafiles from RDA contain many variables, so the total comes out to be around 11 TB, which I can't download all at once), I downloaded
the dataset in chunks of about 1.5TB at a time, and used TaskFarmer on those as described here, then repeated the process until all the files were processed:
- download the current set of files into a directory
- edit generate\_task\_list.sh as needed to point to the data and output directory
- run generate\_task\_list.sh
- edit batch.sl as needed
- module load taskfarmer
- sbatch batch.sl
- verify that done.tasks.txt.fin is present, which mean all the tasks have been completed
- remove the progress and done files before running the next batch 



