# TODO:
#  use pre-allocated buffer matrices during read and write for efficiency
#
"""
Test settings:
ensure DEBUGFLAG = True
salloc -N 20 -t 60 --qos==interactive -C haswell
module load h5py-parallel mpi4py netcdf4-python python
 srun -c 3 -n 200 -u python-mpi -u ./CFSRO_converter.py 

Full run settings:
ensure DEBUGFLAG = False
salloc -N 100 -t 150 -p regular --qos=premium
module load h5py-parallel mpi4py netcdf4-python python
srun -c 3 -n 1000 -u python-mpi -u ./CFSRO_converter.py 
"""

from mpi4py import MPI
from netCDF4 import Dataset
import h5py
import numpy as np
from os import listdir
from os.path import isfile, join
import time, math, sys
import re


comm = MPI.COMM_WORLD
rank = comm.Get_rank()
mpiInfo = MPI.Info.Create()
numProcs = comm.Get_size()
procsList = np.arange(numProcs)

### Helper functions and class

def status(message, ranks=procsList):
    """prints a message for each process in the ranks argument"""

    messageToSend = "%s, process %d: %s" % (time.asctime(time.localtime()), rank, message)
    messages = comm.gather(messageToSend, root=0)
    if rank == 0:
        for (idx, messageToPrint) in enumerate(messages):
            if idx in ranks:
                print messageToPrint

def report(message):
    """print a message from the root process"""
    status(message, [0])

def reportBarrier(message):
    """synchronize all processes, then print a message from the root process"""
    comm.Barrier()
    report(message)

def chunkIdxToWriter(chunkIdx):
    """maps the chunkIdx (0...numWriters) to the rank of the process that should write it out"""
    machineNumber = (chunkIdx % numNodes)
    offsetOnMachine = chunkIdx/numNodes
    return machineNumber*numProcessesPerNode + offsetOnMachine

def extractTimeStamp(fname):
    """given name like ocnh01.gdas.1979010100.nc, returns timestamp as 1979010100"""
    m = re.search("gdas.(\d+).nc", fname)
    return fname[m.start(1):m.end(1)] 

def loadFiles(dir, varName, procInfo):
    """gets the list of all filenames in the data directory, divides them among the processes, opens them, populates some metadata"""
    fileNameList = [fname for fname in listdir(dir) if fname.endswith(".nc")]
    if (DEBUGFLAG):
        fileNameList = fileNameList[:400]
        report("DEBUGGING! LIMITING NUMBER OF FILES CONVERTED")
    report("Found %d input files, starting to open" % len(fileNameList))

    procInfo.fileNameList = [fname for (index, fname) in enumerate(fileNameList) if (index % numProcs == rank)]
    procInfo.numFiles = len(procInfo.fileNameList)
    procInfo.fileHandleList = map( lambda fname: Dataset(join(dir, fname), "r"), procInfo.fileNameList)
    procInfo.numLocalCols = np.sum(np.array([procInfo.numFiles], dtype=np.int))

    procInfo.colsPerProcess = np.empty((numProcs,), dtype=np.int)
    comm.Allgather(procInfo.numLocalCols, procInfo.colsPerProcess)
    procInfo.numCols = sum(procInfo.colsPerProcess)
    procInfo.outputColOffsets = np.hstack([[0], np.cumsum(procInfo.colsPerProcess[:-1])])
    procInfo.timeStamps = map(lambda fname: extractTimeStamp(fname), procInfo.fileNameList)

    # assumes the missing masks for observations are the same across timeslices
    procInfo.missingLocations = np.nonzero(procInfo.fileHandleList[0][varName][...].mask.flatten())[0]
    procInfo.observedLocations = np.nonzero(np.logical_not(procInfo.fileHandleList[0][varName][...].mask.flatten()))[0]
    procInfo.numRows = len(np.nonzero(np.logical_not(procInfo.fileHandleList[0][varName][...].mask.flatten()))[0])

    latList = procInfo.fileHandleList[0]["lat_0"][:]
    lonList = procInfo.fileHandleList[0]["lon_0"][:]
    lonCoordGrid, latCoordGrid = np.meshgrid(lonList, latList)
    observedLatCoords = []
    observedLonCoords = []
    observedLevelNumbers = []
    for levNum in xrange(procInfo.fileHandleList[0][varName].shape[0]):
        observedLatMask = np.logical_not(procInfo.fileHandleList[0][varName][levNum, ...].mask)
        observedLatCoords = np.concatenate([observedLatCoords, latCoordGrid[observedLatMask]])
        observedLonCoords = np.concatenate([observedLonCoords, lonCoordGrid[observedLatMask]])
        observedLevelNumbers = np.concatenate([observedLevelNumbers, [levNum]*np.count_nonzero(observedLatMask)])
    procInfo.observedLatCoords = observedLatCoords
    procInfo.observedLonCoords = observedLonCoords
    procInfo.observedLevelNumbers = observedLevelNumbers

    return fileNameList

