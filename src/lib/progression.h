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

#include "enums.h"
#include "shapeBase.h"
#include "rapidjson/document.h"

#include <utility>
#include <vector>
#include <string>


namespace simplex {

class Simplex;
class Shape;

typedef std::pair<Shape*, double> ProgPair;
typedef std::vector<ProgPair> ProgPairs;

class Progression : public ShapeBase {
	private:
		ProgPairs pairs;
		ProgType interp;
		static size_t getInterval(double tVal, const std::vector<double> &times, bool &outside);
		ProgPairs getSplineOutput(double tVal, double mul=1.0) const;
		ProgPairs getSplitSplineOutput(double tVal, double mul=1.0) const;
		ProgPairs getLinearOutput(double tVal, double mul=1.0) const;

		static ProgPairs getRawSplineOutput(const std::vector<const std::pair<Shape*, double>* > pairs, double tVal, double mul=1.0);
		static ProgPairs getRawLinearOutput(const std::vector<const std::pair<Shape*, double>* > pairs, double tVal, double mul=1.0);

	public:
		ProgPairs getOutput(double tVal, double mul=1.0) const;

		Progression(const std::string &name, const ProgPairs &pairs, ProgType interp);
		static bool parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp);
		static bool parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp);
		static bool parseJSONv3(const rapidjson::Value &val, size_t index, Simplex *simp);
};


}

