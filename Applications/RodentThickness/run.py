#!@pathexecpython@

'''
This python script accepts .csv data set, .bms configurations, and output directory then produces statistical analysis results from the processed data
'''


from optparse import OptionParser
import csv
import os,os.path,re,sys
import system


def countLines(files):
    lines = []
    for file in files:
        fin = open(file)
        lines.append(len(fin.readlines()))
        fin.close()
    return lines

def readAllFiles(files):
    lines = []
    for file in files:
        fin = open(file)
        lines.append(fin.readlines())
        fin.close()
    return lines

def file2string(f):
    fin = open(f)
    lines = fin.readlines()
    lines = map(lambda x: x.strip(), lines)
    return lines


def find_executables(exes):
    for exe in exes:
        if system.find_program(exe) is None:
            raise RuntimeError("can't find %s in PATH variable" % exe)


def check_directories(output_dir):
    dirs = ["{output_dir}/Processing/1.MeasurementandSPHARM",
            "{output_dir}/Processing/2.shapeworks",
            "{output_dir}/Processing/3.sampling",
            "{output_dir}/Statistics"]

    for dir in dirs:
        dir = dir.format(output_dir=output_dir)
        if not os.path.isdir(dir):
            os.makedirs(dir)


def initialize_programs(opts):
    programs_list = ["ResampleVolume2", "kmesh", "ImageMath", \
              "MeshPointsIntensitySampling", "SegPostProcessCLP", \
              "measureThicknessFilter", "ParaToSPHARMMeshCLP", "GenParaMeshCLP", \
              "Rscript", "BinaryToDistanceMap", "kcalc", \
              "ShapeWorksRun", "ShapeWorksGroom"]

    import sys
    newpath = os.path.realpath(sys.path[0] + "/../Rscript-build/bin")\
            +((":"+opts.dirs) if opts.dirs else "")
    return system.configure_paths(newpath, programs_list, opts.verbose)
   

def initalize_dataset(csvfile):
    csvreader = csv.reader(open(csvfile, "r"))
    csvheader = csvreader.next()

    csvdata = []
    for csvline in csvreader:
        csvdata.append(csvline)
    return csvdata


def initialize_system_logging(opts):
    # set up the logger for external programs
    if opts.check_commands:
        logformat = "%(message)s"
    else:
        logformat = "%(levelname)s %(asctime)s %(message)s"

    if opts.logfileName is not None:
        system.rename_logfile(opts.logfileName)
        system.setup_logger(logfilename=opts.logfileName, logformat=logformat)
    else:
        system.setup_logger(logformat=logformat)

    if (opts.check_commands):
        system.set_check_commands(True)



def concatColumnsToFile(input, output, inputIsList=False):
    if (inputIsList):
        args = input
    else:
        if (input != ""):
            args = file2string(input)
        else:
            return
    lines = countLines(args)
    if (len(lines) == 0):
        print "Empty files"
        return
    if (min(lines) != max(lines)):
        print "Some of input files have different line numbers: ", lines
        return
    lineStrings = readAllFiles(args)
    if (output != ""):
        fout = open(output, "w")
    else:
        fout = sys.stdout
    for i in range(0,lines[0]):
        tempOutputLine = [ x[i].strip() for x in lineStrings]
        outputLineString = "\t".join(tempOutputLine)
        fout.write(outputLineString)
        fout.write("\n")
    fout.close()

