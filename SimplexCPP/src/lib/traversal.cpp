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

using namespace simplex;

void Traversal::storeValue(
		const std::vector<double> &values,
		const std::vector<double> &posValues,
		const std::vector<double> &clamped,
		const std::vector<bool> &inverses) {

	if (!enabled) return;
	double val = progressCtrl->getValue();
	double mul = multiplierCtrl->getValue();
	if (progressCtrl->sliderType()) {
		if (valueFlip != inverses[progressCtrl->getIndex()]) return;
		if (valueFlip) val = -val;
	}
	if (multiplierCtrl->sliderType()) {
		if (multiplierFlip != inverses[multiplierCtrl->getIndex()]) return;
		if (multiplierFlip) mul = -mul;
	}
	value = val;
	multiplier = mul;
}

bool Traversal::parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp){
	return parseJSONv2(val, index, simp);
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

	auto pfIt = val.FindMember("progressFlip");
	if (pfIt == val.MemberEnd()) return false;
	if (!pfIt->value.IsBool()) return false;

	auto mtIt = val.FindMember("multiplierType");
	if (mtIt == val.MemberEnd()) return false;
	if (!mtIt->value.IsString()) return false;

	auto mcIt = val.FindMember("multiplierControl");
	if (mcIt == val.MemberEnd()) return false;
	if (!mcIt->value.IsInt()) return false;

	auto mfIt = val.FindMember("multiplierFlip");
	if (mfIt == val.MemberEnd()) return false;
	if (!mfIt->value.IsBool()) return false;

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
		if (pcidx >= simp->sliders.size())
			return false;
		pcItem = &simp->sliders[pcidx];
	}
	else {
		if (pcidx >= simp->combos.size())
			return false;
		pcItem = &simp->combos[pcidx];
	}

	ShapeController *mcItem;
	if (!mctype.empty() && mctype[0] == 'S') {
		if (mcidx >= simp->sliders.size())
			return false;
		mcItem = &simp->sliders[mcidx];
	}
	else {
		if (mcidx >= simp->combos.size())
			return false;
		mcItem = &simp->combos[mcidx];
	}

	if (pidx >= simp->progs.size())
		return false;

	bool enabled = true;
	auto enIt = val.FindMember("enabled");
	if (enIt != val.MemberEnd()){
	    if (enIt->value.IsBool()){
			enabled = enIt->value.GetBool();
	    }
	}
	
	simp->traversals.push_back(Traversal(name, &simp->progs[pidx], index, pcItem, mcItem, pcFlip, mcFlip));
	simp->traversals.back().setEnabled(enabled);
	return true;
}

