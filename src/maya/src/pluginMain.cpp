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

#include "simplex_mayaNode.h"
#include "basicBlendShape.h"
#include "version.h"
#include <maya/MFnPlugin.h>
#include <maya/MObject.h>
#include <maya/MStatus.h>

MStatus initializePlugin(MObject obj)
{ 
	MStatus status;
	MFnPlugin plugin(obj, "Blur Studio", VERSION_STRING, "Any");

	status = plugin.registerNode(
		"simplex_maya",
		simplex_maya::id,
		&simplex_maya::creator,
		&simplex_maya::initialize
	);

	if (!status) {
		status.perror("registerNode simplex_maya");
		return status;
	}

    status = plugin.registerNode(
        "basicBlendShape",
        basicBlendShape::id,
        &basicBlendShape::creator,
        &basicBlendShape::initialize,
        MPxNode::kBlendShape
	);

	if (!status) {
		status.perror("registerNode basicBlendShape");
		return status;
	}
	return status;
}

MStatus uninitializePlugin(MObject obj)
{
	MStatus status;
	MFnPlugin plugin(obj);

	status = plugin.deregisterNode(simplex_maya::id);
	if (!status) {
		status.perror("deregisterNode simplex_maya");
		return status;
	}

	status = plugin.deregisterNode(basicBlendShape::id);
	if (!status) {
		status.perror("deregisterNode basicBlendShape");
		return status;
	}

	return status;
}