'''
execute MeshPointsIntensitySampling
'''
def sample_thickness(opts,config,csvdata,outputDir,corr_opt):
    meshDir = "{outputDir}/Processing/1.MeasurementandSPHARM".format(**locals())
    shapeworksDir = "{outputDir}/Processing/2.shapeworks".format(**locals())
    sampleDir = "{outputDir}/Processing/3.sampling".format(**locals())
    statDir = "{outputDir}/Statistics".format(**locals())
    pathKmesh = config["kmeshPath"]

    if (corr_opt == "initial_dense"):
        extra_args = "--inputPointFlip"
    else:
        extra_args = ""

    # depending on options, choose different meshes
    # loop over ids
    for id in [i for i,l,g in csvdata]:
        distanceVector = "{sampleDir}/{id}.distanceVector.nrrd".format(**locals())
        inputMeasurement = "{meshDir}/{id}_measurementoutput.nrrd".format(**locals())
        #    inputMeasurement = "%s/%s.thickness.mha" % (meshDir, id)
        if (corr_opt == "initial_dense"):
            samplingTxt = "%s/%s.initialDenseSampling.txt" % (sampleDir, id)
            smoothSamplingTxt = "%s/%s.smoothInitialDenseSampling.txt" % (sampleDir, id)
            samplingMeshOutput = "%s/%s.initialDenseSampling.vtk" % (sampleDir, id)
            originalMeshOutput = "%s/%s.initialDenseOriginal.vtk" % (sampleDir, id)
            inputMesh = "%s/%s.subj.SPHARM.vtk" % (meshDir, id)
        elif (corr_opt == "correspondence"):
            samplingTxt = "%s/%s.sampling.txt" % (sampleDir, id)
            smoothSamplingTxt = "%s/%s.smoothSampling.txt" % (sampleDir, id)
            samplingMeshOutput = "%s/%s.sampling.vtk" % (sampleDir, id)
            originalMeshOutput = "%s/%s.original.vtk" % (sampleDir, id)
            inputMesh = "%s/%s.correspondence.vtk" % (shapeworksDir, id)
        elif (corr_opt == "dense_correspondence"):
            samplingTxt = "%s/%s.denseSampling.txt" % (sampleDir, id)
            smoothSamplingTxt = "%s/%s.smoothDenseSampling.txt" % (sampleDir, id)
            samplingMeshOutput = "%s/%s.denseSampling.vtk" % (sampleDir, id)
            originalMeshOutput = "%s/%s.denseOriginal.vtk" % (sampleDir, id)
            inputMesh = "%s/%s.dense_correspondence.vtk" % (shapeworksDir, id)
        elif (corr_opt == "spharm_sampling"):
            samplingTxt = "%s/%s.spharmSampling.txt" % (sampleDir, id)
            smoothSamplingTxt = "%s/%s.smoothSpharmSampling.txt" % (sampleDir, id)
            samplingMeshOutput = "%s/%s.spharmSampling.vtk" % (sampleDir, id)
            originalMeshOutput = "%s/%s.spharmOriginal.vtk" % (sampleDir, id)
            inputMesh = "%s/%s.subj.SPHARM.vtk" % (meshDir, id)


        #samplingCmd = "{MeshPointIntensitySamplingPath} --workDir {workdir} --inputAsPhysicalCoord {extra_args} --distanceVector {distanceVector} -i nn -a {samplingTxt} -m {samplingMeshOutput} --smoothedAttributeOutput {smoothSamplingTxt} --originalMeshOutput {originalMeshOutput} {inputMeasurement} {inputMesh}"
        #exeCmd = samplingCmd.format(**locals())
        # exeCmd = samplingCmd % (outputDir, distanceVector, samplingTxt, samplingMeshOutput, smoothSamplingTxt, originalMeshOutput, inputMeasurement, inputMesh)
        #system.run_process(exeCmd,verbose=True)

        if system.is_file_newer(smoothSamplingTxt, inputMeasurement, opts.overwrite) or \
                system.is_file_newer(smoothSamplingTxt, samplingTxt, opts.overwrite) or \
                system.is_file_newer(smoothSamplingTxt, samplingMeshOutput, opts.overwrite):
            useStreamLine = corr_opt == "spharm_sampling"
            if (not useStreamLine):
                exeCmd = "{pathKmesh} -sampleImage {inputMeasurement} {inputMesh} {samplingMeshOutput} " +\
                            "-outputScalarName Thickness -zrotate"
                exeCmd = exeCmd.format(**locals())
                system.run_process(exeCmd,verbose=True)

                exeCmd = "{pathKmesh} -smoothScalars {samplingMeshOutput} {samplingMeshOutput} " +\
                            "-scalarName Thickness -outputScalarName smoothThickness -iter 3"
                exeCmd = exeCmd.format(**locals())
                system.run_process(exeCmd,verbose=True)

                exeCmd = "{pathKmesh} -exportScalars {samplingMeshOutput} {samplingTxt} -scalarName Thickness"
                exeCmd = exeCmd.format(**locals())
                system.run_process(exeCmd,verbose=True)

                exeCmd = "{pathKmesh} -exportScalars {samplingMeshOutput} {smoothSamplingTxt} " +\
                            "-scalarName smoothThickness "
                exeCmd = exeCmd.format(**locals())
                system.run_process(exeCmd,verbose=True)
            else:
                gradientFile = "{outputDir}/Processing/1.MeasurementandSPHARM/" +\
                        "{id}/laplacianGradient.nrrd".format(**locals())
                gradientVTIFile = "{outputDir}/Processing/1.MeasurementandSPHARM/" +\
                        "{id}/laplacianGradient.vti".format(**locals())
                streamLineFile = "{outputDir}/Processing/1.MeasurementandSPHARM/" +\
                        "{id}/stream_lines.vtp".format(**locals())

                # vti image creation
                exeCmd = "{pathKmesh} -vti {gradientFile} {gradientVTIFile} -attrDim 3"
                exeCmd = exeCmd.format(**locals())
                system.run_process(exeCmd,verbose=True)

                # RK45 integration
                exeCmd = "{pathKmesh} -zrotate -traceDirection backward -traceStream " +\
                    "{gradientVTIFile} {inputMesh} {streamLineFile} {samplingMeshOutput}"
                exeCmd = exeCmd.format(**locals())
                system.run_process(exeCmd,verbose=True)

                # scalar export
                exeCmd = "{pathKmesh} -scalarName Length -exportScalars " +\
                    "{samplingMeshOutput} {smoothSamplingTxt}"
                exeCmd = exeCmd.format(**locals())
                system.run_process(exeCmd,verbose=True)




