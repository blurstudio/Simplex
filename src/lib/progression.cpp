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

#include "shapeBase.h"
#include "progression.h"
#include "simplex.h"
#include "enums.h"

#include "rapidjson/document.h"
#include "rapidjson/rapidjson.h"

#include <algorithm>  // for sort
#include <utility>
#include <vector>
#include <string>

using namespace simplex;
class simplex::Shape;

Progression::Progression(const std::string &name, const ProgPairs &pairs, ProgType interp):
		ShapeBase(name), pairs(pairs), interp(interp) {
	std::sort(this->pairs.begin(), this->pairs.end(),
		[](const ProgPair &a, const ProgPair &b) {
			return a.second < b.second;
		}
	);
}

size_t Progression::getInterval(double tVal, const std::vector<double> &times, bool &outside){
	if (times.size() <= 1){
		outside = true;
		return 0;
	}
	outside = tVal < times[0] || tVal > times[times.size() - 1];
	if (tVal >= times[times.size() - 2]){
		return times.size() - 2;
	}
	else if (tVal < times[0]){
		return 0;
	}
	else{
		// the percent for the current segment of tVal
		// and the corresponding basis values
		for (size_t i=0; i<times.size()-2; ++i){
			if (times[i] <= tVal && tVal < times[i+1]){
				return i;
			}
		}
		return 0;
	}
}

ProgPairs Progression::getSplineOutput(double tVal, double mul) const{
	std::vector<const ProgPair* > sided;
	for (size_t i = 0; i < pairs.size(); ++i) {
		sided.push_back(&(pairs[i]));
	}
	return getRawSplineOutput(sided, tVal, mul);
}

ProgPairs Progression::getSplitSplineOutput(double tVal, double mul) const{
	std::vector<const ProgPair* > sided;
	bool gt = tVal >= 0.0;
	for (size_t i = 0; i < pairs.size(); ++i) {
		if (gt && pairs[i].second >= 0)
			sided.push_back(&(pairs[i]));
		else if (!gt && pairs[i].second <= 0)
			sided.push_back(&(pairs[i]));
	}
	return getRawSplineOutput(sided, tVal, mul);
}

ProgPairs Progression::getLinearOutput(double tVal, double mul) const{
	std::vector<const ProgPair* > sided;
	for (size_t i = 0; i < pairs.size(); ++i) {
		sided.push_back(&(pairs[i]));
	}
	return getRawLinearOutput(sided, tVal, mul);
}

ProgPairs Progression::getRawSplineOutput(const std::vector<const std::pair<Shape*, double>* > pairs, double tVal, double mul){
	if (
		(pairs.size() <= 2) ||
		(tVal < pairs[0]->second) && (tVal > pairs[pairs.size()-1]->second)
	){
		return getRawLinearOutput(pairs, tVal, mul);
	}

	std::vector<Shape*> shapes;
	std::vector<double> st;
	for (auto it = pairs.begin(); it != pairs.end(); ++it){
		shapes.push_back((*it)->first);
		st.push_back((*it)->second);
	}
	bool outside = false;
	size_t interval = getInterval(tVal, st, outside);
	ProgPairs out;

	double start = st[interval];
	double end = st[interval + 1];

	//# compute the catmull-rom basis multipliers
	double x = (tVal - start) / (end - start);
	if (outside) {
		// If I'm outside the range of the spline, then I linear interpolate along the implicit tangent
		if (interval == 0) {
			out.push_back(std::make_pair(shapes[0], mul * (1.0 - x)));
			out.push_back(std::make_pair(shapes[1], mul * x));
		}
		else {
			out.push_back(std::make_pair(shapes[shapes.size() - 1], mul * x));
			out.push_back(std::make_pair(shapes[shapes.size() - 2], mul * (1.0 - x)));
		}
	}
	else{
		double x2 = x*x;
		double x3 = x2*x;
		double v0 = (-0.5*x3 + 1.0*x2 - 0.5*x);
		double v1 = (1.5*x3 - 2.5*x2 + 1.0);
		double v2 = (-1.5*x3 + 2.0*x2 + 0.5*x);
		double v3 = (0.5*x3 - 0.5*x2);
		if (interval == 0) { // deal with input tangent
			out.push_back(std::make_pair(shapes[0], mul * (v1 + v0 + v0)));
			out.push_back(std::make_pair(shapes[1], mul * (v2 - v0)));
			out.push_back(std::make_pair(shapes[2], mul * (v3)));
		}
		else if (interval == st.size() - 2) { // deal with output tangent
			out.push_back(std::make_pair(shapes[shapes.size() - 3], mul * (v0)));
			out.push_back(std::make_pair(shapes[shapes.size() - 2], mul * (v1 - v3)));
			out.push_back(std::make_pair(shapes[shapes.size() - 1], mul * (v2 + v3 + v3)));
		}
		else {
			out.push_back(std::make_pair(shapes[interval - 1], mul * v0));
			out.push_back(std::make_pair(shapes[interval + 0], mul * v1));
			out.push_back(std::make_pair(shapes[interval + 1], mul * v2));
			out.push_back(std::make_pair(shapes[interval + 2], mul * v3));
		}
	}
	return out;
}

