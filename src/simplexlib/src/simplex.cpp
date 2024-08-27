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
#include "utils.h"
#include "simplex.h"

#include "rapidjson/error/en.h"
#include "rapidjson/rapidjson.h"

using namespace simplex;

void Simplex::clearValues(){
	for (auto xit = sliders.begin(); xit != sliders.end(); ++xit) { xit->clearValue(); }
	for (auto xit = combos.begin(); xit != combos.end(); ++xit) { xit->clearValue(); }
	for (auto xit = floaters.begin(); xit != floaters.end(); ++xit) { xit->clearValue(); }
	for (auto xit = traversals.begin(); xit != traversals.end(); ++xit) { xit->clearValue(); }

	//for (auto &x : sliders) x.clearValue();
	//for (auto &x : combos) x.clearValue();
	//for (auto &x : floaters) x.clearValue();
	//for (auto &x : traversals) x.clearValue();
}

void Simplex::setExactSolve(bool exact){
	for (auto xit = combos.begin(); xit != combos.end(); ++xit) { xit->setExact(exact); }
	//for (auto &x : combos) x.setExact(exact);
}

std::vector<double> Simplex::solve(const std::vector<double> &vec){
	// The solver should simply follow this pattern:
	// Ask each top level thing to store its value
	// Ask each shape controller for its contribution to the output
	std::vector<double> posVec, clamped, output;
	std::vector<bool> inverses;
	rectify(vec, posVec, clamped, inverses);


	for (auto xit = sliders.begin(); xit != sliders.end(); ++xit){
		xit->storeValue(vec, posVec, clamped, inverses);
	}
	for (auto xit = combos.begin(); xit != combos.end(); ++xit){
		xit->storeValue(vec, posVec, clamped, inverses);
	}
	for (auto xit = spaces.begin(); xit != spaces.end(); ++xit){
		xit->storeValue(vec, posVec, clamped, inverses);
	}
	for (auto xit = traversals.begin(); xit != traversals.end(); ++xit){
		xit->storeValue(vec, posVec, clamped, inverses);
	}

	/*
	for (auto &x : sliders)
		x.storeValue(vec, posVec, clamped, inverses);
	for (auto &x : combos)
		x.storeValue(vec, posVec, clamped, inverses);
	for (auto &x : spaces)
		x.storeValue(vec, posVec, clamped, inverses);
	for (auto &x : traversals)
		x.storeValue(vec, posVec, clamped, inverses);
	*/
	
	output.resize(shapes.size());
	double maxAct = 0.0;

	for (auto xit = sliders.begin(); xit != sliders.end(); ++xit)
		xit->solve(output, maxAct);
	for (auto xit = combos.begin(); xit != combos.end(); ++xit)
		xit->solve(output, maxAct);
	for (auto xit = floaters.begin(); xit != floaters.end(); ++xit)
		xit->solve(output, maxAct);
	for (auto xit = traversals.begin(); xit != traversals.end(); ++xit)
		xit->solve(output, maxAct);

	/*
	for (auto &x : sliders)
		x.solve(output, maxAct);
	for (auto &x : combos)
		x.solve(output, maxAct);
	for (auto &x : floaters)
		x.solve(output, maxAct);
	for (auto &x : traversals)
		x.solve(output, maxAct);
	*/

	// set the rest value properly
	if (!output.empty())
		output[0] = 1.0 - maxAct;
	return output;
}

Simplex::Simplex(const std::string &json){
	parseJSON(json);
}

Simplex::Simplex(const char *json){
	parseJSON(std::string(json));
}