def perform_analysis(opts, config, csvdata, outputDir, corr_opt="initial_dense"):
    ids = [i for i,l,g in csvdata]
    groups = [g for i,l,g in csvdata]

    meshDir = "{outputDir}/Processing/1.MeasurementandSPHARM".format(**locals())
    shapeworksDir = "{outputDir}/Processing/2.shapeworks".format(**locals())
    sampleDir = "{outputDir}/Processing/3.sampling".format(**locals())
    statDir = "{outputDir}/Statistics".format(**locals())

    sample_thickness(opts,config,csvdata,outputDir,corr_opt)

    # collect_attributes()
    # compute_statistics()
    # aggregate sampling files into a single file
    groupSet = set(groups)
    datafiles = []
    tag = ""
    for group in groupSet:
        # setup output filename template
        if (corr_opt == "initial_dense"):
            tag = "_initialDenseSampling"
            datafilename = "%s/data_initialDenseSampling_%s.txt" % (statDir, group)
            dataregionfilename = "%s/data_region_initialDenseSampling_%s.txt" % (statDir, group)
            outfilename = "%s/list_initialDenseSampling_%s.txt" % (statDir, group)
        elif (corr_opt == "correspondence"):
            tag = ""
            datafilename = "%s/data_%s.txt" % (statDir, group)
            dataregionfilename = "%s/data_region_%s.txt" % (statDir, group)
            outfilename = "%s/list_%s.txt" % (statDir, group)
        elif (corr_opt == "dense_correspondence"):
            tag = "_dense"
            datafilename = "%s/data_dense_%s.txt" % (statDir, group)
            dataregionfilename = "%s/data_region_dense_%s.txt" % (statDir, group)
            outfilename = "%s/list_dense_%s.txt" % (statDir, group)
        elif (corr_opt == "spharm_sampling"):
            tag = "_spharm"
            datafilename = "%s/data_spharm_%s.txt" % (statDir, group)
            dataregionfilename = "%s/data_region_spharm_%s.txt" % (statDir, group)
            outfilename = "%s/list_spharm_%s.txt" % (statDir, group)


        # process and write the aggregated data
        outfile = open(outfilename, 'w')
        for (id, g) in zip(ids, groups):
            if (g != group):
                continue
            if (corr_opt == "initial_dense"):
                samplingTxt = "%s/%s.smoothInitialDenseSampling.txt" % (sampleDir, id)
            elif (corr_opt == "correspondence"):
                samplingTxt = "%s/%s.smoothSampling.txt" % (sampleDir, id)
            elif (corr_opt == "dense_correspondence"):
                samplingTxt = "%s/%s.smoothDenseSampling.txt" % (sampleDir, id)
            elif (corr_opt == "spharm_sampling"):
                samplingTxt = "%s/%s.smoothSpharmSampling.txt" % (sampleDir, id)
            if (os.path.isfile(samplingTxt)):
                outfile.write(samplingTxt)
                outfile.write("\n")
            else:
                print "can't find", samplingTxt
        outfile.close()

        # concatenate those attribute files into a file
        concatColumnsToFile(outfilename, datafilename)
        datafiles.append((group, datafilename))

    # perform statistical analysis
    rscriptExePath = config["RscriptPath"]
    rscriptPath = os.path.dirname(os.path.abspath(__file__)) + "/rodentThicknessStats.r"
    if (corr_opt == "initial_dense"):
        outputfile = "%s/stats.initialDenseSampling.txt" % statDir
        outputVTK = "%s/stats.initialDenseSampling.vtk" % (statDir)
        inputVTK = "%s/%s.subj.SPHARM.vtk" % (meshDir, ids[0])
    elif (corr_opt == "correspondence"):
        outputfile = "%s/stats.correspondence.txt" % statDir
        outputVTK = "%s/stats.correspondence.vtk" % (statDir)
        inputVTK = "%s/%s.correspondence.vtk" % (shapeworksDir, ids[0])
    elif (corr_opt == "dense_correspondence"):
        outputfile = "%s/stats.denseCorrespondence.txt" % statDir
        outputVTK = "%s/stats.denseCorrespondence.vtk" % (statDir)
        inputVTK = "%s/%s.dense_correspondence.vtk" % (shapeworksDir, ids[0])
    elif (corr_opt == "spharm_sampling"):
        outputfile = "%s/stats.spharmCorrespondence.txt" % statDir
        outputVTK = "%s/stats.spharmCorrespondence.vtk" % (statDir)
        inputVTK = "%s/%s.subj.SPHARM.vtk" % (meshDir, ids[0])

    #pythonScriptPath = config["vtkPointAttributesPythonScriptPath"]

    pathKmesh = config["kmeshPath"]
    datafilelist = ""
    datagroups = ""
    for (group, file) in datafiles:
        datafilelist = datafilelist + " " + file
        datagroups = datagroups + " " + group

        # compute per-group statistics
        cmd = "%s -computeVectorStats -scalarName %s -importVectors %s %s %s/%s_thickness.vtk" % (pathKmesh, group + "_Thickness", inputVTK, file, statDir, group)
        system.run_process(cmd,verbose=True)


    if (len(datafiles) > 1):
        runCmd = "%s %s %s %s %s" % (rscriptExePath, rscriptPath, datafilelist, outputfile, datagroups)
        system.run_process(runCmd,verbose=True)
        #visCmd = "%s %s %s %s -i %s -t" % (pythonPath, pythonScriptPath, inputVTK, outputVTK, outputfile)
        visCmd = "%s -use-header %s %s -importCSV %s" % (pathKmesh, inputVTK, outputVTK, outputfile)
        system.run_process(visCmd,verbose=True)

        # connected components for p-value
        print "computing connected components with t.pvalue..."
        runCmd = "%s -connectScalars %s -scalarName t.pvalue %s -thresholdMin 0 -thresholdMax 0.05" % (pathKmesh, outputVTK, outputVTK)
        system.run_process(runCmd,verbose=True)

        print "export scalars..."
        runCmd = "%s -exportScalars -scalarName RegionIds %s %s/regionIds.txt" % (pathKmesh, outputVTK, statDir)
        system.run_process(runCmd,verbose=True)

        # create a combined data file with regions
        regionIdFile = "%s/regionIds.txt" % (statDir)
        if os.path.exists(regionIdFile):
            for (group, file) in datafiles:
                dataregionfilename = "%s/data_region%s_%s.txt" % (statDir, tag, group)
                concatColumnsToFile([regionIdFile, "%s/data%s_%s.txt" % (statDir, tag, group)], dataregionfilename, inputIsList = True)
                # perform splitting
                performSplit([dataregionfilename], "%s/data_%s_region_" % (statDir, group) + "%02d.txt")

            # boxplot
            draw_boxplot = True
            if draw_boxplot:
                groupList = list(groupSet)
                try:
                    print sys.path
                    import boxplot
                    gr1 = groupList[0]
                    gr2 = groupList[1]
                    boxplot.draw_boxplot(groupList[0], groupList[1], \
                        "{statDir}/data_{gr1}_region_*.txt".format(**locals()), \
                        "{statDir}/data_{gr2}_region_*.txt".format(**locals()), \
                        "{statDir}/{gr1}_{gr2}_regions.pdf".format(**locals()))
                except BaseException as e:
                    print system.bcolors.WARNING + e.message + system.bcolors.ENDC
                    pass





