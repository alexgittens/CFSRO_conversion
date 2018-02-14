#!/usr/bin/env bash
# CAVEAT: make sure you don't have the netcdf module loaded! it makes nccopy not able to write compressed NetCDF files
# Takes the tarfile containing the grb2 data to be converted to ncl
# Extracts that variable and writes the netcdf file to the output directory
# Note that is only intended for use with the ocnh01 files (the others contain forecasts, this contains averages!)
# Call as e.g.
#  processraws.sh /global/cscratch1/sd/gittens/large-datasets/rda_ds093.0_dataset/1979/ocnh01.gdas.19790816-19790820.tar \
#                 /global/cscratch1/sd/gittens/large-datasets/rda_ds093.0_dataset/netcdfs

tarfile=$1
outdir=$2
tmpdir=/tmp
varlist=POT_P8_L160_GLL0_avg,lat_0,lon_0,lv_DBSL0

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
 ncl_convert2nc ${gribfile} -l -v ${varlist} -cl 9 -o ${workingdir}
 mv -f ${workingdir}/${basefname}.nc ${workingdir}/tmp.nc
 nccopy -d1 ${workingdir}/tmp.nc ${workingdir}/${basefname}.nc
done;
rm ${workingdir}/tmp.nc
mv ${workingdir}/*.nc ${outdir}
rm -rf ${workingdir}