def writeMetadata(foutName, procInfo):
    """writes metadata for the converted dataset to a numpy file"""
    timeStamps = comm.gather(procInfo.timeStamps, root=0)
    fileNames = comm.gather(procInfo.fileNameList, root=0)
    latList = procInfo.fileHandleList[0]["lat_0"][:]
    lonList = procInfo.fileHandleList[0]["lon_0"][:]
    depthList = procInfo.fileHandleList[0]["lv_DBSL0"][:]

    if rank == 0:
        np.savez(foutName, missingLocations=np.array(procInfo.missingLocations), timeStamps=timeStamps,
                fileNames=fileNames, observedLatCoords=procInfo.observedLatCoords, 
                observedLonCoords=procInfo.observedLonCoords, observedLevelNumbers=procInfo.observedLevelNumbers, 
                latList=latList, lonList=lonList, depthList=depthList,
                observedLocations=procInfo.observedLocations, numLevels=numLevels, numLats=numLats, numLongs=numLongs)

def createDataset(fnameOut, procInfo):
    propfaid = h5py.h5p.create(h5py.h5p.FILE_ACCESS)
    propfaid.set_fapl_mpio(comm, mpiInfo)
    fid = h5py.h5f.create(fnameOut, flags=h5py.h5f.ACC_TRUNC, fapl=propfaid)
    fout = h5py.File(fid)

    spaceid = h5py.h5s.create_simple((procInfo.numRows, procInfo.numCols))
    plist = h5py.h5p.create(h5py.h5p.DATASET_CREATE)
    plist.set_fill_time(h5py.h5d.FILL_TIME_NEVER)
    datasetid = h5py.h5d.create(fout.id, "rows", h5py.h5t.NATIVE_DOUBLE, spaceid, plist)
    rows = h5py.Dataset(datasetid)

    return (fout, rows)

def verifyMask(procInfo):
    """checks that the missing masks are the same for each set of observations"""
    reportBarrier("Verifying that the missing mask is the same for all observations")
    reportBarrier("... checking equality of masks on each process")
    missingLocations = set(np.nonzero(procInfo.fileHandleList[0][varname][...].mask.flatten())[0])
    for (fhIdx, fh) in enumerate(procInfo.fileHandleList):
        curMissingLocations = set(np.nonzero(fh[varname][...].mask.flatten())[0])
        if curMissingLocations != missingLocations:
            status("The missing masks do not match for some of my files")
            sys.exit()
    # would like to use reduce, but apparently this does a gather first, which would cause and issue
    # (tree reduce is NOT implemented)
    reportBarrier("... checking equality of masks across processes")
    for sender in xrange(1, numProcs):
        if rank == sender:
            comm.send(missingLocations, dest=0, tag=0)
        elif rank == 0:
            curMissingLocations = comm.recv(source=sender, tag=0)
            if curMissingLocations != missingLocations:
                status("The missing masks do not match for some of the files")
                sys.exit(1)

