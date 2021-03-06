//
//  vtkio.cpp
//  ktools
//
//  Created by Joohwi Lee on 12/5/13.
//
//

#include "vtkio.h"
#include <vtkDataSet.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>
#include <vtkPolyDataReader.h>
#include <vtkPolyDataWriter.h>
#include <vtkXMLPolyDataReader.h>
#include <vtkXMLPolyDataWriter.h>
#include <vtkXMLUnstructuredGridWriter.h>
#include <vtkMath.h>

static bool endswith(std::string file, std::string ext) {
    int epos = file.length() - ext.length();
    if (epos < 0) {
        return false;
    }
    return file.rfind(ext) == epos;
}

void vtkIO::zrotate(vtkPolyData* p) {
    int np = p->GetNumberOfPoints();
    vtkPoints* points = p->GetPoints();
    for (int i = 0; i < np; i++) {
        double x[3];
        points->GetPoint(i, x);
//        cout << x[0] << "," << x[1] << "," << x[2] << endl;
        x[0] = -x[0];
        x[1] = -x[1];
        points->SetPoint(i, x);
//        cout << x[0] << "," << x[1] << "," << x[2] << endl;
    }
    p->SetPoints(points);
}


/// @param v1 a vector to rotate
/// @param v2 a vector to which v1 rotates
/// @param rotation an output matrix that stores a transform v1 to v2
void vtkIO::rotateVector(const double *x1, const double *x2, vnl_matrix<double> &rotation) {
    double v1[3], v2[3], vn[3];

    /// Compute the norm for v1 and v2
    const double n1 = vtkMath::Norm(x1);
    const double n2 = vtkMath::Norm(x2);

    for (int i = 0; i < 3; i++) {
        v1[i] = x1[i] / n1;
        v2[i] = x2[i] / n2;
    }

    /// Compute the cross product
    vtkMath::Cross(v1, v2, vn);

    double nn = vtkMath::Normalize(vn);
    double theta = asin(nn);

    /// sin(theta)
    double st = nn;
    /// 1 - cos(theta)
    double cct = 1 - cos(theta);

    rotation.set_size(3, 3);
    rotation[0][0] = 1 + cct * (vn[0]*vn[0] - 1);
    rotation[0][1] = 0 - vn[2] * st + cct * (vn[0]*vn[1]);
    rotation[0][2] = 0 + vn[1] * st + cct * (vn[0]*vn[2]);
    rotation[1][0] = 0 + vn[2] * st + cct * (vn[0]*vn[1]);
    rotation[1][1] = 1 + cct * (vn[1]*vn[1] - 1);
    rotation[1][2] = 0 - vn[0] * st + cct * (vn[1] * vn[2]);
    rotation[2][0] = 0 - vn[1] * st + cct * (vn[0] * vn[2]);
    rotation[2][1] = 0 + vn[0] * st + cct * (vn[1] * vn[2]);
    rotation[2][2] = 1 + cct * (vn[2]*vn[2] - 1);
}


/// @brief Read a vtk/vtp file. The file's type is automatically determined by its extension.
vtkPolyData* vtkIO::readFile(std::string file) {
    if (endswith(file, ".vtp")) {
        vtkXMLPolyDataReader* r = vtkXMLPolyDataReader::New();
        r->SetFileName(file.c_str());
        r->Update();
        return r->GetOutput();
    } else if (endswith(file, ".vtk")) {
        vtkPolyDataReader* r = vtkPolyDataReader::New();
        r->SetFileName(file.c_str());
        r->Update();
        return r->GetOutput();
    }
    return NULL;
}

/// @brief Write a vtk/vtp file. The file's type is automatically determined by its extension.
void vtkIO::writeFile(std::string file, vtkDataSet *mesh) {
    if (endswith(file, ".vtp")) {
        vtkXMLPolyDataWriter* w = vtkXMLPolyDataWriter::New();
        w->SetInputData(mesh);
        w->SetFileName(file.c_str());
        w->Write();
        w->Delete();
    } else if (endswith(file, ".vtk")) {
        vtkPolyDataWriter* w = vtkPolyDataWriter::New();
        w->SetInputData(mesh);
        w->SetFileName(file.c_str());
        w->Write();
        w->Delete();
    } else if (endswith(file, ".vtu")) {
        vtkXMLUnstructuredGridWriter* w = vtkXMLUnstructuredGridWriter::New();
        w->SetInputData(mesh);
        w->SetFileName(file.c_str());
        w->Write();
        w->Delete();
    }
}


void vtkIO::writeXMLFile(std::string file, vtkPolyData *mesh) {
    vtkXMLPolyDataWriter* w = vtkXMLPolyDataWriter::New();
    w->SetInputData(mesh);
    w->SetFileName(file.c_str());
    w->SetDataModeToAppended();
    w->EncodeAppendedDataOff();
    w->SetCompressorTypeToZLib();
    w->SetDataModeToBinary();
    w->Write();
    w->Delete();
}