ProgPairs Progression::getRawLinearOutput(const std::vector<const std::pair<Shape*, double>* > pairs, double tVal, double mul){
	ProgPairs out;
	std::vector<double> times;
	if (pairs.size() < 2) return out;

	for (auto it=pairs.begin(); it!=pairs.end(); ++it){
		times.push_back((*it)->second);
	}
	bool outside;
	size_t idx = getInterval(tVal, times, outside);
	double u = (tVal - times[idx]) / (times[idx+1] - times[idx]);
    out.push_back(std::make_pair(pairs[idx]->first, mul * (1.0-u)));
	out.push_back(std::make_pair(pairs[idx+1]->first, mul * u));
	return out;
}

ProgPairs Progression::getOutput(double tVal, double mul) const{
	if (interp == ProgType::spline)
		return getSplineOutput(tVal, mul);
	else if (interp == ProgType::splitSpline)
		return getSplitSplineOutput(tVal, mul);
	else // if (interp == ProgType::linear)
		return getLinearOutput(tVal, mul);
}

bool Progression::parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp){
	if (!val.IsArray()) return false;

	ProgPairs pairs;
	const rapidjson::Value &jindices = val[1];
	const rapidjson::Value &jweights = val[2];
	if (!jweights.IsArray() || !jindices.IsArray()) return false;

	rapidjson::SizeType j;
	for (j = 0; j<jindices.Size(); ++j){
		if (!jindices[j].IsInt()) return false;
		if (!jweights[j].IsNumber()) return false;
		size_t x = (size_t)jindices[j].GetInt();
		double y = (double)jweights[j].GetDouble();
		if (x >= simp->shapes.size()) return false;
		pairs.push_back(std::make_pair(&simp->shapes[x], y));
	}

	if (!val[0u].IsString()) return false;
	std::string name(val[0u].GetString());
	
	ProgType interp = ProgType::spline;

	if (val.Size() > 3){
		if (!val[3].IsString()) return false;
		std::string interpStr = val[3].GetString();
		if (interpStr == "linear") {
			interp = ProgType::linear;
		}
	}
	simp->progs.push_back(Progression(name, pairs, interp));
	return true;
}

bool Progression::parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp){
	if (!val.IsObject()) return false;

	CHECK_JSON_STRING(nameIt, "name", val);
	CHECK_JSON_ARRAY(pairsIt, "pairs", val);
	CHECK_JSON_STRING(interpIt, "interp", val);

	std::string name(nameIt->value.GetString());

	std::string interpStr(interpIt->value.GetString());
	ProgType interp = ProgType::spline;
	if (interpStr == "linear")
		interp = ProgType::linear;
	else if (interpStr == "splitspline")
		interp = ProgType::splitSpline;

	ProgPairs pairs;

	auto &pairsVal = pairsIt->value;
	for (auto it = pairsVal.Begin(); it != pairsVal.End(); ++it){
		auto &ival = *it;
		if (!ival.IsArray()) return false;
		if (!ival[0].IsInt()) return false;
		if (!ival[1].IsDouble()) return false;

		size_t x = (size_t)ival[0].GetInt();
		double y = (double)ival[1].GetDouble();

		if (x >= simp->shapes.size()) return false;
		pairs.push_back(std::make_pair(&simp->shapes[x], y));
	}
	simp->progs.push_back(Progression(name, pairs, interp));
	return true;
}

bool Progression::parseJSONv3(const rapidjson::Value &val, size_t index, Simplex *simp){
	return parseJSONv2(val, index, simp);
}


