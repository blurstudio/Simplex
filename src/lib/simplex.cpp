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

using namespace simplex;

using std::vector;
using std::pair;
using std::make_pair;
using std::string;
using std::unordered_set;
using std::unordered_map;
using std::array;
using std::min;
using std::max;


double softMin(double X, double Y) {
	if (isZero(X) || isZero(Y)) return 0.0;
	if (X < Y) std::swap(X, Y);

	double n = 4.0;
	double h = 0.025;
	double p = 2.0;
	double q = 1.0 / p;

	double d = 2.0 * (powf(1.0 + h, q) - powf(h, q));
	double s = powf(h, q);
	double z = powf(powf(X, p) + h, q) + powf(powf(Y, p) + h, q) - powf(powf(X - Y, p) + h, q);
	return (z - s) / d;
}



/* * CLASS SHAPE * */
bool Shape::parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp){
	if(!val.IsString()) return false;
	string name(val.GetString());
	simp->shapes.push_back(Shape(name, index));
	return true;
}

bool Shape::parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp){
	if (!val.IsObject()) return false;

	auto nameIt = val.FindMember("name");
	if (nameIt == val.MemberEnd()) return false;
	if (!nameIt->value.IsString()) return false;

	string name(nameIt->value.GetString());
	simp->shapes.push_back(Shape(name, index));
	return true;
}



/* * CLASS PROGRESSION * */
size_t Progression::getInterval(double tVal, const vector<double> &times) const{
	if (times.size() <= 1){
		return 0;
	}
	else if (tVal >= times[times.size() - 2]){
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

vector<pair<Shape*, double> > Progression::getSplineOutput(double tVal, double mul) const{
	if (
		(pairs.size() <= 2) ||
		(tVal < pairs[0].second) && (tVal > pairs[pairs.size()-1].second)
	){
		return getLinearOutput(tVal);
	}

	vector<Shape*> shapes;
	vector<double> st;
	for (auto it = pairs.begin(); it != pairs.end(); ++it){
		shapes.push_back(it->first);
		st.push_back(it->second);
	}
	size_t interval = getInterval(tVal, st);
	vector<pair<Shape*, double> > out;

	double start = st[interval];
	double end = st[interval + 1];

	//# compute the catmull-rom basis multipliers
	double x = (tVal - start) / (end - start);
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
	return out;
}

vector<pair<Shape*, double> > Progression::getLinearOutput(double tVal, double mul) const{
	vector<pair<Shape*, double> > out;
	vector<double> times;
	for (auto it=pairs.begin(); it!=pairs.end(); ++it){
		times.push_back(it->second);
	}
	size_t idx = getInterval(tVal, times);
	double u = (tVal - times[idx]) / (times[idx+1] - times[idx]);
    out.push_back(std::make_pair(pairs[idx].first, mul * (1.0-u)));
	out.push_back(std::make_pair(pairs[idx+1].first, mul * u));
	return out;
}

vector<pair<Shape*, double> > Progression::getOutput(double tVal, double mul) const{
	if (interp == ProgType::spline)
		return getSplineOutput(tVal, mul);
	else // if (interp == ProgType::linear)
		return getSplineOutput(tVal, mul);
}

bool Progression::parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp){
	if (!val.IsArray()) return false;

	vector<pair<Shape*, double> > pairs;
	const rapidjson::Value &jindices = val[1];
	const rapidjson::Value &jweights = val[2];
	if (!jweights.IsArray() || !jindices.IsArray()) return false;

	rapidjson::SizeType j;
	for (j = 0; j<jindices.Size(); ++j){
		if (!jindices.IsInt()) return false;
		if (!jweights.IsNumber()) return false;
		size_t x = (size_t)jindices[j].GetInt();
		double y = (double)jweights[j].GetDouble();
		if (x >= simp->shapes.size()) return false;
		pairs.push_back(make_pair(&simp->shapes[x], y));
	}

	if (!val[0u].IsString()) return false;
	string name(val[0u].GetString());
	
	ProgType interp = ProgType::spline;

	if (val.Size() > 3){
		if (!val[3].IsString()) return false;
		string interpStr = val[3].GetString();
		if (interpStr == "linear") {
			interp = ProgType::linear;
		}
	}
	simp->progs.push_back(Progression(name, pairs, interp));
	return true;
}

bool Progression::parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp){
	if (!val.IsObject()) return false;

	auto nameIt = val.FindMember("name");
	if (nameIt == val.MemberEnd()) return false;
	if (!nameIt->value.IsString()) return false;

	auto pairsIt = val.FindMember("pairs");
	if (pairsIt == val.MemberEnd()) return false;
	if (!pairsIt->value.IsArray()) return false;

	auto interpIt = val.FindMember("interp");
	if (interpIt == val.MemberEnd()) return false;
	if (!interpIt->value.IsString()) return false;

	string name(nameIt->value.GetString());

	string interpStr(nameIt->value.GetString());
	ProgType interp = ProgType::spline;
	if (interpStr == "linear") interp = ProgType::linear;

	vector<pair<Shape*, double> > pairs;

	auto &pairsVal = pairsIt->value;
	for (auto it = pairsVal.Begin(); it != pairsVal.End(); ++it){
		auto &ival = *it;
		if (!ival.IsArray()) return false;
		if (!ival[0].IsInt()) return false;
		if (!ival[1].IsDouble()) return false;

		size_t x = (size_t)ival[0].GetInt();
		double y = (double)ival[1].GetDouble();

		if (x >= simp->shapes.size()) return false;
		pairs.push_back(make_pair(&simp->shapes[x], y));
	}
	simp->progs.push_back(Progression(name, pairs, interp));
	return true;
}