def chunkIt(length, num):
    """breaks xrange(length) into num roughly equally sized pieces, returns arrays of start and end indices"""
    smallChunkSize = length/num
    bigChunkSize = length/num + 1
    numBigChunks = length - (length/num)*num
    numSmallChunks = num - numBigChunks

    startIndices = [0]
    endIndices = []
    numChunks = 0
    while numChunks < numSmallChunks:
        endIndices.append(startIndices[-1] + smallChunkSize)
        startIndices.append(endIndices[-1])
        numChunks = numChunks + 1
    numChunks = 0
    while numChunks < numBigChunks:
        endIndices.append(startIndices[-1] + bigChunkSize)
        startIndices.append(endIndices[-1])
        numChunks = numChunks + 1
    startIndices = startIndices[:-1]

    return (startIndices, endIndices)

def loadLevel(procInfo, varname, numLats, numLongs, curLev):
    """loads all the observations from the files assigned to this process at level curLev, and returns as a 
    numObservationsPerTimeStepPerLevel * (numColsInMyFiles) matrix"""

    curLevMask = np.logical_not(procInfo.fileHandleList[0][varname][curLev, ...].mask.flatten())
    procInfo.numObservationsPerTimeStepPerLevel = len(np.nonzero(curLevMask)[0])
    curLevData = np.empty((procInfo.numObservationsPerTimeStepPerLevel, procInfo.numLocalCols), dtype=np.float32)
    for (fhidx, fh) in enumerate(procInfo.fileHandleList):
        observedMask = np.logical_not(fh[varname][curLev, ...].mask)
        observedValues = fh[varname][curLev, ...].data[observedMask]
        curLevData[:, fhidx] = \
                observedValues.reshape(procInfo.numObservationsPerTimeStepPerLevel)

    return curLevData

# TODO: make return chunk a global variable
def gatherDataAtWriter(curLevData, procInfo):
    """Gathers all the row chunks of a given level of observations at the writer processes"""

    chunkStartIndices, chunkEndIndices = chunkIt(procInfo.numObservationsPerTimeStepPerLevel, numWriters)
    chunkSizes = map(lambda chunkIdx: chunkEndIndices[chunkIdx] - chunkStartIndices[chunkIdx], xrange(numWriters))
    outputStartRows = np.hstack([[0], np.cumsum(chunkSizes)[:-1]])
    returnChunk = [-1]
    returnRowChunkSize = -1
    returnOutputRowOffset = -1

    for chunkIdx in xrange(numWriters):
        writerRank = chunkIdxToWriter(chunkIdx)
        curRowChunkSize = chunkSizes[chunkIdx]
        chunkToTransfer = curLevData[chunkStartIndices[chunkIdx]:chunkEndIndices[chunkIdx], :].flatten()

        processChunkSizes = curRowChunkSize*procInfo.colsPerProcess
        processChunkDisplacements = np.hstack([[0], np.cumsum(processChunkSizes[:-1])])
        collectedChunk = None
        if rank == writerRank:
            collectedChunk = np.empty((curRowChunkSize*procInfo.numCols), dtype=np.float32)
        comm.Gatherv(sendbuf=[chunkToTransfer, MPI.FLOAT], \
                     recvbuf=[collectedChunk, processChunkSizes, processChunkDisplacements, MPI.FLOAT], \
                     root=writerRank)
        if rank == writerRank:
            returnChunk = collectedChunk
            returnRowChunkSize = curRowChunkSize
            returnOutputRowOffset = outputStartRows[chunkIdx]

    #status("this chunk has %d rows and will be written starting at row %d" % \
    #            (returnRowChunkSize, returnOutputRowOffset), ranks=writersList)
    return (returnChunk, returnRowChunkSize, returnOutputRowOffset)

