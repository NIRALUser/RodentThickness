#include "MeshPointsIntensitySamplingCLP.h"

#include <math.h>

#include <itkDefaultDynamicMeshTraits.h>
#include <itkSpatialObjectReader.h>
#include <itkSpatialObjectWriter.h>
#include <itkSceneSpatialObject.h>
#include <itkMetaMeshConverter.h>
#include <itkVTKPolyDataReader.h>

#include <itkImage.h>
#include <itkImageFileReader.h>
#include <itkImageFileWriter.h> 
#include <itkInterpolateImageFunction.h>
#include <itkLinearInterpolateImageFunction.h>
#include <itkNearestNeighborInterpolateImageFunction.h>
#include <itkBinaryThresholdImageFilter.h>
#include <itkSignedDanielssonDistanceMapImageFilter.h>
#include <itkDanielssonDistanceMapImageFilter.h>
#include <itkUnaryFunctorImageFilter.h>

#include "vtkPolyData.h"
#include "vtkPolyDataReader.h"
#include "vtkPolyDataWriter.h"
#include "vtkFloatArray.h"
#include "vtkPolyDataToitkMesh.h"
#include "vtkPoints.h"
#include "vtkPointData.h"
#include "vtkDoubleArray.h"

#include <iostream>
#include "vtkio.h"
#include <vtkPolyData.h>
#include <vtkPointData.h>
#include <vtkIdList.h>
#include <vtkFloatArray.h>
#include <vtkMath.h>

#include <vnl/vnl_vector.h>

typedef itk::DefaultDynamicMeshTraits<double,3,3,double,double> MeshTraitsType;
typedef itk::Mesh<double,3,MeshTraitsType> MeshType;
typedef itk::MeshSpatialObject<MeshType> MeshSOType;
typedef MeshTraitsType::PointType PointType;
typedef MeshTraitsType::CellType CellType;
typedef itk::VTKPolyDataReader<MeshType> VTKReaderType;
typedef itk::MetaMeshConverter<3,double,MeshTraitsType> MeshConverterType;
typedef itk::MeshSpatialObject<MeshType> meshSOType;

typedef itk::Image<short,3> BinaryImageType;
typedef itk::Image<double,3> ImageType;
typedef itk::InterpolateImageFunction<ImageType,double> InterpolatorType;
typedef itk::NearestNeighborInterpolateImageFunction<ImageType,double> NNInterpolatorType;
typedef itk::LinearInterpolateImageFunction<ImageType,double> LinearInterpolatorType;
typedef itk::ImageFileReader<ImageType> ImageReaderType;
typedef itk::BinaryThresholdImageFilter<ImageType,BinaryImageType> ThresholdFilterType;
typedef itk::SignedDanielssonDistanceMapImageFilter<BinaryImageType,ImageType> DistanceFilterType;

static bool _overwriteDistanceVector = false;
static bool _inputAsPhysicalCoord = false;
static bool _inputPointFlip = false;

class VectorMagnitudeSquareFunctor {
  public:
    VectorMagnitudeSquareFunctor() {}
    ~VectorMagnitudeSquareFunctor() {}

    bool operator!=(const VectorMagnitudeSquareFunctor&) const { return false; }
    bool operator==(const VectorMagnitudeSquareFunctor& other) const { return !(*this != other); }
    inline double operator()(const DistanceFilterType::VectorImageType::PixelType& v) { return v[0]*v[0] + v[1]*v[1] + v[2]*v[2]; }
};

typedef itk::UnaryFunctorImageFilter<DistanceFilterType::VectorImageType, ImageType, VectorMagnitudeSquareFunctor> VectorToMag2FilterType;

using namespace std;

