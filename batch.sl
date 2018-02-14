#!/bin/sh
#SBATCH -N 6 -c 64
#SBATCH -p debug
#SBATCH -t 00:25:00
#SBATCH -C haswell 
cd $SCRATCH/large-datasets/rda_ds093.0_dataset
export PATH=$PATH:/usr/common/tig/taskfarmer/1.5/bin:$(pwd)
export THREADS=32
runcommands.sh tasks.txt