/* * CLASS SHAPE CONTROLLER * */
void ShapeController::solve(std::vector<double> &accumulator) const {
	vector<pair<Shape*, double> > shapeVals = prog->getOutput(value, multiplier);
	for (const auto &svp: shapeVals){
		accumulator[svp.first->getIndex()] += svp.second;
	}
}


/* * CLASS SLIDER * */
bool Slider::parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp){
	if (!val[0u].IsString()) return false;
	if (!val[1].IsInt()) return false;

	string name(val[0u].GetString()); // needs to be 0u
	size_t slidx = size_t(val[1].GetInt());

	if (slidx >= simp->progs.size()) return false;
	simp->sliders.push_back(Slider(name, &simp->progs[slidx], index));
	return true;
}

bool Slider::parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp){
	if (!val.IsObject()) return false;

	auto nameIt = val.FindMember("name");
	if (nameIt == val.MemberEnd()) return false;
	if (!nameIt->value.IsString()) return false;

	auto progIt = val.FindMember("prog");
	if (progIt == val.MemberEnd()) return false;
	if (!progIt->value.IsInt()) return false;

	string name(nameIt->value.GetString());
	size_t slidx = size_t(progIt->value.GetInt());
	
	if (slidx >= simp->progs.size()) return false;
	simp->sliders.push_back(Slider(name, &simp->progs[slidx], index));
	return true;
}


/* * CLASS COMBO * */
void Combo::storeValue(
		const std::vector<double> &values,
		const std::vector<double> &posValues,
		const std::vector<double> &clamped,
		const std::vector<bool> &inverses){

	if (isFloater) return;
	double mn, mx;
	mn = std::numeric_limits<double>::infinity();
	mx = -mn;

	for (const auto &state: stateList){
		double val = state.first->getValue();
		if (!isPositive(val)) {
			if (inverses[state.first->getIndex()]) return;
			val = -val;
		}
		val = (val > MAXVAL) ? MAXVAL : val;

		//double pval = val / state.second;
		if (val < mn) mn = val;
		if (val > mx) mx = val;
	}
	value = (exact) ? mn : softMin(mx, mn);
}

bool Combo::parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp){
	if (!val[0u].IsString()) return false;
	if (!val[1].IsInt()) return false;
	const rapidjson::Value &jcstate = val[2];
	vector<pair<Slider*, double> > state;
	
	bool isFloater = false;
	rapidjson::SizeType j;
	for (j = 0; j<jcstate.Size(); ++j){
		if (!jcstate[j][0u].IsInt()) return false;
		if (!jcstate[j][1].IsNumber()) return false;
		size_t slidx = (size_t) jcstate[j][0u].GetInt();
		double slval = jcstate[j][1].GetDouble();

		if (!floatEQ(fabs(slval), 1.0, EPS) && !isZero(slval))
			isFloater = true;

		if (slidx >= simp->sliders.size()) return false;
		state.push_back(make_pair(&simp->sliders[slidx], slval));
	}

	string name(val[0u].GetString());
	size_t pidx = (size_t)val[1].GetInt();
	if (pidx >= simp->progs.size()) return false;
	if (isFloater)
		simp->floaters.push_back(Floater(name, &simp->progs[pidx], index, state, isFloater));
	simp->combos.push_back(Combo(name, &simp->progs[pidx], index, state, isFloater));
	return true;
}

