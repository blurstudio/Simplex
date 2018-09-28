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

#include <string>
#include <vector>
#include <array>
#include <utility>
#include <algorithm>
#include <unordered_map>
#include <stdint.h>
#include <math.h>

#include <algorithm>
#include <numeric>
#include <unordered_set>

#include "rapidjson/document.h"
#include "rapidjson/error/en.h"
#include "Eigen/Dense"


namespace simplex {
//enum ProgType {linear, spline, centripetal, bezier, circular};
enum ProgType {linear, spline};
static double const EPS = 1e-6;
static int const ULPS = 4;
static double const MAXVAL = 1.0; // max clamping value

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


class Simplex;

class ShapeBase {
	protected:
		void *shapeRef; // pointer to whatever the user wants
		std::string name;
		size_t index;
	public:
		explicit ShapeBase(const std::string &name, size_t index): name(name), index(index), shapeRef(nullptr) {}
		explicit ShapeBase(const std::string &name): name(name), index(0u), shapeRef(nullptr) {}
		const std::string* getName() const {return &name;}
		const size_t getIndex() const { return index; }
		void setUserData(void *data) {shapeRef = data;}
		void* getUserData(){return shapeRef;}
};

class Shape : public ShapeBase {
	public:
		Shape(const std::string &name, size_t index): ShapeBase(name, index){}
		static bool parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp);
		static bool parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp);
};

class Progression : public ShapeBase {
	private:
		std::vector<std::pair<Shape*, double>> pairs;
		ProgType interp;
		size_t getInterval(double tVal, const std::vector<double> &times) const;
		std::vector<std::pair<Shape*, double>> getSplineOutput(double tVal, double mul=1.0) const;
		std::vector<std::pair<Shape*, double>> getLinearOutput(double tVal, double mul=1.0) const;
	public:
		std::vector<std::pair<Shape*, double>> getOutput(double tVal, double mul=1.0) const;

		Progression::Progression(const std::string &name, const std::vector<std::pair<Shape*, double> > &pairs, ProgType interp):
				ShapeBase(name), pairs(pairs), interp(interp) {
			std::sort(pairs.begin(), pairs.end(),
				[](const std::pair<Slider*, double> &a, const std::pair<Slider*, double> &b) {a.second < b.second; } );
		}
		static bool parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp);
		static bool parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp);
};

class ShapeController : public ShapeBase {
	protected:
		bool enabled;
		double value;
		double multiplier;
		Progression* prog;
	public:
		ShapeController(const std::string &name, Progression* prog, size_t index):
			ShapeBase(name, index), enabled(true), value(0.0), prog(prog) {}

		void clearValue(){value = 0.0; multiplier=1.0;}
		const double getValue() const { return value; }
		const double getMultiplier() const { return multiplier; }
		void setEnabled(bool enable){enabled = enable;}
		virtual void storeValue(
				const std::vector<double> &values,
				const std::vector<double> &posValues,
				const std::vector<double> &clamped,
				const std::vector<bool> &inverses) = 0;
		void solve(std::vector<double> &accumulator) const;
};

class Slider : public ShapeController {
	public:
		Slider(const std::string &name, Progression* prog, size_t index) : ShapeController(name, prog, index){}
		void storeValue(
				const std::vector<double> &values,
				const std::vector<double> &posValues,
				const std::vector<double> &clamped,
				const std::vector<bool> &inverses){
			this->value = values[this->index];
		}
		static bool parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp);
		static bool parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp);
};

class Combo : public ShapeController {
	private:
		bool isFloater;
		bool exact;
	protected:
		std::vector<std::pair<Slider*, double>> stateList;
	public:
		void setExact(bool e){exact = e;}
		Combo(const std::string &name, Progression* prog, size_t index,
				const std::vector<std::pair<Slider*, double>> &stateList, bool isFloater):
			ShapeController(name, prog, index), stateList(stateList), isFloater(isFloater){
			std::sort(this->stateList.begin(), this->stateList.end(),
				[](const std::pair<Slider*, double> &lhs, const std::pair<Slider*, double> &rhs) {
					return lhs.first->getIndex() < rhs.first->getIndex();
				}
			);
		}
		void storeValue(
				const std::vector<double> &values,
				const std::vector<double> &posValues,
				const std::vector<double> &clamped,
				const std::vector<bool> &inverses);
		static bool parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp);
		static bool parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp);
};