'''
Label map processing for thickness measurement
def labelprocessing(config, csvdata, outputdir, labelNCleft, labelNCright, labelOB):
  workdir = "%s/Processing/1.MeasurementandSPHARM"
  for (id, labelmap, group):
    brain_nc_left = "%s/%s_brain_left.nrrd" % (workdir, id)
    brain_nc_left = "%s/%s_brain_left.nrrd" % (workdir, id)
    brain_nc_left = "%s/%s_brain_left.nrrd" % (workdir, id)
    brain_nc_left = "%s/%s_brain_left.nrrd" % (workdir, id)
    brain_nc_left = "%s/%s_brain_left.nrrd" % (workdir, id)
'''

# run thickness measurement
# if the measurement file exists, skip it
def compute_thickness(opts, config, data, outputdir, ids, idl, idh, idn):
    pathThicknessTool = config["measureThicknessFilterPath"]
    for (id, labelmap, group) in data:
        labelmap = "{outputdir}/Processing/1.MeasurementandSPHARM/{id}.boundaryMap.mha".format(**locals())
        # temporary
        #    workdir = "%s/Processing/1.MeasurementandSPHARM/%s_2" % (outputdir, id)
        #    measurementoutput = "%s/Processing/1.MeasurementandSPHARM/%s.thickness.mha" % (outputdir, id)

        workdir = "{outputdir}/Processing/1.MeasurementandSPHARM/{id}".format(**locals())
        measurementoutput = "{outputdir}/Processing/1.MeasurementandSPHARM/" +\
                        "{id}_measurementoutput.nrrd"
        measurementoutput = measurementoutput.format(**locals())

        if (not os.path.exists(workdir)):
            os.makedirs(workdir)

        if system.is_file_newer(measurementoutput, labelmap, opts.overwrite) or \
                system.is_file_newer(measurementoutput, "{workdir}/laplacianCache.nii.gz".format(**locals()), opts.overwrite):
            cmd = "{pathThicknessTool} --mr --sbt --ids {ids} --idl {idl} --idh {idh} --idn {idn} --ttrns 500 " +\
                "--workdir {workdir} --cachedLaplacianOutput laplacianCache.nii.gz {labelmap} {measurementoutput}"
            cmd = cmd.format(**locals())
            system.run_process(cmd,verbose=True)




