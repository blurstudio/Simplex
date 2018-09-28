/*
class TriSpace {
	private:
		// Correlates the auto-generated simplex with the user-created simplices
		// resulting from the splitting procedure
		std::vector<std::pair<std::vector<int>, std::vector<std::vector<int>>>> simplexMap;
	
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



// Check if the stateList of one floater is equal to another
bool stateEq(std::vector<std::pair<Slider*, double>> lhs, std::vector<std::pair<Slider*, double>> rhs){
	for (size_t i=0; i<lhs.size(); ++i){
		// pointers compare equal if they point to the same object
		if (lhs[i].first != rhs[i].first) return false;
	}
	return true;
}

std::vector<TriSpace> TriSpace::buildSpaces(std::vector<Floater> &floaters){
	// group floaters by subspace dimension span
	std::vector<std::vector<Floater*>> dimmed;
	for (auto &floater : floaters){
		size_t sls = floater.stateList.size();
		if (sls > dimmed.size()) dimmed.resize(sls);
		dimmed[sls].push_back(&floater);
	}

	// Go through each dimension group and separate them by shared
	// sliders and directions
	std::vector<TriSpace> spaces;
	for (auto &dim : dimmed){
		std::vector<Floater*> bucket;
		std::vector<bool> used(dim.size());
		for (size_t i=0; i<dim.size(); ++i){
			if (used[i]) continue;
			used[i] = true;
			bucket.clear();
			bucket.push_back(dim[i]);

			for (size_t j=i+1; j<dim.size(); ++j){
				if (used[j]) continue;
				if (stateEq(dim[i]->stateList, dim[j]->stateList)){
					used[j] = true;
					bucket.push_back(dim[j]);
				}
			}
			spaces.push_back(TriSpace(bucket));
		}
	}
	return spaces;
}

TriSpace::TriSpace(std::vector<Floater*> floaters):floaters(floaters){
	triangulate();
}



void TriSpace::triangulate(){
	unordered_map<vector<int>, vector<vector<double>> ,vectorHash<int>> d;
	for (auto f : floaters){
		std::vector<double> userPoint;
		for (auto sp : f->stateList){
			userPoint.push_back(sp.first);
		}
		userPoints.push_back(userPoint);
		vector<vector<int>> rawSimps = pointToAdjSimp(userPoint);
		for (auto &rawSimp : rawSimps){
			d[rawSimp].push_back(userPoint);
		}
	}

	for (auto p : d){
		overrideSimplices.push_back(p.first);
		vector<vector<int>> singleSimp;
		singleSimp.push_back(p.first);
		auto ext = splitSimps(p.second, singleSimp);
		for (auto &userSimplex : ext){
			vector<int> newSimp;
			for (size_t cIdx=0; cIdx<userSimplex.size(); ++i){
				auto findIt = std::find(userPoints.begin(), userPoints.end(), userSimplex[cIdx]);
				if (findIt == userPoints.end()){ // not found
					newSimp.push_back(p.first[cIdx]);
				}
				else{
					size_t idx = findIt - userPoints.begin();
					newSimp.push_back(int(p.first.size() + idx));
				}
			}
			simplexMap[p.first].push_back(newSimp);
		}
	}
}

// TODO
void TriSpace::storeValue(
		const std::vector<double> &values,
		const std::vector<double> &posValues,
		const std::vector<double> &clamped,
		const std::vector<bool> &inverses){

	// All floats in a trispace share the same span, so I only need to check one of them





	// TODO: check that I'm actually supposed to be here
	// but if I am ...
	std::vector<double> vec; // the data I care about (from clamped) should be put in here

	vector<int> majorSimp = pointToSimp(vec);
	size_t c = simplexMap.count(majorSimp);
	if (c == 0) return;

	vector<vector<int>> &simps = simplexMap[majorSimp];

	for (auto &simp : simps){
		vector<vector<double>> expanded = userSimplexToCorners(simp, majorSimp);
		vector<double> b = barycentric(expanded, vec);
		if (std::all_of(b.begin(), b.end(), isPositive)){
			// TODO:
			// go through &simp to find values of user points
			// then set the value property directly on them from b
		}
	}
}

vector<vector<int> > TriSpace::pointToAdjSimp(const vector<double> &pt, double eps=0.01) {
	/*
		Search for simplices that are near the point
		This allows for splitting the simplex, or snapping a
		point to a nearby progression
	*/

	// Point, OrderedValues, CurrentSimplex, Output

	vector<vector<int> > out;
	vector<int> rn, simp;
	rn.resize(pt.size());
	for (int i=0; i<pt.size(); ++i){
		rn.push_back(i);
	}
	simp.push_back(0);
	TriSpace::_rec(pt, rn, simp, out, eps);
	return out;
}