namespace {
  void updatePoints(vtkPoints* points, vtkIdType pointId, InterpolatorType::ContinuousIndexType& newpoint, ImageType::SpacingType& spacing, ImageType::PointType& origin) {
    double meshPoint[3];
//    cout << "Spacing: " << spacing[0] << ", " << spacing[1] << ", " << spacing[2] << endl;
//   cout << "Origin: " << origin[0] << ", " << origin[1] << ", " << origin[2] << endl;
    for (int j = 0; j < 3; j++) {
			if (_inputAsPhysicalCoord) {
				meshPoint[j] = newpoint[j] * spacing[j] + origin[j];
			} else {
				// SPHARM doesn't consider the origin
				meshPoint[j] = newpoint[j] * spacing[j];
			}
    }
//   cout << newpoint[0] << "," << newpoint[1] << "," << newpoint[2] << " => " << meshPoint[0] << "," << meshPoint[1] << "," << meshPoint[2] << endl;
    points->SetPoint(pointId, meshPoint);
  }
  int roundd(double d)
  {
      return static_cast<int>(d + 0.5);
  }
  void thresholdDistanceVector(string distanceVector, string thresholdVectorOutput) {
    cout << "Reading " << distanceVector << " ... ";
    typedef itk::ImageFileReader<DistanceFilterType::VectorImageType> VectorReaderType;
    VectorReaderType::Pointer vreader = VectorReaderType::New();
    vreader->SetFileName(distanceVector);
    vreader->Update();
    cout << "done" << endl;

    cout << "Filtering ... ";
    DistanceFilterType::VectorImageType::Pointer distanceMap = NULL;
    distanceMap = vreader->GetOutput();
    cout << "done" << endl;

    VectorToMag2FilterType::Pointer filter = VectorToMag2FilterType::New();
    filter->SetInput(distanceMap);
    filter->Update();

    cout << "Writing " << thresholdVectorOutput << " ... ";
    typedef itk::ImageFileWriter<ImageType> WriterType;
    WriterType::Pointer writer = WriterType::New();
    writer->SetFileName(thresholdVectorOutput);
    writer->SetInput(filter->GetOutput());
    writer->UseCompressionOn();
    writer->Write();
    cout << "done" << endl;
  }



void runSmoothScalars(vtkPolyData* poly, string attrOutput, double sigma, int nIters) {
    vtkMath* math = vtkMath::New();

    // sigma for smoothing
    double sigma2 = sigma;
    sigma2 *= sigma2;

    // number of iterations
    int numIters = nIters;

    // access data
    string scalarName = "sample";
    vtkDataArray* scalars = poly->GetPointData()->GetScalars(scalarName.c_str());
    if (scalars == NULL) {
        cout << "can't find scalars: " << scalarName << endl;
        return;
    }

    // copy the scalars to iteratively apply smoothing
    vtkFloatArray* data = vtkFloatArray::New();
    data->DeepCopy(scalars);

    // prepare new data array
    vtkFloatArray* newData = vtkFloatArray::New();

    string outputScalarName = "smooth_sample";
    newData->SetName(outputScalarName.c_str());
    newData->SetNumberOfTuples(data->GetNumberOfTuples());
    poly->GetPointData()->AddArray(newData);


    // check if the scalar array exists
    if (data == NULL) {
        cout << "can't access scalar array: " << scalarName << endl;
        return;
    }

    // iterate over all points
    vtkIdList* cellIds = vtkIdList::New();
    vtkIdList* ptIds = vtkIdList::New();
    std::set<int> ptSet;

    // build cells
    poly->BuildCells();
    poly->BuildLinks();

    for (int n = 0; n < numIters; n++) {
        for (int i = 0; i < poly->GetNumberOfPoints(); i++) {
            double center[3];
            poly->GetPoint(i, center);

            // collect neighbor cells
            ptSet.clear();

            cellIds->Reset();
            poly->GetPointCells(i, cellIds);

            // iterate over neighbor cells
            for (int j = 0; j < cellIds->GetNumberOfIds(); j++) {
                int cellId = cellIds->GetId(j);
                ptIds->Reset();

                // collect cell points
                poly->GetCellPoints(cellId, ptIds);

                // iterate over all cell points
                for (int k = 0; k < ptIds->GetNumberOfIds(); k++) {
                    int ptId = ptIds->GetId(k);
                    ptSet.insert(ptId);
                }
            }

            // iterate over all neighbor points
            std::set<int>::iterator iter = ptSet.begin();

            // compute weight
            vnl_vector<float> weights;
            weights.set_size(ptSet.size());

            for (int j = 0; iter != ptSet.end(); iter++, j++) {
                int ptId = *iter;
                double neighbor[3];
                poly->GetPoint(ptId, neighbor);

                double dist2 = math->Distance2BetweenPoints(center, neighbor);

                // apply the heat kernel with the sigma
                weights[j] = exp(-dist2/sigma2);
            }

            // add one for the center
            double weightSum = weights.sum() + 1;
            weights /= weightSum;


            // iterate over neighbors and compute weighted sum
            double smoothedValue = data->GetTuple1(i) / weightSum;
            iter = ptSet.begin();

            // compute the weighted averge
            for (uint j = 0; j < ptSet.size(); j++, iter++) {
                int ptId = *iter;
                int value = data->GetTuple1(ptId);
                smoothedValue += (value * weights[j]);
            }
            newData->SetTuple1(i, smoothedValue);
        }


        // prepare next iteration by copying newdata to data
        data->DeepCopy(newData);
    }

    ofstream file(attrOutput.c_str());
    for (int i = 0; i < poly->GetNumberOfPoints(); i++) {
        file << data->GetTuple1(i) << endl;
    }
    file.close();
}