def writeOutputRowChunks(rowChunk, numRowsInChunk, outputRowOffset, rows, procInfo):
    """On writer processes, writes out the stored chunk of rows"""
    chunkStartIndices, chunkEndIndices = chunkIt(procInfo.numObservationsPerTimeStepPerLevel, numWriters)

    for chunkIdx in xrange(numWriters):
        if rank == chunkIdxToWriter(chunkIdx):
            assert(len(rowChunk)== numRowsInChunk*procInfo.numCols)
            processChunkSizes = numRowsInChunk*procInfo.colsPerProcess
            processChunkDisplacements = np.hstack([[0], np.cumsum(processChunkSizes[:-1])])
            chunkToWrite = np.empty((numRowsInChunk, procInfo.numCols), dtype=np.float32)

            for processNum in np.arange(numProcs):
                outputStartCol = procInfo.outputColOffsets[processNum]
                outputEndCol = outputStartCol + procInfo.colsPerProcess[processNum]
                startChunkOffset = processChunkDisplacements[processNum]
                endChunkOffset = startChunkOffset + numRowsInChunk*procInfo.colsPerProcess[processNum]
                chunkToWrite[:, outputStartCol:outputEndCol] = np.reshape(rowChunk[startChunkOffset:endChunkOffset], \
                        (numRowsInChunk, procInfo.colsPerProcess[processNum]))

            startOutputRow = outputRowOffset
            endOutputRow = outputRowOffset + numRowsInChunk
            rows[startOutputRow:endOutputRow, :] = chunkToWrite

class ProcessInformation(object):
    def __init__(self):
        pass

# Variables that should really be command-line settings
#DEBUGFLAG = True
#numNodes = 20
#numProcessesPerNode = 10
#numWriters = 20
DEBUGFLAG = False
numNodes = 100 # number of physical nodes
numProcessesPerNode = 10
numWriters = 60 # a good choice is one per physical node (probably up to the number of OSTs used)

basePath = "/global/cscratch1/sd/gittens/large-datasets/rda_ds093.0_dataset"
dataInPath = basePath + "/netcdfs" 
dataOutFname = basePath + "/outputs/ocean2T.h5" 
varname = "POT_P8_L160_GLL0_avg"
metadataFnameOut = basePath + "/outputs/ocean2Tmetadata.npz" 

numLevels = 40
numLats = 360
numLongs = 720

### Setup the processes for reading and writing

report("Using %d processes" % numProcs)
report("Writing variable %s " % varname)
procInfo = ProcessInformation()
fileNameList = loadFiles(dataInPath, varname, procInfo)
writeMetadata(metadataFnameOut, procInfo)

report("Writer ranks : " + " ".join(map(lambda idx: str(chunkIdxToWriter(idx)), xrange(numWriters))))
reportBarrier("Creating output file and dataset")
fout, rows = createDataset(dataOutFname, procInfo)
reportBarrier("Finished creating output file and dataset")

### Write the data to the output file
reportBarrier("Writing %s to file" % varname)

chunkToWrite = None
levelStartRow = 0
writersList = map(chunkIdxToWriter, xrange(numWriters))
for curLev in xrange(numLevels):
    reportBarrier("Loading data for level %d/%d" % (curLev + 1, numLevels))
    curLevData = loadLevel(procInfo, varname, numLats, numLongs, curLev)
    reportBarrier("Done loading data for this level")
    reportBarrier("There are %d observed grid points on this level" % procInfo.numObservationsPerTimeStepPerLevel)

    reportBarrier("Gathering data for this level from processes to writers")
    (curOutputRowChunk, curNumOutputRows, curOutputRowOffset) = gatherDataAtWriter(curLevData, procInfo)
    reportBarrier("Done gathering")

    reportBarrier("Writing data for this level on writers")
    writeOutputRowChunks(curOutputRowChunk, curNumOutputRows, levelStartRow + curOutputRowOffset, rows, procInfo)
    levelStartRow = levelStartRow + procInfo.numObservationsPerTimeStepPerLevel

reportBarrier("Done writing")

# close the open files
map(lambda fh: fh.close(), procInfo.fileHandleList)
fout.close()
