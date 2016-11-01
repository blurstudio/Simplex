/*
Copyright 2016, Blur Studio

This file is part of Simplex.

Simplex is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Simplex is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with Simplex.  If not, see <http://www.gnu.org/licenses/>.
*/

%Module simplex

class Simplex {
%TypeHeaderCode
#include "simplex_lib/simplex.h"
%End

public:
		Simplex(const std::string &json);
		bool parseJSON(const std::string &json);
		std::vector<float> getDeltaIndexValues(const std::vector<float> &vec);
};

%MappedType std::vector<float>
{
%TypeHeaderCode
#include <vector>
%End

%ConvertFromTypeCode
    // Create the vector.
    PyObject *l;
    if ((l = PyList_New(sipCpp->size())) == NULL)
        return NULL;
    // Set the vector elements.
    std::vector<float>::iterator iter;
    int i(0);
    for (iter = sipCpp->begin(); iter != sipCpp->end(); ++iter) {
        PyList_SET_ITEM(l, i++, PyFloat_FromDouble(double(*iter)) );
    }
    return l;
%End

%ConvertToTypeCode
    // Check the type if that is all that is required.
    if (sipIsErr == NULL) {
        if (!PyList_Check(sipPy))
            return 0;
        for (int i = 0; i < PyList_GET_SIZE(sipPy); ++i)
            if (!PyFloat_Check( PyList_GET_ITEM(sipPy, i) ))
                return 0;
        return 1;
    }
    std::vector<float> *qv = new std::vector<float>;
    for (int i = 0; i < PyList_GET_SIZE(sipPy); ++i) {
        qv->push_back(float(PyFloat_AsDouble(PyList_GET_ITEM(sipPy, i))));
    }
    *sipCppPtr = qv;
    return sipGetState(sipTransferObj);
%End
};

%MappedType std::string
{
%TypeHeaderCode
#include <string>
%End

%ConvertFromTypeCode
    return PyString_FromString( sipCpp->c_str() );
%End

%ConvertToTypeCode
    if (sipIsErr == NULL) {
        return PyString_Check(sipPy);
    }
    char* buf = PyString_AsString(sipPy);
    *sipCppPtr = new std::string(buf);

    return sipGetState(sipTransferObj);
%End
};
