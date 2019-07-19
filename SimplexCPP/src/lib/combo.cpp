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

#include "enums.h"
#include "utils.h"
#include "shapeController.h"
#include "slider.h"
#include "combo.h"
#include "floater.h"
#include "simplex.h"

#include "rapidjson/rapidjson.h"
#include "math.h"

#include <algorithm> // for sort
#include <limits>    // for numeric_limits

using namespace simplex;
class simplex::Progression;


bool simplex::solveState(const std::vector<double> &vals, const std::vector<double> &tars, ComboSolve solveType, bool exact, double &value) {
	double mn, mx, allMul = 1.0, allSum = 0.0;
	mn = std::numeric_limits<double>::infinity();
	mx = -mn;

	for (size_t i = 0; i < vals.size(); ++i){
		double val = vals[i];
		double tar = tars[i];

		// Specifically this instead of isNegative()
		// because isNegative returns true for 0.0
		bool valNeg = !isPositive(val);
		bool tarNeg = !isPositive(tar);

		if (valNeg != tarNeg) return false;
		if (valNeg) val = -val;

		val = (val > MAXVAL) ? MAXVAL : val;
		allMul *= val;
		allSum += val;
		if (val < mn) mn = val;
		if (val > mx) mx = val;
	}

	switch (solveType) {
	case ComboSolve::min:
		value = (exact) ? mn : doSoftMin(mx, mn);
		break;
	case ComboSolve::allMul:
		value = allMul;
		break;
	case ComboSolve::extMul:
		value = mx * mn;
		break;
	case ComboSolve::mulAvgExt:
		if (isZero(mx + mn))
			value = 0.0;
		else
			value = 2 * (mx * mn) / (mx + mn);
		break;
	case ComboSolve::mulAvgAll:
		if (isZero(allSum))
			value = 0.0;
		else
			value = vals.size() * allMul / allSum;
		break;
	case ComboSolve::None:
		value = (exact) ? mn : doSoftMin(mx, mn);
		break;
	default:
		value = (exact) ? mn : doSoftMin(mx, mn);
	}
	return true;
}

bool simplex::solveState(const ComboPairs &stateList, ComboSolve solveType, bool exact, double &value) {
	std::vector<double> vals, tars;
	for (auto sit = stateList.begin(); sit != stateList.end(); ++sit) {
		//for (const auto &state: stateList){
		const auto &state = *sit;
		vals.push_back(state.first->getValue());
		tars.push_back(state.second);
	}
	return simplex::solveState(vals, tars, solveType, exact, value);
}

ComboSolve simplex::getSolveType(const rapidjson::Value &val) {
	ComboSolve solveType = ComboSolve::None;
	auto solveIt = val.FindMember("solveType");
	if (solveIt != val.MemberEnd()) {
		if (!solveIt->value.IsString()) {
			solveType = ComboSolve::None;
		}
		else {
			std::string solve(solveIt->value.GetString());
			if (solve == "min")
				solveType = ComboSolve::min;
			else if (solve == "allMul")
				solveType = ComboSolve::allMul;
			else if (solve == "extMul")
				solveType = ComboSolve::extMul;
			else if (solve == "mulAvgExt")
				solveType = ComboSolve::mulAvgExt;
			else if (solve == "mulAvgAll")
				solveType = ComboSolve::mulAvgAll;
			else if (solve == "None")
				solveType = ComboSolve::None;
			else
				solveType = ComboSolve::None;
		}
	}
	return solveType;
}

bool simplex::getSolvePairs(const rapidjson::Value &val, Simplex *simp, ComboPairs &state, bool &isFloater) {
	for (auto it = val.Begin(); it != val.End(); ++it) {
		auto &ival = *it;
		if (!ival.IsArray()) return false;
		if (!ival[0].IsInt()) return false;
		if (!ival[1].IsDouble()) return false;

		size_t slidx = (size_t)ival[0].GetInt();
		double slval = (double)ival[1].GetDouble();
		if (!floatEQ(fabs(slval), 1.0, EPS) && !isZero(slval))
			isFloater = true;
		if (slidx >= simp->sliders.size()) return false;
		state.push_back(std::make_pair(&simp->sliders[slidx], slval));
	}
	return true;
}

