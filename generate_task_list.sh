#!/usr/bin/env bash

rawsdir=$SCRATCH/large-datasets/rda_ds093.0_dataset/raws
netcdfdir=$SCRATCH/large-datasets/rda_ds093.0_dataset/netcdfs

tarlist=`ls ${rawsdir}/*/*.tar`
for tarfile in ${tarlist[*]};
do
  echo "processraws.sh ${tarfile} ${netcdfdir}" >> tasks.txt
done;

