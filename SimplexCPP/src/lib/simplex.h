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
enum ProgType {linear, spline, centripetal};
static double const EPS = 1e-6;
static int const ULPS = 4;

bool floatEQ(const double A, const double B, const double eps=EPS);


template <typename T>
struct vectorHash{
	size_t operator()(const std::vector<T> & val) const {
		// this is the python tuple hashing algorithm
		size_t value = 0x345678;
		size_t vSize = val.size();
		std::hash<T> iHash;
		for (auto i = val.begin(); i != val.end(); ++i){
			value = (1000003 * value) ^ iHash(*i);
			value = value ^ vSize;
		}
		return value;
	}
};

class ShapeBase {
	protected:
		void *shapeRef; // pointer to whatever the user wants
		std::string name;
		std::string _overrideSide;
		std::string _side;
		std::string getRealSide(void);
	public:
		ShapeBase(void);
		explicit ShapeBase(const std::string &name);
		std::string getName(void) const;
		void forceSide(const std::string &side);
		std::string getSide(void) const;
		bool isForced(void) const;
		void setUserData(void *data);
		void* getUserData(void);
};

class Shape : public ShapeBase {
	protected:
		size_t index;
	public:
		Shape(void);
		Shape(const std::string &name, size_t index);
		size_t getIndex(void) const;
};

class Progression : public ShapeBase {
	private:
		std::vector<std::pair<Shape*, double> > pairs;
		std::string interp;
	public:
		bool isSimpleProg;
		Progression(void);
		Progression(const std::string &name, const std::vector<std::pair<Shape*, double> > &pairs, const std::string &interp);
		size_t getInterval(double tVal, const std::vector<double> &times) const;
		size_t shapeCount(void);
		std::vector<std::pair<Shape*, double> > getSplineOutput(double tVal) const;
		std::vector<std::pair<Shape*, double> > getShapeValues(double tVal) const;
		void setTimes(const std::vector<double> &newTimes);
		void centripetalCRBasisValues(double tVal, double a0, double a1, double a2, double a3, double alpha,
															double &v1, double &v2, double &v3, double &v4) const;
		void centripetalCRTimes(const std::vector<double> &timeList, size_t index,
													  double &t0, double &t1, double &t2, double &t3) const;
};

class Simplex;

class ShapeController : public ShapeBase {
	public:
		Simplex* solver;
		Progression* prog;
		ShapeController(void);
		ShapeController(const std::string &name, Progression* prog, Simplex* solver);
		size_t shapeCount(void);
};

class Slider : public ShapeController {
	public:
		Slider(void);
		Slider(const std::string &name, Progression* prog, Simplex* solver);
		bool split(std::vector<Slider> &out) const;

};

class Combo : public ShapeController {
	private:
		std::vector<std::pair<Slider*, double> > stateList;
	public:
		Combo(void);
		Combo(const std::string &name, Progression* progression, Simplex* solver, const std::vector<std::pair<Slider*, double> > &stateList);
		std::vector<double> getRow(const std::vector<Slider*>& sliders) const;
		std::vector<Combo> split(const std::vector< std::pair< Slider*, std::vector<Slider*> > > &splitList ) const;
		std::vector<double> mkPoint(const std::vector<Slider*> &sliderList) const;
};

class ShapeSpace {
	protected:
		std::vector<Slider*> sliders;
		std::vector<ShapeController*> progs;
		std::vector<Combo*> combos;
		std::vector<Shape*> shapes;
		std::vector<std::vector<double> > shapeMatrix;
		std::vector<size_t> shapeInfluenceCount;
		std::vector<std::vector<char> > shapeZeroMatrix;
		std::vector<char> shapeMidMatrix;

	public:
		ShapeSpace(void);
		void addItem(Combo* combo);
		void addItem(Slider* slider);
		void setShapes(std::vector<Shape> &inshapes);
		bool progTypeSlider(size_t idx) const;
		bool contains(const Combo &item) const;
		bool contains(const Slider &item) const;
};

