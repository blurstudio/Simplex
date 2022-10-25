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

#include "shapeBase.h"
#include "rapidjson/document.h"

#include <vector>
#include <string>

namespace simplex {

class Progression;

class ShapeController : public ShapeBase {
	protected:
		bool enabled;
		double value;
		double multiplier;
		Progression* prog;
	public:
		ShapeController(const std::string &name, Progression* prog, size_t index):
			ShapeBase(name, index), enabled(true), value(0.0), multiplier(1.0), prog(prog) {}

		virtual bool sliderType() const { return true; }
		void clearValue(){value = 0.0; multiplier=1.0;}
		const double getValue() const { return value; }
		const double getMultiplier() const { return multiplier; }
		void setEnabled(bool enable){enabled = enable;}
		virtual void storeValue(
				const std::vector<double> &values,
				const std::vector<double> &posValues,
				const std::vector<double> &clamped,
				const std::vector<bool> &inverses) = 0;
		void solve(std::vector<double> &accumulator, double &maxAct) const;
		static bool getEnabled(const rapidjson::Value &val);
};


}

