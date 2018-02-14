#!/bin/sh
#SBATCH -N 100 
#SBATCH -p regular
#SBATCH -t 01:30:00
#SBATCH -C haswell 

module unload darshan
module load h5py-parallel 
module load python
srun -c 3 -n 1000 -u python -u ./CFSRO_converter.py