def genparamesh(opts, config, data, outputDir):
    pathGenParaMesh = config["GenParaMeshCLPPath"]
    pathImageMath = config["ImageMathPath"]
    pathSegPostProcess = config["SegPostProcessCLPPath"]
    workdir = "{outputDir}/Processing/1.MeasurementandSPHARM".format(**locals())

    for (id, labelmap, group) in data:
        eulerName = "{workdir}/{id}.euler.txt".format(**locals())
        paraFile = "{workdir}/{id}.para.vtk".format(**locals())
        surfFile = "{workdir}/{id}.surf.vtk".format(**locals())
        surfaceLabel = "{workdir}/{id}.seg.nii.gz".format(**locals())
        segpostLabel = "{workdir}/{id}.segpost.nii.gz".format(**locals())

        if (not system.is_file_exist(surfaceLabel,opts.overwrite)):
            ids = opts.ids
            cmd = "{pathImageMath} {labelmap} -extractLabel {ids} -outfile {surfaceLabel}"
            cmd = cmd.format(**locals())
            system.run_process(cmd,verbose=opts.verbose)

        if (not system.is_file_exist(segpostLabel,opts.overwrite)):
            cmd = "{pathSegPostProcess} {surfaceLabel} {segpostLabel}"
            cmd = cmd.format(**locals())
            system.run_process(cmd,verbose=opts.verbose)

        if (not system.is_file_exist(paraFile,opts.overwrite)):
            num_iters = opts.genparamesh_iter
            cmd = "{pathGenParaMesh} --EulerFile --outEulerName {eulerName} {segpostLabel} " +\
                    "--iter {num_iters} --label 1 {paraFile} {surfFile}"
            cmd = cmd.format(**locals())
            system.run_process(cmd,verbose=opts.verbose)



def paratospharm(opts, config, data, outputDir):
    workdir = "%s/Processing/1.MeasurementandSPHARM" % (outputDir)
    pathParaToSPHARM = config["ParaToSPHARMMeshCLPPath"]

    idlist = [id for id,l,g in data]
    parafiles = ["%s/%s.para.vtk"%(workdir,id) for id,l,g in data]
    surffiles = ["%s/%s.surf.vtk"%(workdir,id) for id,l,g in data]
    lowresfiles = ["%s/%s.ip.SPHARM.vtk"%(workdir,id) for id,l,g in data]
    highresfiles = ["%s/%s.subj.SPHARM.vtk"%(workdir,id) for id,l,g in data]
    lowresparams = ["%s/%s.ip.Param.vtk"%(workdir,id) for id,l,g in data]
    highresparams = ["%s/%s.subj.Param.vtk"%(workdir,id) for id,l,g in data]
    dataset = zip(parafiles, surffiles, lowresfiles, lowresparams, highresfiles, highresparams)

    for idx,(pf,sf,lm,lp,hm,hp) in enumerate(dataset):
        # check if the parafile is newer than lm-output
        if system.is_file_newer(lm, pf, opts.overwrite):
            if idx == 0:
                id = idlist[idx]
                cmd = "{pathParaToSPHARM} {pf} {sf} --subdivLevel 10 --spharmDegree 20 " +\
                        " {workdir}/{id}.ip. --paraOut"
            else:
                id = idlist[idx]
                refid = idlist[0]
                cmd = "{pathParaToSPHARM} {pf} {sf} --subdivLevel 10 --spharmDegree 20  " +\
                        "{workdir}/{id}.ip. --flipTemplateOn " +\
                        "--flipTemplate {workdir}/{refid}.ip.SPHARM.coef --paraOut"
            cmd = cmd.format(**locals())
            system.run_process(cmd,verbose=opts.verbose)


    for idx,(pf,sf,lm,lp,hm,hp) in enumerate(dataset):
        # check if the parafile is newer than hm-output
        if system.is_file_newer(hm, pf, opts.overwrite):
            if idx == 0:
                id = idlist[idx]
                cmd = "{pathParaToSPHARM} {pf} {sf} --subdivLevel 50 --spharmDegree 20 " +\
                        "{workdir}/{id}.subj. --paraOut"
            else:
                id = idlist[idx]
                refid = idlist[0]
                cmd = "{pathParaToSPHARM} {pf} {sf} --subdivLevel 50 --spharmDegree 20 " +\
                        "{workdir}/{id}.subj. --flipTemplateOn " +\
                        "--flipTemplate {workdir}/{refid}.subj.SPHARM.coef --paraOut"
            cmd = cmd.format(**locals())
            system.run_process(cmd,verbose=opts.verbose)


def resample_segmentations(opts,config,data,outputdir):
    workdir = "%s/Processing/1.MeasurementandSPHARM" % (outputdir)
    refid = data[0][0]
    reference_image = "{workdir}/{refid}.segpost.nii.gz".format(**locals())

    pathResampleVolume = config["ResampleVolume2Path"]
    for id,l,g in data:
        segpost_image = "{workdir}/{id}.segpost.nii.gz".format(**locals())
        labelMapNCResampled = "{workdir}/{id}.labelMapNCsegmentation.nrrd".format(**locals())
        cmd = "{pathResampleVolume} {segpost_image} {labelMapNCResampled} -R {reference_image} -i nn"
        if system.is_file_newer(labelMapNCResampled, segpost_image, opts.overwrite):
            cmd = cmd.format(**locals())
            system.run_process(cmd,verbose=True)