class Traversal : public ShapeController {
	private:
		ShapeController *progressCtrl;
		ShapeController *multiplierCtrl;
	public:
		Traversal(const std::string &name, Progression* prog, size_t index,
				ShapeController* progressCtrl, ShapeController* multiplierCtrl):
			ShapeController(name, prog, index), progressCtrl(progressCtrl), multiplierCtrl(multiplierCtrl){}
		void storeValue(
				const std::vector<double> &values,
				const std::vector<double> &posValues,
				const std::vector<double> &clamped,
				const std::vector<bool> &inverses){
			this->value = progressCtrl->getValue();
			this->multiplier = multiplierCtrl->getValue();
		}
		static bool parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp);
		static bool parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp);
};

class Floater : public Combo {
	public:
		friend class TriSpace; // lets the trispace set the value for this guy
		Floater(const std::string &name, Progression* prog, size_t index,
			const std::vector<std::pair<Slider*, double>> &stateList, bool isFloater) :
			Combo(name, prog, index, stateList, isFloater) {
		}
};


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


class TriSpace {
	private:
		// Correlates the auto-generated simplex with the user-created simplices
		// resulting from the splitting procedure
		std::unordered_map<std::vector<int>, std::vector<std::vector<int>>, vectorHash<int>> simplexMap;
		std::vector<std::vector<double>> userPoints;
	


		std::vector<Floater *> floaters;
		static std::vector<double> barycentric(const std::vector<std::vector<double>> &simplex, const std::vector<double> &p);
		static std::vector<std::vector<double>> simplexToCorners(const std::vector<int> &simplex);
		static std::vector<int> pointToSimp(const std::vector<double> &pt);
		static std::vector<std::vector<int>> pointToAdjSimp(const std::vector<double> &pt, double eps);
		void triangulate(); // convenience function for separating the data access from the actual math
		// Code to split a list of simplices by a list of points, only used in triangulate()
		std::vector<std::vector<std::vector<double>>> splitSimps(const std::vector<std::vector<double>> &pts, const std::vector<std::vector<int>> &simps) const;

		// break down the given simplex encoding to a list of corner points for the barycentric solver and
		// a correlation of the point index to the floater index (or size_t_MAX if invalid)
		void userSimplexToCorners(
				const std::vector<int> &simplex,
				const std::vector<int> &original,
				std::vector<std::vector<double>> out,
				std::vector<size_t> floaterCorners
				) const;
	public:
		// Take the non-related floaters and group them by shared span and orthant
		static std::vector<TriSpace> buildSpaces(std::vector<Floater> &floaters);
		TriSpace(std::vector<Floater*> floaters);
		void storeValue(
				const std::vector<double> &values,
				const std::vector<double> &posValues,
				const std::vector<double> &clamped,
				const std::vector<bool> &inverses);
};

class Simplex {
	private:
		bool exactSolve;
		static void rectify(const std::vector<double> &rawVec, std::vector<double> &values, std::vector<double> &clamped, std::vector<bool> &inverses);
	public:
		std::vector<Shape> shapes;
		std::vector<Progression> progs;
		std::vector<Slider> sliders;
		std::vector<Combo> combos;
		std::vector<Floater> floaters;
		std::vector<TriSpace> spaces;
		std::vector<Traversal> traversals;

		bool built;
		bool loaded;
		bool hasParseError;

		std::string parseError;
		size_t parseErrorOffset;
		const size_t sliderLen() const { return sliders.size(); }

		Simplex() {};
		explicit Simplex(const std::string &json);
		explicit Simplex(const char* json);

		void clearValues();
		void clear();
		bool parseJSON(const std::string &json);
		bool parseJSONversion(const rapidjson::Document &d, unsigned version);
		void build();

		void setExactSolve(bool exact);

		std::vector<double> solve(const std::vector<double> &vec);
};

} // end namespace simplex