  int extraction(string image, string mesh, string intp, string dstv, double lowThreshold, string attrfileName, string smoothAttrFile, string meshOutput, string meshSampling) {

    cout << "Image: " << image << endl;
    cout << "Mesh: " << mesh << endl;
		cout << "Interpolation: " << intp << endl;
    
    ImageReaderType::Pointer ireader = ImageReaderType::New();
    ireader->SetFileName(image.c_str());
    ireader->Update();
    ImageType::Pointer imagePtr = ireader->GetOutput();

    InterpolatorType::Pointer interpolator = NULL;
		if (intp == "nn") {
			interpolator = static_cast<InterpolatorType::Pointer>(NNInterpolatorType::New());
		} else if (intp == "linear") {
			interpolator = static_cast<InterpolatorType::Pointer>(LinearInterpolatorType::New());
		}
		interpolator->SetInputImage(imagePtr);
    InterpolatorType::ContinuousIndexType pointIndex;

    /*
		MeshConverterType* converter = new MeshConverterType();
		MeshSOType::Pointer soMesh = converter->ReadMeta(mesh.c_str());
		MeshType::Pointer inputMesh = soMesh->GetMesh();
		MeshType::PointsContainerPointer points = inputMesh->GetPoints();
    */
    /*
    vtkPolyDataToitkMesh converter;
    converter.SetInput(reader->GetOutput());
    converter.ConvertvtkToitk();
    MeshType *inputMesh = dynamic_cast<MeshType*>(converter.GetOutput());
		MeshType::PointsContainerPointer points = inputMesh->GetPoints();
    */

    vtkPolyDataReader* reader = vtkPolyDataReader::New();
    reader->SetFileName(mesh.c_str());
    reader->Update();

    vtkPolyData* vtkMesh = reader->GetOutput();


    // keep the original mesh in order to compute smoothed scalars
    vtkPolyData* sourceMesh = vtkPolyData::New();
    sourceMesh->DeepCopy(vtkMesh);
    
     
    vtkPoints* points = vtkMesh->GetPoints();

    DistanceFilterType::Pointer distance = DistanceFilterType::New();
    DistanceFilterType::VectorImageType::Pointer distanceMap = NULL;

    bool dstvExists = itksys::SystemTools::FileExists(dstv.c_str(), true);

    if (!dstvExists || _overwriteDistanceVector) {
      cout << "Generating distance vector: " << dstv << endl;
      ThresholdFilterType::Pointer threshold = ThresholdFilterType::New();

      threshold->SetInput(imagePtr);
      threshold->SetLowerThreshold(1);
      threshold->SetUpperThreshold(32000);

      distance->UseImageSpacingOn();
      distance->SquaredDistanceOn();
      distance->SetInput(threshold->GetOutput());
      distance->Update();

      distanceMap = distance->GetVectorDistanceMap();

      typedef itk::ImageFileWriter<DistanceFilterType::VectorImageType> VectorWriterType;

      VectorWriterType::Pointer writer = VectorWriterType::New();
      writer->SetInput(distanceMap);
      writer->UseCompressionOn();
      writer->SetFileName(dstv);
      writer->Write();

      cout << "Generating distance vector done" << endl;
    } else {
      cout << "Loading distance vector: " << dstv << endl;
      typedef itk::ImageFileReader<DistanceFilterType::VectorImageType> VectorReaderType;

      VectorReaderType::Pointer vreader = VectorReaderType::New();
      vreader->SetFileName(dstv);
      vreader->Update();

      distanceMap = vreader->GetOutput();
    }

    ImageType::SpacingType spacing = imagePtr->GetSpacing();
    ImageType::PointType origin = imagePtr->GetOrigin();

    //int numPoints = points->Size();
    int numPoints = points->GetNumberOfPoints();
    double* extractValue = new double[numPoints];
    memset(extractValue, 0, sizeof(double) * numPoints);

    int e[3] = { 1, 1, 1 };
    ofstream attr;
    attr.open(attrfileName.c_str());

    cout << "Sampling " << numPoints << " points ... " << endl;
    for (int i = 0; i < numPoints; i++) { 
      // PointType p = points->GetElement(i);
      double p[3];
      points->GetPoint(i, p);
	
			if (_inputAsPhysicalCoord) {
				ImageType::PointType meshPoint;
				meshPoint[0] = (_inputPointFlip ? -1 : 1) * p[0];
				meshPoint[1] = (_inputPointFlip ? -1 : 1) * p[1];
				meshPoint[2] = p[2];

				itk::ContinuousIndex<double, 3> meshIndex;
				imagePtr->TransformPhysicalPointToContinuousIndex(meshPoint, meshIndex);
				
				pointIndex[0] = meshIndex[0];
				pointIndex[1] = meshIndex[1];
				pointIndex[2] = meshIndex[2];
			} else {
				for (unsigned int d = 0; d < 3; d++) {
					pointIndex[d] = (e[d] * (_inputPointFlip ? -1 : 1) * p[d]) / spacing[d];
				}
			}
	
      extractValue[i] = interpolator->EvaluateAtContinuousIndex(pointIndex);
      updatePoints(points, i, pointIndex, spacing, origin);

      if (extractValue[i] <= lowThreshold) {
        DistanceFilterType::VectorImageType::PixelType distanceValue;
        DistanceFilterType::VectorImageType::IndexType distanceIndex;
        for (int d = 0; d < 3; d++) {
          distanceIndex[d] = (long int) roundd(pointIndex[d]);
        }
        distanceValue = distanceMap->GetPixel(distanceIndex);

        bool validPointIndex = true;
        for (int d = 0; d < 3 && validPointIndex; d++) {
          pointIndex[d] = distanceIndex[d] + distanceValue[d];
          validPointIndex = validPointIndex && (pointIndex[d] > 0);
        }
        updatePoints(points, i, pointIndex, spacing, origin);
	
        if (validPointIndex) {	
	
          extractValue[i] = interpolator->EvaluateAtContinuousIndex(pointIndex); 
	
          if (extractValue[i] <= lowThreshold) {
            cerr << "error at extracting closest point " << endl;
	
          }
        } else {
	
            extractValue[i] = 0;
            cerr << "invalid pointIndex (" << pointIndex[0] << ", " << pointIndex[1] << ", " << pointIndex[2] << ")" << endl;
        }
      }
      attr << extractValue[i] << endl;
    }
    attr.close();

    cout << "sampling points ... done" << endl;

    vtkMesh->SetPoints(points);
    vtkDoubleArray* arr = vtkDoubleArray::New();
    arr->SetNumberOfValues(numPoints);
    for (int i = 0; i < numPoints; i++) {
      arr->SetValue(i, extractValue[i]);
    }
    arr->SetName("sample");
    vtkMesh->GetPointData()->AddArray(arr);



    // add the samples to the original mesh
    sourceMesh->GetPointData()->AddArray(arr);

    // execute scalar smoothing
    runSmoothScalars(sourceMesh, smoothAttrFile, 1, 10);

    // added smoothed sample to the modified mesh
    vtkMesh->GetPointData()->AddArray(sourceMesh->GetPointData()->GetScalars("smooth_sample"));

    vtkPolyDataWriter* writer1 = vtkPolyDataWriter::New();
    writer1->SetFileName(meshSampling.c_str());
    writer1->SetInputData(vtkMesh);
    writer1->Write();

    vtkPolyDataWriter* writer2 = vtkPolyDataWriter::New();
    writer2->SetFileName(meshOutput.c_str());
    writer2->SetInputData(sourceMesh);
    writer2->Write();

    return 0;
  }
}




int main(int argc, char* argv[]) {
  PARSE_ARGS;

  itksys::SystemTools::ChangeDirectory(workingDirectory.c_str());
  _overwriteDistanceVector = overwriteDistanceVector;
	_inputAsPhysicalCoord = inputAsPhysicalCoord;
  _inputPointFlip = inputPointFlip;

  if (thresholdDistanceVector) {
    ::thresholdDistanceVector(distanceVector, thresholdVectorOutput);
  } else {
    ::extraction(imageName, meshName, interpolation, distanceVector, lowThreshold, attrfileName, smoothAttrFileName, originalMeshOutput, modifiedMeshOutput);
  }
}