Combo::Combo(const std::string &name, Progression* prog, size_t index,
	const ComboPairs &stateList, bool isFloater, ComboSolve solveType) :
	ShapeController(name, prog, index), stateList(stateList), isFloater(isFloater), solveType(solveType), exact(true) {
	std::sort(this->stateList.begin(), this->stateList.end(),
		[](const ComboPair &lhs, const ComboPair &rhs) {
		return lhs.first->getIndex() < rhs.first->getIndex();
	}
	);
	std::vector<double> rawVec;
	for (auto pit = this->stateList.begin(); pit != this->stateList.end(); ++pit) {
		//for (auto &p : this->stateList) {
		auto &p = *pit;
		rawVec.push_back(p.second);
	}
	rectify(rawVec, rectified, clamped, inverted);
}

void Combo::storeValue(
	const std::vector<double> &values,
	const std::vector<double> &posValues,
	const std::vector<double> &clamped,
	const std::vector<bool> &inverses) {

	if (!enabled) return;
	if (isFloater) return;
	solveState(stateList, solveType, exact, value);
}

bool Combo::parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp) {
	if (!val[0u].IsString()) return false;
	if (!val[1].IsInt()) return false;
	const rapidjson::Value &jcstate = val[2];
	ComboPairs state;

	bool isFloater = false;
	rapidjson::SizeType j;
	for (j = 0; j < jcstate.Size(); ++j) {
		if (!jcstate[j][0u].IsInt()) return false;
		if (!jcstate[j][1].IsNumber()) return false;
		size_t slidx = (size_t)jcstate[j][0u].GetInt();
		double slval = jcstate[j][1].GetDouble();

		if (!floatEQ(fabs(slval), 1.0, EPS) && !isZero(slval))
			isFloater = true;

		if (slidx >= simp->sliders.size()) return false;
		state.push_back(std::make_pair(&simp->sliders[slidx], slval));
	}

	std::string name(val[0u].GetString());
	size_t pidx = (size_t)val[1].GetInt();
	if (pidx >= simp->progs.size()) return false;
	if (isFloater)
		simp->floaters.push_back(Floater(name, &simp->progs[pidx], index, state, isFloater));
	simp->combos.push_back(Combo(name, &simp->progs[pidx], index, state, isFloater, ComboSolve::None));
	return true;
}

bool Combo::parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp) {
	if (!val.IsObject()) return false;
	CHECK_JSON_STRING(nameIt, "name", val);
	CHECK_JSON_INT(progIt, "prog", val);
	CHECK_JSON_ARRAY(pairsIt, "pairs", val);

	std::string name(nameIt->value.GetString());

	ComboSolve solveType = getSolveType(val);
	ComboPairs state;
	bool isFloater = false;
	auto &pairsVal = pairsIt->value;
	if (!getSolvePairs(pairsVal, simp, state, isFloater)) return false;

	size_t pidx = (size_t)progIt->value.GetInt();
	if (pidx >= simp->progs.size()) return false;

	bool enabled = getEnabled(val);

	if (isFloater) {
		simp->floaters.push_back(Floater(name, &simp->progs[pidx], index, state, isFloater));
		simp->floaters.back().setEnabled(enabled);
	}
	// because a floater is still considered a combo
	// I need to add it to the list for indexing purposes

	simp->combos.push_back(Combo(name, &simp->progs[pidx], index, state, isFloater, solveType));
	simp->combos.back().setEnabled(enabled);
	return true;
}

bool Combo::parseJSONv3(const rapidjson::Value &val, size_t index, Simplex *simp) {
	return parseJSONv2(val, index, simp);
}