bool Combo::parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp){
	if (!val.IsObject()) return false;

	auto nameIt = val.FindMember("name");
	if (nameIt == val.MemberEnd()) return false;
	if (!nameIt->value.IsString()) return false;

	auto progIt = val.FindMember("prog");
	if (progIt == val.MemberEnd()) return false;
	if (!progIt->value.IsInt()) return false;

	auto pairsIt = val.FindMember("pairs");
	if (pairsIt == val.MemberEnd()) return false;
	if (!pairsIt->value.IsArray()) return false;

	string name(nameIt->value.GetString());

	vector<pair<Slider*, double> > state;
	bool isFloater = false;
	auto &pairsVal = pairsIt->value;
	for (auto it = pairsVal.Begin(); it != pairsVal.End(); ++it){
		auto &ival = *it;
		if (!ival.IsArray()) return false;
		if (!ival[0].IsInt()) return false;
		if (!ival[1].IsDouble()) return false;

		size_t slidx = (size_t)ival[0].GetInt();
		double slval = (double)ival[1].GetDouble();
		if (!floatEQ(fabs(slval), 1.0, EPS) && !isZero(slval))
			isFloater = true;
		if (slidx >= simp->sliders.size()) return false;
		state.push_back(make_pair(&simp->sliders[slidx], slval));
	}

	size_t pidx = (size_t)progIt->value.GetInt();
	if (pidx >= simp->progs.size()) return false;
	if (isFloater)
		simp->floaters.push_back(Floater(name, &simp->progs[pidx], index, state, isFloater));
	// because a floater is still considered a combo
	// I need to add it to the list for indexing purposes
	simp->combos.push_back(Combo(name, &simp->progs[pidx], index, state, isFloater));
	return true;
}



/* * CLASS TRAVERSAL * */
bool Traversal::parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp){
	if (!val[0u].IsString()) return false;
	if (!val[1].IsInt()) return false;
	if (!val[2].IsString()) return false;
	if (!val[3].IsInt()) return false;
	if (!val[4].IsString()) return false;
	if (!val[5].IsInt()) return false;

	string name(val[0u].GetString()); // needs to be 0u
	size_t progIdx = (size_t)val[1].GetInt();
	string pctype(val[2].GetString());
	size_t pcidx = (size_t)val[3].GetInt();
	string mctype(val[4].GetString());
	size_t mcidx = (size_t)val[5].GetInt();

	ShapeController *pcItem;
	if (!pctype.empty() && pctype[0] == 's') {
		if (pcidx >= simp->sliders.size()) return false;
		pcItem = &simp->sliders[pcidx];
	}
	else {
		if (pcidx >= simp->combos.size()) return false;
		pcItem = &simp->combos[pcidx];
	}

	ShapeController *mcItem;
	if (!mctype.empty() && mctype[0] == 'c') {
		if (mcidx >= simp->sliders.size()) return false;
		mcItem = &simp->sliders[mcidx];
	}
	else {
		if (mcidx >= simp->combos.size()) return false;
		mcItem = &simp->combos[mcidx];
	}

	if (progIdx >= simp->progs.size()) return false;
	simp->traversals.push_back(Traversal(name, &simp->progs[progIdx], index, pcItem, mcItem));
	return true;
}

bool Traversal::parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp){
	if (!val.IsObject()) return false;

	auto nameIt = val.FindMember("name");
	if (nameIt == val.MemberEnd()) return false;
	if (!nameIt->value.IsString()) return false;

	auto progIt = val.FindMember("prog");
	if (progIt == val.MemberEnd()) return false;
	if (!progIt->value.IsInt()) return false;

	auto ptIt = val.FindMember("progressType");
	if (ptIt == val.MemberEnd()) return false;
	if (!ptIt->value.IsString()) return false;

	auto pcIt = val.FindMember("progressControl");
	if (pcIt == val.MemberEnd()) return false;
	if (!pcIt->value.IsInt()) return false;

	auto mtIt = val.FindMember("multiplierType");
	if (mtIt == val.MemberEnd()) return false;
	if (!mtIt->value.IsString()) return false;

	auto mcIt = val.FindMember("multiplierControl");
	if (mcIt == val.MemberEnd()) return false;
	if (!mcIt->value.IsInt()) return false;

	string name(nameIt->value.GetString());
	size_t pidx = (size_t)progIt->value.GetInt();
	string pctype(ptIt->value.GetString());
	string mctype(mtIt->value.GetString());
	size_t pcidx = (size_t)pcIt->value.GetInt();
	size_t mcidx = (size_t)mcIt->value.GetInt();
	

	ShapeController *pcItem;
	if (!pctype.empty() && pctype[0] == 's') {
		if (pcidx >= simp->sliders.size()) return false;
		pcItem = &simp->sliders[pcidx];
	}
	else {
		if (pcidx >= simp->combos.size()) return false;
		pcItem = &simp->combos[pcidx];
	}

	ShapeController *mcItem;
	if (!mctype.empty() && mctype[0] == 's') {
		if (mcidx >= simp->sliders.size()) return false;
		mcItem = &simp->sliders[mcidx];
	}
	else {
		if (mcidx >= simp->combos.size()) return false;
		mcItem = &simp->combos[mcidx];
	}

	if (pidx >= simp->progs.size()) return false;
	simp->traversals.push_back(Traversal(name, &simp->progs[pidx], index, pcItem, mcItem));
	return true;
}


