//-
// ==========================================================================
// Copyright 2015 Autodesk, Inc.  All rights reserved.
//
// Use of this software is subject to the terms of the Autodesk
// license agreement provided at the time of installation or download,
// or which otherwise accompanies this software in either electronic
// or hard copy form.
// ==========================================================================
//+

//
//  File: basicBlendShape.cpp
//
//  Description:
//      Rudimentary implementation of a blendshape.
//
//      Use this script to create a simple example.
/*      
loadPlugin basicBlendShape;
polyTorus -r 1 -sr 0.5 -tw 0 -sx 50 -sy 50 -ax 0 1 0 -cuv 1 -ch 1;
polyTorus -r 1 -sr 0.5 -tw 0 -sx 50 -sy 50 -ax 0 1 0 -cuv 1 -ch 1;
scale -r 0.5 1 1;
makeIdentity -apply true -t 1 -r 1 -s 1 -n 0 -pn 1;
select -r pTorus1;
deformer -type "basicBlendShape";
blendShape -edit -t pTorus1 0 pTorus2 1.0 basicBlendShape1;
*/
#pragma once

#include <maya/MTypeId.h> 
#include <maya/MMatrixArray.h>
#include <maya/MPxBlendShape.h> 


class basicBlendShape : public MPxBlendShape {
public:
    static  void*   creator();
    static  MStatus initialize();

    // Deformation function
    //
    virtual MStatus deformData(
		MDataBlock&    block,
		MDataHandle geomData,
		unsigned int groupId,
		const MMatrix& mat,
		unsigned int multiIndex
	);

    static MTypeId id;
};

