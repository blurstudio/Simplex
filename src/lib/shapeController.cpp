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
#include "simplex.h"
#include "shapeController.h"
#include "progression.h"
#include "shape.h"

#include <utility>
#include <vector>
#include "math.h"

using namespace simplex;

void ShapeController::solve(std::vector<double> &accumulator, double &maxAct) const {
	double vm = fabs(value * multiplier);
	if (vm > maxAct) maxAct = vm;

	ProgPairs shapeVals = prog->getOutput(value, multiplier);
	for (auto sit=shapeVals.begin(); sit!=shapeVals.end(); ++sit){
		//for (const auto &svp: shapeVals){
		const auto &svp = *sit;
		accumulator[svp.first->getIndex()] += svp.second;
	}
}

bool ShapeController::getEnabled(const rapidjson::Value &val) {
	auto enIt = val.FindMember("enabled");
	if (enIt != val.MemberEnd()) {
		if (enIt->value.IsBool()) {
			return enIt->value.GetBool();
		}
	}
	return true;
}