/* * CLASS SIMPLEX * */
void Simplex::clearValues(){
	for (auto &x : sliders) x.clearValue();
	for (auto &x : combos) x.clearValue();
	for (auto &x : floaters) x.clearValue();
	for (auto &x : traversals) x.clearValue();
}

void Simplex::setExactSolve(bool exact){
	for (auto &x : combos) x.setExact(exact);
}

std::vector<double> Simplex::solve(const std::vector<double> &vec){
	// The solver should simply follow this pattern:
	// Ask each top level thing to store its value
	// Ask each shape controller for its contribution to the output
	std::vector<double> posVec, clamped, output;
	std::vector<bool> inverses;
	rectify(vec, posVec, clamped, inverses);
	for (auto &x : sliders)
		x.storeValue(vec, posVec, clamped, inverses);
	for (auto &x : combos)
		x.storeValue(vec, posVec, clamped, inverses);
	for (auto &x : spaces)
		x.storeValue(vec, posVec, clamped, inverses);
	for (auto &x : traversals)
		x.storeValue(vec, posVec, clamped, inverses);
	
	output.resize(shapes.size());

	for (auto &x : sliders) x.solve(output);
	for (auto &x : combos) x.solve(output);
	for (auto &x : floaters) x.solve(output);
	for (auto &x : traversals) x.solve(output);

	return output;
}

Simplex::Simplex(const string &json){
	parseJSON(json);
}

Simplex::Simplex(const char *json){
	parseJSON(string(json));
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
		if (version == 2)
			ret = Shape::parseJSONv2(jshapes[i], (size_t)i, this);
		else
			ret = Shape::parseJSONv1(jshapes[i], (size_t)i, this);
		if (!ret) return false;
	}

	for (i = 0; i<jprogs.Size(); ++i){
		if (version == 2)
			ret = Progression::parseJSONv2(jprogs[i], (size_t)i, this);
		else
			ret = Progression::parseJSONv1(jprogs[i], (size_t)i, this);
		if (!ret) return false;
	}

	for (i = 0; i<jsliders.Size(); ++i){
		if (version == 2)
			ret = Slider::parseJSONv2(jsliders[i], (size_t)i, this);
		else
			ret = Slider::parseJSONv1(jsliders[i], (size_t)i, this);
		if (!ret) return false;
	}

	if (d.HasMember("combos")){
		const rapidjson::Value &jcombos = d["combos"];
		if (!jcombos.IsArray()) return false;
		for (i = 0; i<jcombos.Size(); ++i){
			if (version == 2)
				ret = Combo::parseJSONv2(jcombos[i], (size_t)i, this);
			else
				ret = Combo::parseJSONv1(jcombos[i], (size_t)i, this);
			if (!ret) return false;
		}
	}

	if (d.HasMember("traversals")){
		const rapidjson::Value &jtravs = d["traversals"];
		if (!jtravs.IsArray()) return false;
		for (i = 0; i<jtravs.Size(); ++i){
			if (version == 2)
				ret = Traversal::parseJSONv2(jtravs[i], (size_t)i, this);
			else
				ret = Traversal::parseJSONv1(jtravs[i], (size_t)i, this);
			if (!ret) return false;
		}
	}

	loaded = true;
	return true;
}

bool Simplex::parseJSON(const string &json){
	// Make sure when getting the 0 index from a rapidjson Value
	// always use rapidjson::SizeType, or 0u because the compiler
	// can't decide between 0 and a null string
	built = false;
	
	rapidjson::Document d;
	d.Parse<0>(json.c_str());

	hasParseError = false;
	if (d.HasParseError()){
		hasParseError = true;
		parseError = string(rapidjson::GetParseError_En(d.GetParseError()));
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
}