void TriSpace::_rec(const vector<double> &point, const vector<int> &oVals, const vector<int> &simp, vector<vector<int> > &out, double eps) {
	if (point.empty()){
		out.push_back(simp);
		return;
	}

	double maxabs = fabs(point[0]);
	for (size_t i=0; i<point.size(); ++i){
		double aa = fabs(point[i]);
		if (aa > maxabs){
			maxabs = aa;
		}
	}

	vector<size_t> mxs;
	for (size_t i=0; i<point.size(); ++i){
		if (maxabs - fabs(point[i]) < eps){
			mxs.push_back(i);
		}
	}

	vector<double> subpoint;
	vector<int> subvals, nSimp;
	bool mvZero = isZero(maxabs);

	for (size_t i=0; i<mxs.size(); ++i){
		std::vector<int> searchDirection;
		// zero is both positive and negative
		// so I need to do both directions
		if (mvZero){
			searchDirection.push_back(-1); 
			searchDirection.push_back(1); 
		}
		else {
			int p = (isPositive(point[mx])) ? 1 : -1;
			searchDirection.push_back(p);
		}

		for (int direction : searchDirection){
			size_t mx = mxs[i];
			int newval = (oVals[mx] + 1) * direction;

			// Copy
			nSimp = simp;
			subpoint = point;
			subvals = oVals;

			nSimp.insert(nSimp.end(), newval);
			subpoint.erase(subpoint.begin()+mx);
			subvals.erase(subvals.begin()+mx);
			TriSpace::_rec(subpoint, subvals, nSimp, out, eps);
		}
	}
}

vector<double> TriSpace::barycentric(const vector<vector<double> > &simplex, const vector<double> &p) const{
	using namespace Eigen;

	vector<double> last = simplex.back();

	// lastVec = (p - last)
	VectorXd lastVec(p.size());
	for (size_t i=0; i<last.size(); ++i){
		lastVec(i) = p[i] - last[i];
	}

	// M = (s - last)[:-1].transpose()
	Eigen::MatrixXd M(simplex.size()-1,simplex.size()-1);
	for (size_t i=0; i<simplex.size()-1; ++i){ // [:-1]
		for (size_t j=0; j<simplex[i].size(); ++j){
			// transpose // ji = ij
			M(j,i) = simplex[i][j] - last[j];
		}
	}

	// solve for the coordinates
	VectorXd x = M.colPivHouseholderQr().solve(lastVec);
	double * outArray = x.data(); // x.data isn't a vector, so convert it
	vector<double> out(&outArray[0],&outArray[p.size()]);
	double sum = accumulate(out.begin(), out.end(), 0.0);
	out.push_back(1.0 - sum); // 1-sum = missing value
	return out;
}

vector<int> TriSpace::pointToSimp(const vector<double> &pt) {
	/*
		Each simplex can be represented as a permutation of [(+-)(i+1) for i in range(len(dim))]
		So I will encode these values by the pos/neg direction along a dimension number.
		We always start at 0, so that makes [0,-2,4,1,-3] a valid encoding

		The resultant simplex is called a "Schlafli Orthoscheme"
	*/
	vector<pair<int, double> > abspt;
	double v;
	int idx, i, n;
	for (i=0; i<pt.size(); ++i){
		v = pt[i];
		idx = i+1;
		n = !isPositive(v) ? -1 : 1;
		abspt.push_back(make_pair(idx*n, v*n));
	}
	std::sort(abspt.begin(), abspt.end(),
		[](const std::pair<int, double> &a, const std::pair<int, double> &b) {a.second < b.second; } );

	vector<int> out;
	out.push_back(0);
	for (i=int(abspt.size()); i>0; --i){
		out.push_back(abspt[i-1].first);
	}
	return out;
}

vector<vector<double> > TriSpace::userSimplexToCorners(const vector<int> &simplex, const vector<int> &original) const{
	vector<double> currVec (simplex.size()-1, 0.0);
	vector<vector<double> > out;
	for (size_t i=0; i<simplex.size(); ++i){
		int s = simplex[i];
		int os = original[i];
		if (s == 0){
			out.push_back(currVec);
			continue;
		}
		// get the user idx
		int idx = (s > 0)? s : -s;

		// get the original idx
		int oidx = (os > 0)? os : -os;
		double val = (os > 0)? 1.0 : -1.0;

		if (oidx != 0){	
			// keep track of where we *would* be normally
			// unless we're replacing the first item
			currVec[oidx-1] = val;
		}

		// if the user idx is too high
		if (idx >= simplex.size()){
			// grab a user point
			idx = idx - int(simplex.size());
			out.push_back(this->userPoints[idx]);
		}
		else {
			// get the currVec		
			out.push_back(currVec);
		}
	}
	return out;
}

