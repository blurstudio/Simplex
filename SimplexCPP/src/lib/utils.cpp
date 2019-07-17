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
#include "utils.h"
#include "math.h"
#include <utility>
#include <vector>
#include <string>

namespace simplex{

void rectify(
		const std::vector<double> &rawVec,
		std::vector<double> &values,
		std::vector<double> &clamped,
		std::vector<bool> &inverses
){
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

double doSoftMin(double X, double Y) {
	if (isZero(X) || isZero(Y)) return 0.0;
	if (X < Y) std::swap(X, Y);

	double n = 4.0;
	double h = 0.025;
	double p = 2.0;
	double q = 1.0 / p;

	double d = 2.0 * (pow(1.0 + h, q) - pow(h, q));
	double s = pow(h, q);
	double z = pow(pow(X, p) + h, q) + pow(pow(Y, p) + h, q) - pow(pow(X - Y, p) + h, q);
	return (z - s) / d;
}
} // namespace simplex
