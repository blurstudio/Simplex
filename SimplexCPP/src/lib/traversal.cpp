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
#include "shapeController.h"
#include "slider.h"
#include "combo.h"
#include "traversal.h"
#include "simplex.h"

#include "rapidjson/document.h"

#include <vector>
#include <string>
#include <unordered_map>
#include <unordered_set>

using namespace simplex;

Traversal::Traversal(
		const std::string &name, Progression* prog, size_t index,
		ShapeController* progressCtrl, ShapeController* multiplierCtrl, bool valueFlip, bool multiplierFlip):
		ShapeController(name, prog, index), exact(true){

	if (multiplierCtrl->sliderType()) {
		multState.push_back(std::make_pair((Slider*)multiplierCtrl, multiplierFlip ? -1.0 : 1.0));
	}
	else {
		// loop over the combos. Also, multiplier flip should *never* be negative here
		Combo *cmb = (Combo *) multiplierCtrl;
		for (auto pairIt = cmb->stateList.begin(); pairIt != cmb->stateList.end(); ++pairIt){
			multState.push_back(std::make_pair(pairIt->first, pairIt->second));
		}
	}

	if (progressCtrl->sliderType()) {
		progStartState.push_back(std::make_pair((Slider*)progressCtrl, 0.0));
		progDeltaState.push_back(std::make_pair((Slider*)progressCtrl, valueFlip ? -1.0 : 1.0));
	}
	else {
		// loop over the combos. Also, multiplier flip should *never* be negative here
		Combo *cmb = (Combo *) progressCtrl;
		for (auto pairIt = cmb->stateList.begin(); pairIt != cmb->stateList.end(); ++pairIt){
			progStartState.push_back(std::make_pair(pairIt->first, 0.0));
			progDeltaState.push_back(std::make_pair(pairIt->first, pairIt->second));
		}
	}
}

Traversal::Traversal(
		const std::string &name, Progression* prog, size_t index,
		const ComboPairs &startPairs, const ComboPairs &endPairs, ComboSolve solveType):
		ShapeController(name, prog, index), exact(true){

	std::unordered_map<Slider*, double> startSliders, endSliders;
	std::unordered_set<Slider*> allSliders;

	for (size_t i=0; i<startPairs.size(); ++i){
		startSliders[startPairs[i].first] = startPairs[i].second;
		allSliders.insert(startPairs[i].first);
	}

	for (size_t i=0; i<endPairs.size(); ++i){
		endSliders[endPairs[i].first] = endPairs[i].second;
		allSliders.insert(endPairs[i].first);
	}

	for (auto sliIt = allSliders.begin(); sliIt != allSliders.end(); ++sliIt){
		
		auto &sli = *sliIt;
		auto startIt = startSliders.find(sli);
		auto endIt = endSliders.find(sli);

		if (startIt == startSliders.end()){
			// means slider exists in end, but not start
			progStartState.push_back(std::make_pair(sli, 0.0));
			progDeltaState.push_back(std::make_pair(sli, endIt->second));
		}
		else if (endIt == endSliders.end()){
			// means slider exists in start, but not end
			progStartState.push_back(std::make_pair(sli, startIt->second));
			progDeltaState.push_back(std::make_pair(sli, -startIt->second));
		}
		else {
			if (startIt->second == endIt->second){
				// if the values are the same, add it to the multiplier state
				multState.push_back(std::make_pair(sli, startIt->second));
			}
			else {
				// if the values are different, add them to ther respective states
				progStartState.push_back(std::make_pair(sli, startIt->second));
				progDeltaState.push_back(std::make_pair(sli, endIt->second - startIt->second));
			}
		}
	}
}

void Traversal::storeValue(
		const std::vector<double> &values,
		const std::vector<double> &posValues,
		const std::vector<double> &clamped,
		const std::vector<bool> &inverses) {

	if (!enabled) return;

	double mul = 0.0, val = 0.0;
	solveState(multState, solveType, exact, mul);

	std::vector<double> vals, tars;

	for (size_t i = 0; i < progStartState.size(); ++i) {
		vals.push_back(progStartState[i].first->getValue() - progStartState[i].second);
		tars.push_back(progDeltaState[i].second);
	}
	solveState(vals, tars, solveType, exact, val);

	value = val;
	multiplier = mul;
}

bool Traversal::parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp){
	return parseJSONv2(val, index, simp);
}

bool Traversal::parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp){
	if (!val.IsObject()) return false;

	CHECK_JSON_STRING(nameIt, "name", val)
	CHECK_JSON_INT(progIt, "prog", val)
	CHECK_JSON_STRING(ptIt, "progressType", val)
	CHECK_JSON_INT(pcIt, "progressControl", val)
	CHECK_JSON_BOOL(pfIt, "progressFlip", val)
	CHECK_JSON_STRING(mtIt, "multiplierType", val)
	CHECK_JSON_INT(mcIt, "multiplierControl", val)
	CHECK_JSON_BOOL(mfIt, "multiplierFlip", val)

	std::string name(nameIt->value.GetString());
	size_t pidx = (size_t)progIt->value.GetInt();
	std::string pctype(ptIt->value.GetString());
	std::string mctype(mtIt->value.GetString());
	size_t pcidx = (size_t)pcIt->value.GetInt();
	size_t mcidx = (size_t)mcIt->value.GetInt();
	bool pcFlip = pfIt->value.GetBool();
	bool mcFlip = mfIt->value.GetBool();

	ShapeController *pcItem;
	if (!pctype.empty() && pctype[0] == 'S') {
		if (pcidx >= simp->sliders.size()) return false;
		pcItem = &simp->sliders[pcidx];
	}
	else {
		if (pcidx >= simp->combos.size()) return false;
		pcItem = &simp->combos[pcidx];
	}

	ShapeController *mcItem;
	if (!mctype.empty() && mctype[0] == 'S') {
		if (mcidx >= simp->sliders.size()) return false;
		mcItem = &simp->sliders[mcidx];
	}
	else {
		if (mcidx >= simp->combos.size()) return false;
		mcItem = &simp->combos[mcidx];
	}

	if (pidx >= simp->progs.size()) return false;

	bool enabled = getEnabled(val);
	
	simp->traversals.push_back(Traversal(name, &simp->progs[pidx], index, pcItem, mcItem, pcFlip, mcFlip));
	simp->traversals.back().setEnabled(enabled);
	return true;
}

bool Traversal::parseJSONv3(const rapidjson::Value &val, size_t index, Simplex *simp){
	if (!val.IsObject()) return false;

	CHECK_JSON_STRING(nameIt, "name", val)
	CHECK_JSON_INT(progIt, "prog", val)
	CHECK_JSON_ARRAY(startIt, "start", val)
	CHECK_JSON_ARRAY(endIt, "end", val)

	ComboSolve solveType = getSolveType(val);

	bool isFloater = false;
	ComboPairs startPairs, endPairs;
	if (!getSolvePairs(startIt->value, simp, startPairs, isFloater)) return false;
	if (!getSolvePairs(endIt->value, simp, endPairs, isFloater)) return false;

	std::string name(nameIt->value.GetString());
	size_t pidx = (size_t)progIt->value.GetInt();
	if (pidx >= simp->progs.size()) return false;

	bool enabled = getEnabled(val);
	simp->traversals.push_back(Traversal(name, &simp->progs[pidx], index, startPairs, endPairs, solveType));
	simp->traversals.back().setEnabled(enabled);
	return true;
}