# @brief compute consistent boundary conditions from surface maps
def regenerate_segmentations(data, config, outputdir):
    pathKmesh = config["kmeshPath"]
    pathKcalc = config["kcalcPath"]
    workdir = "{outputdir}/Processing/1.MeasurementandSPHARM".format(**locals())

    # before executing the boundary correction
    # check if none of input is not generated.
    testLabelMapsFail = False in [os.path.exists(x) for (t,x,g) in data]
    if testLabelMapsFail:
        raise RuntimeError("There are missing label maps")

    surfaceInputList = ["{workdir}/{id}.subj.SPHARM.vtk".format(**locals()) for (id,l,g) in data]
    testSurfaceInputsFail = False in [os.path.exists(x) for x in surfaceInputList]
    if testSurfaceInputsFail:
        raise RuntimeError("There are missing surface inputs. Check SPHARM results!")

    if opts.nop1 is False:
        for idx, (id,labelMap,group) in enumerate(data):
            labelOutput = "{workdir}/{id}.zerocortex.nrrd".format(**locals())
            surfaceInput = "{workdir}/{id}.subj.SPHARM.vtk".format(**locals())
            #surfaceInput = "{workdir}/{id}.surf.vtk".format(**locals())
            surfaceLabels = "{workdir}/{id}.labels.vtp".format(**locals())

            #if system.is_file_newer(labelOutput, labelMap, opts.overwrite):
            if (not system.is_file_exist(labelOutput)):
                cmd = "{pathKcalc} -e 'A==3?0:A' -o {labelOutput} {labelMap}"
                cmd = cmd.format(**locals())
                if system.run_process(cmd,verbose=True) != 0:
                    raise RuntimeError("fail to modify labelmap")

            if system.is_file_newer(surfaceLabels, surfaceInput, opts.overwrite) or \
                    system.is_file_newer(surfaceLabels, labelOutput, opts.overwrite):
                cmd = "{pathKmesh} -sampleImage -zrotate -outputScalarName labels " + \
                        "{labelOutput} {surfaceInput} {surfaceLabels}"
                cmd = cmd.format(**locals())
                if system.run_process(cmd,verbose=True) != 0:
                    raise RuntimError("fail to run kmesh") 

    # compute the average of labels scalar values to smooth out
    if opts.nop2 is False:
        cmd = "{pathKmesh} -averageScalars -threshold 1.8 " + \
              "-scalarName labels -outputScalarName meanLabels"
        cmd = cmd.format(**locals())
        for (tag, labelmap, group) in data:
            surfaceMeshWithLabels = "{workdir}/{tag}.labels.vtp".format(**locals())
            cmd += " " + surfaceMeshWithLabels

        system.run_process(cmd,verbose=True)

    if opts.nop3 is False:
        for idx,(tag,labelMap,group) in enumerate(data):
            labelOutput = "{workdir}/{tag}.zerocortex.nrrd".format(**locals())
            surfaceLabels = "{workdir}/{tag}.labels.vtp".format(**locals())
            voronoiImage = "{workdir}/{tag}.voronoi.mha".format(**locals())
            surfaceImage = "{workdir}/{tag}.solution.mha".format(**locals())
            boundaryMap = "{workdir}/{tag}.boundaryMap.mha".format(**locals())

            # if system.is_file_newer(labelOutput, voronoiImage, opts.overwrite) or \
            #         system.is_file_newer(surfaceLabels, voronoiImage, opts.overwrite):
                

            # if system.is_file_newer(labelOutput, voronoiImage, opts.overwrite) or \
            #         system.is_file_newer(surfaceLabels, voronoiImage, opts.overwrite):


            # if system.is_file_newer(voronoiImage, boundaryMap, opts.overwrite) or \
            #         system.is_file_newer(surfaceImage, boundaryMap, opts.overwrite):

            if (not system.is_file_exist(voronoiImage,opts.overwrite)):
                cmd = "{pathKmesh} -voronoiImage -zrotate -scalarName labels " +\
                    "{labelOutput} {surfaceLabels} -o {voronoiImage}"
                cmd = cmd.format(**locals())
                system.run_process(cmd,verbose=True)

            if (not system.is_file_exist(surfaceImage,opts.overwrite)):
                cmd = "{pathKmesh} -scanConversion -zrotate " +\
                    "{surfaceLabels} {labelOutput} {surfaceImage}"
                cmd = cmd.format(**locals())
                system.run_process(cmd,verbose=True)

            if (not system.is_file_exist(boundaryMap,opts.overwrite)):
                cmd = "{pathKcalc} -e 'B>0?3:A' -o {boundaryMap} " +\
                    "{voronoiImage} {surfaceImage}"
                cmd = cmd.format(**locals())
                system.run_process(cmd,verbose=True)