bool Simplex::parseJSONversion(const rapidjson::Document &d, unsigned version){
	// Must have these
	if (!d.HasMember("shapes")) return false;
	if (!d.HasMember("progressions")) return false;
	if (!d.HasMember("sliders")) return false;

	const rapidjson::Value &jshapes = d["shapes"];
	const rapidjson::Value &jsliders = d["sliders"];
	const rapidjson::Value &jprogs = d["progressions"];

	if (!jshapes.IsArray()) return false;
	if (!jsliders.IsArray()) return false;
	if (!jprogs.IsArray()) return false;

	rapidjson::SizeType i;
	bool ret;
	for (i = 0; i<jshapes.Size(); ++i){
		if (version == 3)
			ret = Shape::parseJSONv3(jshapes[i], (size_t)i, this);
		else if (version == 2)
			ret = Shape::parseJSONv2(jshapes[i], (size_t)i, this);
		else
			ret = Shape::parseJSONv1(jshapes[i], (size_t)i, this);
		if (!ret)
			return false;
	}

	for (i = 0; i<jprogs.Size(); ++i){
		if (version == 3)
			ret = Progression::parseJSONv3(jprogs[i], (size_t)i, this);
		else if (version == 2)
			ret = Progression::parseJSONv2(jprogs[i], (size_t)i, this);
		else
			ret = Progression::parseJSONv1(jprogs[i], (size_t)i, this);
		if (!ret)
			return false;
	}

	for (i = 0; i<jsliders.Size(); ++i){
		if (version == 3)
			ret = Slider::parseJSONv3(jsliders[i], (size_t)i, this);
		else if (version == 2)
			ret = Slider::parseJSONv2(jsliders[i], (size_t)i, this);
		else
			ret = Slider::parseJSONv1(jsliders[i], (size_t)i, this);
		if (!ret)
			return false;
	}

	if (d.HasMember("combos")){
		const rapidjson::Value &jcombos = d["combos"];
		if (!jcombos.IsArray()) return false;
		for (i = 0; i<jcombos.Size(); ++i){
			if (version == 3)
				ret = Combo::parseJSONv3(jcombos[i], (size_t)i, this);
			else if (version == 2)
				ret = Combo::parseJSONv2(jcombos[i], (size_t)i, this);
			else
				ret = Combo::parseJSONv1(jcombos[i], (size_t)i, this);
			if (!ret)
				return false;
		}
	}

	if (d.HasMember("traversals")){
		const rapidjson::Value &jtravs = d["traversals"];
		if (!jtravs.IsArray()) return false;
		for (i = 0; i<jtravs.Size(); ++i){
			if (version == 3)
				ret = Traversal::parseJSONv3(jtravs[i], (size_t)i, this);
			else if (version == 2)
				ret = Traversal::parseJSONv2(jtravs[i], (size_t)i, this);
			else
				ret = Traversal::parseJSONv1(jtravs[i], (size_t)i, this);
			if (!ret)
				return false;
		}
	}

	loaded = true;
	return true;
}

bool Simplex::parseJSON(const std::string &json){
	// Make sure when getting the 0 index from a rapidjson Value
	// always use rapidjson::SizeType, or 0u because the compiler
	// can't decide between 0 and a null std::string
	built = false;
	
	rapidjson::Document d;
	d.Parse<0>(json.c_str());

	hasParseError = false;
	if (d.HasParseError()){
		hasParseError = true;
		parseError = std::string(rapidjson::GetParseError_En(d.GetParseError()));
		parseErrorOffset = d.GetErrorOffset();
		return false;
	}

	unsigned encoding = 1u;
	if (d.HasMember("encodingVersion")){
		const rapidjson::Value &ev = d["encodingVersion"];
		if (!ev.IsUint()) return false;
		encoding = ev.GetUint();
	}
	return parseJSONversion(d, encoding);
}

void Simplex::clear() {
	shapes.clear();
	progs.clear();
	sliders.clear();
	combos.clear();
	floaters.clear();
	spaces.clear();
	traversals.clear();

	built = false;
	loaded = false;
	hasParseError = false;
}

void Simplex::build() {
	spaces = TriSpace::buildSpaces(floaters);
	built = true;
}