class TriSpace : public ShapeSpace {
	private:
		std::vector<std::vector<int> > overrideSimplices;
		std::vector<std::vector<double> > userPoints;
		std::unordered_map<std::vector<int>, std::vector<std::vector<int> >, vectorHash<int> > simplexMap;
		bool triangulated;
		static void _rec(const std::vector<double> &point, const std::vector<int> &oVals, const std::vector<int> &simp, std::vector<std::vector<int> > &out, double eps);
	public:
		TriSpace(void);
		void triangulate(void);
		static std::vector<int> pointToSimp(const std::vector<double> &pt);
		static std::vector<std::vector<int> > pointToAdjSimp(const std::vector<double> &pt, double eps);

		std::vector<std::vector<double> > simplexToCorners(const std::vector<int> &simplex) const;
		std::vector<std::vector<double> > userSimplexToCorners(const std::vector<int> &simplex, const std::vector<int> &original) const;
		std::vector<double> barycentric(const std::vector<std::vector<double> > &simplex, const std::vector<double> &p) const;
		std::vector<std::vector<std::vector<double> > > splitSimps(const std::vector<std::vector<double> > &pts, const std::vector<std::vector<int> > &simps) const;
		std::vector<std::pair<std::vector<double>, double> > getUserValues(const std::vector<double> &vec) const;
};

class ControlSpace : public ShapeSpace {
	private:
		std::vector<TriSpace> triSpaces;
		std::vector<std::vector<size_t> > tsIndices;
		std::vector<std::vector<size_t> > subsetMatrix;
		bool triangulated;
        bool exactSolve;
	public:
		ControlSpace(void);
		void setExactSolve(bool exact);
		void triangulate(void);
		void triangulateOld(void);
		void clamp(const std::vector<double> &vec, std::vector<double> &cvector, std::vector<double> &rem, double& maxval) const;
		std::vector<double> getSubVector(const std::vector<double> &over, const std::vector<size_t> &idxList) const;
		std::vector<double> getSuperVector(const std::vector<double> &under, const std::vector<size_t> &idxList, size_t size) const;
		bool hasCommon(const std::unordered_set<size_t> &a, const std::unordered_set<size_t> &b) const;
		std::vector<std::pair<Shape*, double> > deltaSolver(const std::vector<double> &rawVec) const;
		double applyMask(const std::vector<double> &vec, const std::vector<double> &mask, bool allowNeg, bool exactSolve) const;
};

class Simplex {
	private:
		std::vector<Shape> shapes;
		std::vector<Progression> progs;
		std::vector<Slider> sliders;
		std::vector<Combo> combos;
		ControlSpace controlSpace;

		std::unordered_map<std::string, Progression*> progMap;
		std::unordered_map<std::string, Slider*> sliderMap;
		std::unordered_map<std::string, Shape*> shapeMap;
		std::unordered_map<std::string, Combo*> comboMap;
		bool exactSolve;

	public:
		// public variables
		bool built;
		bool loaded;
		bool hasParseError;

		std::string parseError;
		size_t parseErrorOffset;

		Simplex(void);
		explicit Simplex(const std::string &json);
		explicit Simplex(const char* json);

		void clear(void);
		bool parseJSON(const std::string &json);
		bool Simplex::parseJSONv1(const rapidjson::Document &d);
		bool Simplex::parseJSONv2(const rapidjson::Document &d);

		void buildControlSpace(void);
		std::vector<std::pair<Shape*, double> > getDeltaShapeValues(const std::vector<double> &vec);
		std::vector<double> getDeltaIndexValues(const std::vector<double> &vec);
		void splitSliders(void);

		Progression * duplicateProgression(Progression * p);
		void updateProgTimes(const std::string& name, const std::vector<double>& newTimes);

		size_t shapeLen(void) const;
		size_t progLen(void) const;
		size_t sliderLen(void) const;
		size_t comboLen(void) const;
		void setExactSolve(bool exact);
		bool getExactSolve() const;
};

} // end namespace simplex