def setup_particle_tools(config, data, outputDir, ids):
    inputSurfaceFiles = open(\
        "{outputDir}/Processing/2.shapeworks/inputsurfacemodels.txt".format(**locals()), 'w')
    inputImageFiles = open(\
        "{outputDir}/Processing/2.shapeworks/inputimage.txt".format(**locals()), 'w')
    outputCorrespondenceFiles = open(\
        "{outputDir}/Processing/2.shapeworks/outputCorrespondence.txt".format(**locals()), 'w')
    outputWarpedFiles = open(\
        "{outputDir}/Processing/2.shapeworks/outputWarped.txt".format(**locals()), 'w')

    workdir = "{outputDir}/Processing/1.MeasurementandSPHARM".format(**locals())
    lowresfiles = ["{workdir}/{id}.ip.SPHARM.vtk".format(**locals()) for id,l,g in data]
    highresfiles = ["{workdir}/{id}.subj.SPHARM.vtk".format(**locals()) for id,l,g in data]
    segmentationfiles = ["{workdir}/{id}.segpost.nii.gz".format(**locals()) for id,l,g in data]
    shapedir = "{outputDir}/Processing/2.shapeworks".format(**locals())
    correspondencefiles = ["{shapedir}/{id}.correspondence.vtk".format(**locals()) for id,l,g in data]
    warpedfiles = ["{shapedir}/{id}.warped.vtk".format(**locals()) for id,l,g in data]

    # file generation
    inputSurfaceFiles.write("\n".join(lowresfiles))
    inputImageFiles.write("\n".join(segmentationfiles))
    outputCorrespondenceFiles.write("\n".join(correspondencefiles))
    outputWarpedFiles.write("\n".join(warpedfiles))

    inputSurfaceFiles.close()
    inputImageFiles.close()
    outputCorrespondenceFiles.close()
    outputWarpedFiles.close()


def run_particle_tools(config, data, outputdir, ids):
    import sys,os
    pathPython = sys.executable
    pathShapeWorksScript = os.path.dirname(os.path.abspath(__file__)) + "/shapeworks.py"
    pathShapeWorksRun = config["ShapeWorksRunPath"]
    pathImageMath = config["ImageMathPath"]
    pathShapeWorksGroom = config["ShapeWorksGroomPath"]
    pathBinaryToDistanceMap = config["BinaryToDistanceMapPath"]

    workdir = "%s/Processing/2.shapeworks" % (outputdir)

    # generate binary distance map for each label map
    # cmd = "%s %s %s/inputimage.txt %s/inputsurfacemodels.txt -c %s/outputCorrespondence.txt -w %s/outputWarped.txt --workingDir %s --pathShapeWorksRun %s --pathShapeWorksGroom %s --pathImageMath %s --pathBinaryToDistanceMap %s" % (pathPython, pathShapeWorksScript, workdir, workdir, workdir, workdir, workdir, pathShapeWorksRun, pathShapeWorksGroom, pathImageMath, pathBinaryToDistanceMap)

    outputCorrespondence = "{workdir}/outputCorrespondence.txt"
    outputCorrespondence = outputCorrespondence.format(**locals())  
    if (not system.is_file_exist(outputCorrespondence,opts.overwrite)):

        cmd = "{pathPython} {pathShapeWorksScript} {workdir}/inputimage.txt " +\
                "{workdir}/inputsurfacemodels.txt " + \
                "-c {workdir}/outputCorrespondence.txt " +\
                "-w {workdir}/outputWarped.txt " +\
                "--workingDir {workdir}" 
            
        cmd = cmd.format(**locals())         
        system.run_process(cmd,verbose=True)


def performSplit(args, outputPattern):
    # read each argument file
    for inputFile in args:
        fin = open(inputFile)
        lines = fin.readlines()
        outputLines = {}
        # iterate over the entire lines
        for line in lines:
            words = line.split("\t")
            regionId = int(words[0])
            # skip if the region is 0
            if (regionId == 0):
                continue
            # otherwise, add to outputLines separately
            if (regionId in outputLines):
                outputLines[regionId].append(line)
            else:
                outputLines[regionId] = [ line ]
        fin.close()
        # write all region lines
        for region in outputLines:
            ofile = outputPattern % (region)
            fout = open(ofile, "w")
            for line in outputLines[region]:
                fout.write(line)
            fout.close()


