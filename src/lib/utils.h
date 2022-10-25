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

#include <vector>
#include <type_traits>  // for hash
#include "rapidjson/document.h"
#include "math.h"

#define CHECK_JSON_STRING(jsIt, jsName, jsVal) \
	auto (jsIt) = (jsVal).FindMember(jsName); \
	if ((jsIt) == (jsVal).MemberEnd()) return false; \
	if (!(jsIt)->value.IsString()) return false;

#define CHECK_JSON_BOOL(jsIt, jsName, jsVal) \
	auto (jsIt) = (jsVal).FindMember(jsName); \
	if ((jsIt) == (jsVal).MemberEnd()) return false; \
	if (!(jsIt)->value.IsBool()) return false;

#define CHECK_JSON_INT(jsIt, jsName, jsVal) \
	auto (jsIt) = (jsVal).FindMember(jsName); \
	if ((jsIt) == (jsVal).MemberEnd()) return false; \
	if (!(jsIt)->value.IsInt()) return false;

#define CHECK_JSON_ARRAY(jsIt, jsName, jsVal) \
	auto (jsIt) = (jsVal).FindMember(jsName); \
	if ((jsIt) == (jsVal).MemberEnd()) return false; \
	if (!(jsIt)->value.IsArray()) return false;


namespace simplex {
const double EPS = 1e-6;
const int ULPS = 4;
const double MAXVAL = 1.0; // max clamping value

inline bool floatEQ(const double A, const double B, const double eps) {
	// from https://randomascii.wordpress.com/2012/01/11/tricks-with-the-floating-point-format
	// Check if the numbers are really close -- needed
	// when comparing numbers near zero.
	double absDiff = fabs(A - B);
	if (absDiff <= eps)
		return true;
	return false;
}

inline bool isZero(const double a) { return floatEQ(a, 0.0, EPS); }
inline bool isPositive(const double a) { return a > -EPS; }
inline bool isNegative(const double a) { return a < EPS; }

void rectify(
		const std::vector<double> &rawVec,
		std::vector<double> &values,
		std::vector<double> &clamped,
		std::vector<bool> &inverses
);

double doSoftMin(double X, double Y);

template <typename T>
struct vectorHash {
	size_t operator()(const std::vector<T> & val) const {
		// this is the python tuple hashing algorithm
		size_t value = 0x345678;
		size_t vSize = val.size();
		std::hash<T> iHash;
		for (auto i = val.begin(); i != val.end(); ++i) {
			value = (1000003 * value) ^ iHash(*i);
			value = value ^ vSize;
		}
		return value;
	}
};

} // namespace simplex
