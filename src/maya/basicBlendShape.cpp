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

#include "basicBlendShape.h"

#include <maya/MFloatArray.h>
#include <maya/MPoint.h>
#include <maya/MPointArray.h>

#include <maya/MItGeometry.h>
#include <maya/MFnPointArrayData.h>
#include <maya/MFnComponentListData.h>


MTypeId basicBlendShape::id(0x00122706);

void* basicBlendShape::creator() {
    return new basicBlendShape();
}

MStatus basicBlendShape::initialize() {
    return MStatus::kSuccess;
}


MStatus
basicBlendShape::deformData(MDataBlock& block,
					  MDataHandle geomData,
					  unsigned int /*groupId*/,
                      const MMatrix& /*m*/,
                      unsigned int multiIndex)
//
// Method: deform
//
// Description:   Deforms the point with a simple smooth skinning algorithm
//
// Arguments:
//   block      : the datablock of the node
//   geomData   : a handle to the geometry to be deformed
//	 groupId	: the group ID of the geometry to deform
//   m          : matrix to transform the point into world space
//   multiIndex : the index of the geometry that we are deforming
//
//
{
    MStatus returnStatus;

	// get the weights
	//
	MArrayDataHandle weightMH = block.inputArrayValue(weight);
	unsigned int numWeights = weightMH.elementCount();
	MFloatArray weights;
	for (unsigned int w=0; w<numWeights; ++w) {
		weights.append(weightMH.inputValue().asFloat());
		weightMH.next();
	}

	// get the input targets
	// as a point array per weight
	//
	MArrayDataHandle inputTargetMH = block.inputArrayValue(inputTarget);
	returnStatus = inputTargetMH.jumpToElement(multiIndex);
	if (!returnStatus) {
		return returnStatus;
	}
	MDataHandle inputTargetH = inputTargetMH.inputValue();
	MArrayDataHandle inputTargetGroupMH = inputTargetH.child(inputTargetGroup);
	for (unsigned int w=0; w<numWeights; ++w) {
		// inputPointsTarget is computed on pull,
		// so can't just read it out of the datablock
		MPlug plug(thisMObject(), inputPointsTarget);
		plug.selectAncestorLogicalIndex(multiIndex, inputTarget);
		plug.selectAncestorLogicalIndex(w, inputTargetGroup);
		// ignore deformer chains here and just take the first one
		plug.selectAncestorLogicalIndex(6000, inputTargetItem);
		MDGContext context = block.context();
		MObject pointArray = plug.asMObject(context);
		MPointArray pts = MFnPointArrayData(pointArray).array();

		// get the component list
		plug = plug.parent();
		plug = plug.child(inputComponentsTarget);
		MFnComponentListData compList(plug.asMObject(context));
		if (compList.length() == 0) {
			continue;
		}
		MObject comp = compList[0];

		// iterate over the components
		float defWgt = weights[w];
		inputTargetGroupMH.jumpToArrayElement(w);
		MArrayDataHandle targetWeightsMH = inputTargetGroupMH.inputValue().child(targetWeights);
		unsigned int ptIndex = 0;
		MItGeometry iter(geomData, comp, false);
		for (; !iter.isDone(); iter.next(), ++ptIndex) {
			MPoint pt = iter.position();
			unsigned int compIndex = iter.index();
			float wgt = defWgt;
			if (targetWeightsMH.jumpToElement(compIndex)) {
				wgt *= targetWeightsMH.inputValue().asFloat();
			}
			pt += pts[ptIndex] * wgt;
			iter.setPosition(pt);
		}
	}

    return returnStatus;
}


