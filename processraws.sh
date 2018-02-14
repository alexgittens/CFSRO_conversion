#!/usr/bin/env bash

# Takes the tarfile containing the grb2 data to be converted to ncl
# Extracts that variable and writes the netcdf file to the output directory
# Call as e.g.
#  processraws.sh /global/cscratch1/sd/gittens/large-datasets/rda_ds093.0_dataset/1979/ocnh03.gdas.19790816-19790820.tar \
#                 /global/cscratch1/sd/gittens/large-datasets/rda_ds093.0_dataset/netcdfs
# Note that the ocnh01 files have a different name for the potential temperature variable, so catch this and rename it to the
# one that the other files use

tarfile=$1
outdir=$2
tmpdir=/tmp
truevarname=POT_P8_L160_GLL0_avg1h
infrequentvarname=POT_P8_L160_GLL0_avg

module load ncl

tarfname=${tarfile##*/}
workingdir=${tmpdir}/${tarfname%.*}
mkdir -p ${workingdir}
tar -xf $tarfile -C ${workingdir}
grblist=`ls ${workingdir}/*.grb2`
for gribfile in ${grblist[*]}
do
 fname=${gribfile##*/}
 basefname=${fname%.*}
 echo $gribfile
 ncl_filedump ${gribfile} | grep $truevarname
 if [ $? -eq 1 ]; then
   ncl_convert2nc ${gribfile} -l -v ${infrequentvarname} -cl 9 -o ${workingdir}
   ncrename -v ${infrequentvarname},${truevarname} ${workingdir}/${basefname}.nc
 else
   ncl_convert2nc ${gribfile} -l -v ${truevarname} -cl 9 -o ${workingdir}
 fi
 mv -f ${workingdir}/${basefname}.nc ${workingdir}/tmp.nc
 nccopy -d1 ${workingdir}/tmp.nc ${workingdir}/${basefname}.nc
done;
rm ${workingdir}/tmp.nc
mv ${workingdir}/*.nc ${outdir}
rm -rf ${workingdir}