# @brief Main function
if (__name__ == "__main__"):
    parser = OptionParser(usage="usage: %prog dataset.csv config.bms output-directory")
    #  parser.add_option("--labelprocessing", help="preprocessing for label map generation", action="store_true", dest="labelprocessing")
    parser.add_option("--path", help="add directories to PATH environment (e.g. --path=/usr/bin:/home/bin)", dest="dirs", metavar="PATH", default="")
    parser.add_option("--genparamesh", help="generate SPHARM parameter and surface mesh", action="store_true", dest="genparamesh")
    parser.add_option("--genparamesh-iter", metavar="NUM", help="set the number of iteration for GenParaMesh (default: 100)", type="int", dest="genparamesh_iter", default=1000)
    parser.add_option("--paratospharm", help="reconstruct surface mesh from SPHARM parameters", action="store_true", dest="paratospharm")
    parser.add_option("--resample-segmentations", help="resample segmentation images to have consistent dimensions", action="store_true", dest="resample_segmentations")
    parser.add_option("--run-particle-tools", help="run particle correspondence", action="store_true", dest="run_particle_tools")
    parser.add_option("--regenerate-segmentations", dest="regenerate_segmentations", help="Regenerate segmentation images based on reconstructed mesh", action="store_true")
    parser.add_option("--compute-thickness", help="compute thickness for a given label", action="store_true", dest="compute_thickness")
    parser.add_option("--sample-thickness", help="sample thickness from the measurement with a given mesh", action="store_true", dest="sample_thickness")
    parser.add_option("--compute-statistics", help="compute statistics for hypothesis testing", action="store_true", dest="compute_statistics")
    parser.add_option("--run-preprocessing", help="generate surface meshes and regenerate consistent labelmaps", action="store_true", dest="run_preprocessing")
    parser.add_option("--run-all", help="run all pipeline steps", action="store_true", dest="run_all")

    parser.add_option("--idn", metavar="6", help="Neumann Boundary label", dest="idn", default="6")
    parser.add_option("--ids", metavar="3", help="solution label", dest="ids", default="3")
    parser.add_option("--idl", metavar="2", help="low boundary label", dest="idl", default="2")
    parser.add_option("--idh", metavar="1", help="high boundary label", dest="idh", default="1")

    parser.add_option("--labelNCleft", help="label id for NC left", dest="labelNCleft", default="30")
    parser.add_option("--labelNCright", help="label id for NC right", dest="labelNCright", default="14")
    parser.add_option("--labelOB", help="label id for Olfactory Bulb", dest="labelOB", default="16")

    parser.add_option("--regionSplit", help="split the data file with its region (1st column)", dest="regionSplit", action="store_true")
    parser.add_option("--outputPattern", help="Specify the output pattern ex) --outputPattern region_control_%02d.txt", dest="outputPattern")
    parser.add_option("--overwrite", help="specify if the script overwrites previous results", action="store_true", dest="overwrite", default=False)
    parser.add_option("--log-file", help="Specify the filename for logging stdout and stderr outputs", dest="logfileName", default=None)
    parser.add_option("--check-commands", help="Specify if the script logs only command lines not executing those", action="store_true", dest="check_commands")
    parser.add_option("--verbose", help="Print out logs to cosnole", action="store_true", dest="verbose", default=False)

    parser.add_option("--nop1", help="Debug flag to skip a part1 of an algorithm", action="store_true", dest="nop1", default=False)
    parser.add_option("--nop2", help="Debug flag to skip a part1 of an algorithm", action="store_true", dest="nop2", default=False)
    parser.add_option("--nop3", help="Debug flag to skip a part1 of an algorithm", action="store_true", dest="nop3", default=False)

    (opts, args) = parser.parse_args()



    # argument processing
    if (len(args) < 2):
        parser.print_help()
    else:
        csvfile = args[0]
        bmsfile = args[1]
        outputdir = args[2]

	print "CSVFILE: " + csvfile
        print "bmsfile: " + bmsfile
	print "Outputdir: " + outputdir

        check_directories(outputdir)
        config = initialize_programs(opts)
        csvdata = initalize_dataset(csvfile)
        initialize_system_logging(opts)


        if (opts.regionSplit):
            performSplit(args, opts.outputPattern)
            # just finish the script
            sys.exit(0)


        if (opts.genparamesh):
            genparamesh(opts, config, csvdata, outputdir)

        if (opts.paratospharm):
            paratospharm(opts, config, csvdata, outputdir)

        if (opts.resample_segmentations):
            resample_segmentations(opts,config,csvdata,outputdir)

        if (opts.regenerate_segmentations):
            regenerate_segmentations(csvdata, config, outputdir)

        if (opts.compute_thickness):
            compute_thickness(opts, config, csvdata, outputdir, opts.ids, opts.idl, opts.idh, opts.idn)

        if (opts.run_particle_tools):
            setup_particle_tools(config, csvdata, outputdir, opts.ids)
            run_particle_tools(config, csvdata, outputdir, opts.ids)

        if opts.sample_thickness:
            sample_thickness(opts, config, csvdata, outputdir, "initial_dense")

        if (opts.compute_statistics):
            #perform_analysis(csvdata, config, outputdir, "initial_dense")
            perform_analysis(opts,config,csvdata,outputdir,"initial_dense")
            # perform_analysis(csvdata, config, outputdir, "spharm_sampling")
            # perform_analysis(csvdata, config, outputdir, "correspondence")

        if (opts.run_preprocessing):
            genparamesh(opts, config, csvdata, outputdir)
            paratospharm(opts, config, csvdata, outputdir)
            resample_segmentations(opts,config,csvdata,outputdir)
            regenerate_segmentations(csvdata, config, outputdir)

        if (opts.run_all):
            genparamesh(opts, config, csvdata, outputdir)
            paratospharm(opts, config, csvdata, outputdir)
            resample_segmentations(opts,config,csvdata,outputdir)
            regenerate_segmentations(csvdata, config, outputdir)
            compute_thickness(opts, config, csvdata, outputdir, opts.ids, opts.idl, opts.idh, opts.idn)
            if opts.run_particle_tools:
                 setup_particle_tools(config, csvdata, outputdir, opts.ids)
                 run_particle_tools(config, csvdata, outputdir, opts.ids)
            perform_analysis(opts, config, csvdata, outputdir, "initial_dense")
