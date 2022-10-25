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

#pragma once

#include <vector>

#include <maya/MPxNode.h>
#include <maya/MFnNumericAttribute.h>
#include <maya/MFnStringData.h>
#include <maya/MFnTypedAttribute.h>
#include <maya/MTypeId.h> 
#include <maya/MEvaluationNode.h>
#include <maya/MFnMessageAttribute.h>

#include "simplex.h"
 
class simplex_maya : public MPxNode
{
public:
	simplex_maya();
	virtual	~simplex_maya(); 

	virtual	MStatus	compute( const MPlug& plug, MDataBlock& data );
	virtual MStatus preEvaluation(const  MDGContext& context, const MEvaluationNode& evaluationNode);
	virtual MStatus setDependentsDirty(const MPlug& plug, MPlugArray& plugArray);
	static	void*	creator();
	static	MStatus	initialize();

public:
	static MObject	aSliders;
	static MObject	aWeights;
	static MObject	aDefinition;
	static MObject	aMinorUpdate;
	static MObject	aExactSolve;

	static	MTypeId	id;


private:
	simplex::Simplex * sPointer;
	std::vector<double> cache;
	bool simplexIsValid = false;
	bool cacheIsValid = false;
};

