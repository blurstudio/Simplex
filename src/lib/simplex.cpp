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


bool floatEQ(const double A, const double B, const double eps) {
	// from https://randomascii.wordpress.com/2012/01/11/tricks-with-the-floating-point-format
	// Check if the numbers are really close -- needed
	// when comparing numbers near zero.
	double absDiff = fabs(A - B);
	if (absDiff <= eps)
		return true;
	return false;
}

bool isZero(const double a) { return floatEQ(a, 0.0, EPS); }
bool isPositive(const double a) { return a > -EPS; }
bool isNegative(const double a) { return a < EPS; }



double softMin(double X, double Y) {
	if (isZero(X) || isZero(Y)) {
		return 0.0;

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
		(pairs.size() <= 2) && 
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


/* * CLASS SHAPE CONTROLLER * */
void ShapeController::solve(std::vector<double> &accumulator) const {
	vector<pair<Shape*, double> > shapeVals = prog->getOutput(value, multiplier);
	for (const auto &svp: shapeVals){
		accumulator[svp.first->getIndex()] += svp.second;
	}
}


/* * CLASS COMBO * */
void Combo::storeValue(
		const std::vector<double> &values,
		const std::vector<double> &posValues,
		const std::vector<double> &clamped,
		const std::vector<bool> &inverses){

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
		double pval = val / clamped[state.first->getIndex()];
		if (pval < mn) mn = pval;
		if (pval > mx) mx = pval;
	}
	value = (exact) ? mn : softMin(mx, mn);
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

void Simplex::rectify(const std::vector<double> &rawVec, std::vector<double> &values, std::vector<double> &clamped, std::vector<bool> &inverses){
	// Rectifying just makes everything positive, keeps track of the inversion, and applies clamping
	values.resize(rawVec.size());
	clamped.resize(rawVec.size());
	inverses.resize(rawVec.size());
	for (size_t i=0; i<rawVec.size(); ++i){
		double v = rawVec[i];
		if (v < 0){
			v = -v;
			inverses[i] = true;
		}
		values[i] = v;
		clamped[i] = (v > MAXVAL) ? MAXVAL : v;
	}
}

std::vector<double> Simplex::solve(const std::vector<double> &vec){
	// The solver should simply follow this pattern:
	// Ask each top level thing to store its value
	// Ask each shape controller for its contribution to the output
	std::vector<double> posVec, clamped, output;
	std::vector<bool> inverses;
	rectify(vec, posVec, clamped, inverses);
	for (auto &x : sliders) x.storeValue(vec, posVec, clamped, inverses);
	for (auto &x : combos) x.storeValue(vec, posVec, clamped, inverses);
	for (auto &x : spaces) x.storeValue(vec, posVec, clamped, inverses);
	for (auto &x : traversals) x.storeValue(vec, posVec, clamped, inverses);
	
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

bool Simplex::parseJSONv1(const rapidjson::Document &d){
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

	rapidjson::SizeType i, j;
	for (i = 0; i<jshapes.Size(); ++i){
		if (!jshapes[i].IsString()) return false;
		string name(jshapes[i].GetString());
		shapes.push_back(Shape(name, (size_t)i));
	}

	for (i = 0; i<jprogs.Size(); ++i){
		if (!jprogs[i].IsArray()) return false;
		vector<pair<Shape*, double> > pairs;
		const rapidjson::Value &jindices = jprogs[i][1];
		const rapidjson::Value &jweights = jprogs[i][2];
		if (jweights.IsArray() && jindices.IsArray()){
			for (j = 0; j<jindices.Size(); ++j){
				if (!jindices.IsInt()) return false;
				if (!jweights.IsNumber()) return false;
				size_t x = (size_t)jindices[j].GetInt();
				double y = (double)jweights[j].GetDouble();
				if (x >= shapes.size()) return false;
				pairs.push_back(make_pair(&shapes[x], y));
			}

			if (!jprogs[i][0u].IsString()) return false;
			string name(jprogs[i][0u].GetString());
			
			ProgType interp = ProgType::spline;

			if (jprogs[i].Size() > 3){
				if (!jprogs[i][3].IsString()) return false;
				string interpStr = jprogs[i][3].GetString();
				if (interpStr == "linear") {
					interp = ProgType::linear;
				}
			}
			progs.push_back(Progression(name, pairs, interp));
		}
		else{
			return false;
		}
	}

	for (i = 0; i<jsliders.Size(); ++i){
		if (!jsliders[i][0u].IsString()) return false;
		if (!jsliders[i][1].IsInt()) return false;

		string name(jsliders[i][0u].GetString()); // needs to be 0u
		size_t slidx = size_t(jsliders[i][1].GetInt());
		if (slidx >= progs.size()) return false;

		sliders.push_back(Slider(name, &progs[slidx], (size_t)i));
	}

	if (d.HasMember("combos")){
		const rapidjson::Value &jcombos = d["combos"];
		if (!jcombos.IsArray()) return false;
		for (i = 0; i<jcombos.Size(); ++i){
			const rapidjson::Value &jcstate = jcombos[i][2];
			vector<pair<Slider*, double> > state;
			
			for (j = 0; j<jcstate.Size(); ++j){
				if (!jcstate[j][0u].IsInt()) return false;
				if (!jcstate[j][1].IsNumber()) return false;
				size_t slidx = (size_t) jcstate[j][0u].GetInt();
				double slval = jcstate[j][1].GetDouble();
				if (slidx >= sliders.size()) return false;
				state.push_back(make_pair(&sliders[slidx], slval));
			}

			if (!jcombos[i][0u].IsString()) return false;
			if (!jcombos[i][1].IsInt()) return false;

			string name(jcombos[i][0u].GetString());
			size_t pidx = (size_t)jcombos[i][1].GetInt();
			if (pidx >= progs.size) return false;
			combos.push_back(Combo(name, &progs[pidx], (size_t)i, state));
		}
	}

	if (d.HasMember("traversals")){
		const rapidjson::Value &jtravs = d["traversals"];
		if (!jtravs.IsArray()) return false;
		for (i = 0; i<jtravs.Size(); ++i){
			if (!jtravs[i][0u].IsString()) return false;
			if (!jtravs[i][1].IsInt()) return false;
			if (!jtravs[i][2].IsString()) return false;
			if (!jtravs[i][3].IsInt()) return false;
			if (!jtravs[i][4].IsString()) return false;
			if (!jtravs[i][5].IsInt()) return false;

			string name(jtravs[i][0u].GetString()); // needs to be 0u
			size_t progIdx = (size_t)jtravs[i][1].GetInt();
			string pctype(jtravs[i][2].GetString());
			size_t pcidx = (size_t)jtravs[i][3].GetInt();
			string mctype(jtravs[i][4].GetString());
			size_t mcidx = (size_t)jtravs[i][5].GetInt();

			ShapeController *pcItem;
			if (!pctype.empty() && pctype[0] == 's') {
				if (pcidx >= sliders.size()) return false;
				pcItem = &sliders[pcidx];
			}
			else {
				if (pcidx >= combos.size()) return false;
				pcItem = &combos[pcidx];
			}

			ShapeController *mcItem;
			if (!mctype.empty() && mctype[0] == 'c') {
				if (mcidx >= sliders.size()) return false;
				mcItem = &sliders[mcidx];
			}
			else {
				if (mcidx >= combos.size()) return false;
				mcItem = &combos[mcidx];
			}

			if (progIdx >= progs.size()) return false;
			traversals.push_back(Traversal(name, &progs[progIdx], (size_t)i, pcItem, mcItem));
		}
	}

	loaded = true;
	return true;
}

bool Simplex::parseJSONv2(const rapidjson::Document &d){
	if (!d.HasMember("shapes")) return false;
	if (!d.HasMember("progressions")) return false;
	if (!d.HasMember("sliders")) return false;

	const rapidjson::Value &jshapes = d["shapes"];
	const rapidjson::Value &jprogs = d["progressions"];
	const rapidjson::Value &jsliders = d["sliders"];

	if (!jshapes.IsArray()) return false;
	if (!jprogs.IsArray()) return false;
	if (!jsliders.IsArray()) return false;

	rapidjson::SizeType i;

	for (i = 0; i<jshapes.Size(); ++i){
        const auto &shapeVal = jshapes[i];

		if (!jshapes[i].IsObject()) return false;

        auto nameIt = jshapes[i].FindMember("name");
        if (nameIt == jshapes[i].MemberEnd()) return false;
        if (!nameIt->value.IsString()) return false;

        string name(nameIt->value.GetString());
		shapes.push_back(Shape(name, (size_t)i));
	}

	for (i = 0; i<jprogs.Size(); ++i){
        const auto &progVal = jprogs[i];

		if (!progVal.IsObject()) return false;

        auto nameIt = progVal.FindMember("name");
        if (nameIt == progVal.MemberEnd()) return false;
        if (!nameIt->value.IsString()) return false;

        auto pairsIt = progVal.FindMember("pairs");
        if (pairsIt == progVal.MemberEnd()) return false;
        if (!pairsIt->value.IsArray()) return false;

        auto interpIt = progVal.FindMember("interp");
        if (interpIt == progVal.MemberEnd()) return false;
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

			if (x >= shapes.size()) return false;
            pairs.push_back(make_pair(&shapes[x], y));
        }
        progs.push_back(Progression(name, pairs, interp));
    }

	for (i = 0; i<jsliders.Size(); ++i){
        const auto &sliVal = jsliders[i];
		if (!sliVal.IsObject()) return false;

        auto nameIt = sliVal.FindMember("name");
        if (nameIt == sliVal.MemberEnd()) return false;
        if (!nameIt->value.IsString()) return false;

        auto progIt = sliVal.FindMember("prog");
        if (progIt == sliVal.MemberEnd()) return false;
        if (!progIt->value.IsInt()) return false;

        string name(nameIt->value.GetString());
        size_t slidx = size_t(progIt->value.GetInt());
		
		if (slidx >= progs.size()) return false;
		sliders.push_back(Slider(name, &progs[slidx], (size_t)i));
    }

	if (d.HasMember("combos")){
		const rapidjson::Value &jcombos = d["combos"];
		if (!jcombos.IsArray()) return false;

		for (i = 0; i<jcombos.Size(); ++i){
			const auto &comboVal = jcombos[i];
			if (!comboVal.IsObject()) return false;

			auto nameIt = comboVal.FindMember("name");
			if (nameIt == comboVal.MemberEnd()) return false;
			if (!nameIt->value.IsString()) return false;

			auto progIt = comboVal.FindMember("prog");
			if (progIt == comboVal.MemberEnd()) return false;
			if (!progIt->value.IsInt()) return false;

			auto pairsIt = comboVal.FindMember("pairs");
			if (pairsIt == comboVal.MemberEnd()) return false;
			if (!pairsIt->value.IsArray()) return false;

			string name(nameIt->value.GetString());

			vector<pair<Slider*, double> > state;
			auto &pairsVal = pairsIt->value;
			for (auto it = pairsVal.Begin(); it != pairsVal.End(); ++it){
				auto &ival = *it;
				if (!ival.IsArray()) return false;
				if (!ival[0].IsInt()) return false;
				if (!ival[1].IsDouble()) return false;

				size_t x = (size_t)ival[0].GetInt();
				double y = (double)ival[1].GetDouble();
				if (x >= sliders.size()) return false;
				state.push_back(make_pair(&sliders[x], y));
			}
			
			size_t pidx = (size_t)progIt->value.GetInt();
			if (pidx >= progs.size()) return false;
			combos.push_back(Combo(name, &progs[pidx], (size_t)i, state));
		}
	}

	if (d.HasMember("traversals")){
		const rapidjson::Value &jtravs = d["traversals"];
		if (!jtravs.IsArray()) return false;

		for (i = 0; i<jtravs.Size(); ++i){
			const auto &travVal = jtravs[i];
			if (!travVal.IsObject()) return false;

			auto nameIt = travVal.FindMember("name");
			if (nameIt == travVal.MemberEnd()) return false;
			if (!nameIt->value.IsString()) return false;

			auto progIt = travVal.FindMember("prog");
			if (progIt == travVal.MemberEnd()) return false;
			if (!progIt->value.IsInt()) return false;

			auto ptIt = travVal.FindMember("progressType");
			if (ptIt == travVal.MemberEnd()) return false;
			if (!ptIt->value.IsString()) return false;

			auto pcIt = travVal.FindMember("progressControl");
			if (pcIt == travVal.MemberEnd()) return false;
			if (!pcIt->value.IsInt()) return false;

			auto mtIt = travVal.FindMember("multiplierType");
			if (mtIt == travVal.MemberEnd()) return false;
			if (!mtIt->value.IsString()) return false;

			auto mcIt = travVal.FindMember("multiplierControl");
			if (mcIt == travVal.MemberEnd()) return false;
			if (!mcIt->value.IsInt()) return false;

			string name(nameIt->value.GetString());
			size_t pidx = (size_t)progIt->value.GetInt();
			string pctype(ptIt->value.GetString());
			string mctype(mtIt->value.GetString());
			size_t pcidx = (size_t)pcIt->value.GetInt();
			size_t mcidx = (size_t)mcIt->value.GetInt();
			

			ShapeController *pcItem;
			if (!pctype.empty() && pctype[0] == 's') {
				if (pcidx >= sliders.size()) return false;
				pcItem = &sliders[pcidx];
			}
			else {
				if (pcidx >= combos.size()) return false;
				pcItem = &combos[pcidx];
			}

			ShapeController *mcItem;
			if (!mctype.empty() && mctype[0] == 'c') {
				if (mcidx >= sliders.size()) return false;
				mcItem = &sliders[mcidx];
			}
			else {
				if (mcidx >= combos.size()) return false;
				mcItem = &combos[mcidx];
			}

			if (pidx >= progs.size()) return false;
			traversals.push_back(Traversal(name, &progs[pidx], (size_t)i, pcItem, mcItem));
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

	unsigned encoding;
	if (d.HasMember("encodingVersion")){
		const rapidjson::Value &ev = d["encodingVersion"];
		if (!ev.IsUint()) return false;
		encoding = ev.GetUint();
	}
	else {
		encoding = 1u;
	}

	//if (!d.HasMember("shapes")) return false;
	//if (!d.HasMember("sliders")) return false;
	//if (!d.HasMember("combos")) return false;
	//if (!d.HasMember("progressions")) return false;

	if (encoding == 1u) {
		return parseJSONv1(d);
	}
	else if (encoding == 2u) {
		return parseJSONv2(d);
	}
	return false;
}



