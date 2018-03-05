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

/*
	Simplex v2.5 or The separation of Shape and Progression

	The simplex solver aims to be the most comprehensive combination system I can
    create. It also aims to be as general as possible, so it is structured as a library
    along with simple wrapper plugins that use the library.

	The idea came from a technical paper in the 2013 SIGGRAPH paper titled
	"Simplicial Interpolation for Animating the Hulk" by Julien Cohen Bengio and Rony
    Goldenthal. Unfortunately, the paper was not released (at least I couldn't find it),
    but I was lucky enough to be present at their talk.

	In their talk, they described a method of PSD wherein an artist could add a target
    shape for any pose.  This in itself is not surprising, we've had this with the
    Radial Basis Function for some time. However, with RBF you have to be careful with
    the number and placement of the samples, otherwise you can easily get wobbling.
	Instead, they took each input slider and set it up to control a dimension in a
    hyperspace. Then, each sample point would simply be an N-dimensional point in that
    space. After that, the space would be "triangulated" (the simplest shape in 2D is
    a triangle, in 3D is a tetrahedron, and in N-dim space is called a simplex).
	Once that setup was done, the animator could feed the system any N-dim point, and the
    barycentric weights of the simplex that contained that point would be returned. So
    each simplex corner was associated with a shape and a weight, and that was used to
    drive the PSD.
	There were some problems though. Anything higher than 3 dimensions was difficult for
    an artist to grasp, and anything higher than 6 proved incredibly difficult to find
    obtuse simplices that would form even with special tools written to find them. All
    interpolation was linear, and every corner of the space must be defined. Every
    simplex must be tested to see if it contains the animated point.

	The underlying idea was great, but I wanted something that would be easy enough for
    an artist in the general case, not require full definition, and allow for spline
    interpolation between multiple shapes.

	These were my ideas that led to the current system
	* Artists don't want to deal with weights in places like (0.244, 0.34, .88311),
	  they generally want to deal with extreme weights like (1.0, 1.0, 0.0, 1.0), and
      only then possibly an in-between shape like (1.0, 1.0, 0.0, 0.5) However, for
      technical artists, the power to place a shape anywhere must still be available,
      but it will not be the norm
	* Allowing for spline interpolation between shapes will reduce the need for many
	  "corner" points
	* An artist doesn't want to manually build a new "dimension" when a new control
      gets added to the rig.

    After much input from Clay Osmus, I have arrived at this current implementation.

    First, A "simple" blendshape value system is put into play based on the minimum
    value of all inputs. For any shapes defined at extremes, this is all that is
    computed.
    However, if an internal point is defined, I provide a default implicit
    triangulation of that point's hyperspace (what I MUCH later learned were called
    Schlafli Orthoschemes) which is then further refined based on any other points
    that live in that hyperspace. This means that an internal point that only activates
    with 3 sliders only has to deal with tetrahedra instead of a simplex in a crazy
    number of dimensions.
    During the solve phase, if that shape is activated, we supplement the 'extremes'
    shape with the delta based on a barycentric solve

    There is one big problem I'm left with: The simple solve uses a naiive min()
    approach. This can cause hitches and corners with some shapes.
    If you look in ControlSpace::applyMask, you'll see where I have been working
    on finding a fast smooth approximation of the min() function that will eliminate
    these corners.  However, I believe it will be necessary to add a switch between
    the exact and the smoothed solver.
*/

using namespace simplex;

using std::vector;
using std::pair;
using std::make_pair;
using std::string;
using std::unordered_set;
using std::unordered_map;
using std::array;


#define MIN(X, Y) ((X) < (Y) ? (X) : (Y))
#define MAX(X, Y) ((X) > (Y) ? (X) : (Y))

bool simplex::floatEQ(const double A, const double B, const double eps)
{
	// from https://randomascii.wordpress.com/2012/01/11/tricks-with-the-floating-point-format/
	// Check if the numbers are really close -- needed
	// when comparing numbers near zero.
	double absDiff = fabs(A - B);
	if (absDiff <= eps)
		return true;
	return false;
}

bool isZero(const double &a) { return floatEQ(a, 0.0); }
bool isPositive(const double &a) { return a > -EPS; }
bool isNegative(const double &a) { return a < EPS; }

template <class T> // so I can sort vector<pair<T, double> >
bool pairCompare(const pair<T, double> &left, const pair<T, double> &right){
	return left.second < right.second;
}

size_t influenceCount(const vector<double> &vec) {
	size_t out = 0;
	for (auto i = vec.begin(); i != vec.end(); ++i){
		if (!isZero(*i)){
			++out;
		}
	}
	return out;
}

vector<char> zeroRow(const vector<double> &vec, size_t &count) {
	vector<char> out;
	count = 0;
	for (auto i = vec.begin(); i != vec.end(); ++i){
		if (!isZero(*i)){
			out.push_back(0);
			++count;
		}
		else{
			out.push_back(1);
		}
	}
	return out;
}

char isMidShape(const vector<double> &vec){
	for (size_t i = 0; i < vec.size(); ++i){
		if (!(floatEQ(vec[i], 0.0) || floatEQ(abs(vec[i]), 1.0))){
			return 1;
		}
	}
	return 0;
}

bool hasSubset(const vector<double> &over, size_t overInfCount, const vector<double> &under, size_t underInfCount, const vector<char> &underZero){
	//if (over.empty() || under.empty()) return false;
	//if (over.size() != under.size()) return false;
	if (overInfCount == 0) return false;
	if (underInfCount > overInfCount) return false;

	if (overInfCount == 1){
		for (size_t i = 0; i<over.size(); ++i){
			//if (!isZero(under[i]) && !floatEQ(abs(under[i]), abs(over[i]))){
			if (!underZero[i] && !floatEQ(abs(under[i]), abs(over[i]))){
				return false;
			}
		}
	}
	else {
		for (size_t i = 0; i<over.size(); ++i){
			if (!underZero[i] && !floatEQ(under[i], over[i])){
				return false;
			}
		}
	}
	return true;
}


/* * CLASS SHAPE BASE * */

ShapeBase::ShapeBase()
	:name(""), _overrideSide(""), _side(""), shapeRef(NULL){}

ShapeBase::ShapeBase(const string &name):
name(name), _overrideSide(""), _side(""){
}

string ShapeBase::getName() const{
	return this->name;
}

void ShapeBase::forceSide(const string &side){
	this->_overrideSide = side;
}

bool ShapeBase::isForced() const{
	return !this->_overrideSide.empty();
}

string ShapeBase::getSide() const{
	if (this->isForced()){
		return this->_overrideSide;
	}
	return this->_side;
}

void ShapeBase::setUserData(void *data){
	this->shapeRef = data;
}

void* ShapeBase::getUserData(){
	return this->shapeRef;
}


/* * CLASS SHAPE * */

Shape::Shape():
ShapeBase(""), index(0){}

Shape::Shape(const string &name, size_t index):
ShapeBase(name), index(index){}

size_t Shape::getIndex() const{
	return this->index;
}


/* * CLASS PROGRESSION * */

Progression::Progression()
	:ShapeBase(""),isSimpleProg(true){}

Progression::Progression(const string &name, const vector<pair<Shape*, double> > &pairs, const string &interp):
ShapeBase(name), pairs(pairs), interp(interp) {
	std::sort(this->pairs.begin(), this->pairs.end(), pairCompare<Shape*>);
	this->isSimpleProg = false;
	for (auto p = this->pairs.begin(); p != this->pairs.end(); ++p){
		if (!isZero(fmod(p->second, 1.0))){
			return;
		}
	}
	this->isSimpleProg = true;
}

void Progression::centripetalCRBasisValues(double tVal, double a0, double a1, double a2, double a3, double alpha,
													double &v1, double &v2, double &v3, double &v4) const {
	/*
	So can we just call this magic? No? Ok
	Look up: http://en.wikipedia.org/wiki/Centripetal_Catmull%E2%80%93Rom_spline
	And look up Barry and Goldman's pyramidal formulation.
	Take those equations, and plug in the groups of substitutions from below (t01, t1v, etc)
	Then get out your favorite Computer Algegra System (sympy in my case), and expand the whole
	series of equations. Once that's done, find the terms that contain each of the four
	points, factor out the point, and return the terms as the outputs
	*/

	// alpha = 0.0: standard spline
	// alpha = 0.5: centripetal
	// alpha = 1.0: chordal
	double t0 = pow(a0, alpha);
	double t1 = pow(a1, alpha);
	double t2 = pow(a2, alpha);
	double t3 = pow(a3, alpha);

	double t0v = t0-tVal;
	double t1v = t1-tVal;
	double t2v = t2-tVal;
	double t3v = t3-tVal;

	double t01 = t1-t0;
	double t02 = t2-t0;
	double t12 = t2-t1;
	double t13 = t3-t1;
	double t23 = t3-t2;

	double t122 = t12 * t12;
	double t1v2 = t1v * t1v;
	double t2v2 = t2v * t2v;

	v1 = t1v*t2v2/(t01*t02*t12);
	v2 = -(t1v*t2v*t3v/(t122*t13) + t0v*t2v2/(t02*t122) + t0v*t2v2/(t01*t02*t12));
	v3 = t1v2*t3v/(t12*t13*t23) + t1v2*t3v/(t122*t13) + t0v*t1v*t2v/(t02*t122);
	v4 = -(t1v2*t2v/(t12*t13*t23));
}

void Progression::centripetalCRTimes(const vector<double> &timeList, size_t index,
											  double &t0, double &t1, double &t2, double &t3) const{
	size_t tls = timeList.size();
	if (index == 0){ // deal with input tangent
		t0 = 2*timeList[0] - timeList[1];
		t1 = timeList[0];
		t2 = timeList[1];
		t3 = timeList[2];
	}
	else if (index >= tls-2){ // deal with output tangent{}
		t0 = timeList[tls-3];
		t1 = timeList[tls-2];
		t2 = timeList[tls-1];
		t3 = 2*timeList[tls-1] - timeList[tls-2];
	}
	else {
		t0 = timeList[index-1];
		t1 = timeList[index];
		t2 = timeList[index+1];
		t3 = timeList[index+2];
	}
}

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

size_t Progression::shapeCount(){
	return this->pairs.size();
}

vector<pair<Shape*, double> > Progression::getSplineOutput(double tVal) const{
	vector<Shape*> shapes;
	vector<double> st;
	for (auto it = this->pairs.begin(); it != this->pairs.end(); ++it){
		shapes.push_back(it->first);
		st.push_back(it->second);
	}
	size_t interval = this->getInterval(tVal, st);
	vector<pair<Shape*, double> > out;

	double start = st[interval];
	double end = st[interval + 1];
	double v0, v1, v2, v3;

	//# compute the basis multipliers
	if (this->interp == "cetripetal") { // TODO make into enum
		double t0, t1, t2, t3;
		double alpha = 0.5;
		this->centripetalCRTimes(st, interval, t0, t1, t2, t3);
		this->centripetalCRBasisValues(tVal, t0, t1, t2, t3, alpha, v0, v1, v2, v3);
	}
	else {
		double x, x2, x3;
		x = (tVal - start) / (end - start);
		x2 = x*x;
		x3 = x2*x;
		v0 = (-0.5*x3 + 1.0*x2 - 0.5*x);
		v1 = (1.5*x3 - 2.5*x2 + 1.0);
		v2 = (-1.5*x3 + 2.0*x2 + 0.5*x);
		v3 = (0.5*x3 - 0.5*x2);
	}

	if (interval == 0) { // deal with input tangent
		out.push_back(std::make_pair(shapes[0], (v1 + v0 + v0)));
		out.push_back(std::make_pair(shapes[1], (v2 - v0)));
		out.push_back(std::make_pair(shapes[2], v3));
	}
	else if (interval == st.size() - 2) { // deal with output tangent
		out.push_back(std::make_pair(shapes[shapes.size() - 3], v0));
		out.push_back(std::make_pair(shapes[shapes.size() - 2], v1 - v3));
		out.push_back(std::make_pair(shapes[shapes.size() - 1], v2 + v3 + v3));
	}
	else {
		out.push_back(std::make_pair(shapes[interval - 1], v0));
		out.push_back(std::make_pair(shapes[interval + 0], v1));
		out.push_back(std::make_pair(shapes[interval + 1], v2));
		out.push_back(std::make_pair(shapes[interval + 2], v3));
	}
	return out;
}

vector<pair<Shape*, double> > Progression::getShapeValues(double tVal) const{
	// TODO make this work with the enum
	if (
		(this->pairs.size() > 2) && 
		(this->interp == "spline" || this->interp == "centripetal") &&
		// if the tVal is outside the spline curve, just use linear
		(tVal > this->pairs[0].second) && (tVal < this->pairs[this->pairs.size()-1].second)
	){
		return this->getSplineOutput(tVal);
	}

	vector<pair<Shape*, double> > out;
	if (this->pairs.size() <= 1){
		return out;
	}

	// linear
	vector<double> times;
	for (auto it=this->pairs.begin(); it!=this->pairs.end(); ++it){
		times.push_back(it->second);
	}

	size_t idx = this->getInterval(tVal, times);
	
	double num = tVal - times[idx];
	double denom = times[idx+1] - times[idx];
	double u = num / denom;
    out.push_back(std::make_pair(this->pairs[idx].first, (1.0-u)));
	out.push_back(std::make_pair(this->pairs[idx+1].first, u));
	return out;
}

void Progression::setTimes(const std::vector<double> &newTimes){
	if (this->pairs.size() == newTimes.size()){
		for (size_t i=0; i<this->pairs.size(); ++i){
			this->pairs[i].second = newTimes[i];		
		}
	}
}


/* * CLASS SHAPECONTROLLER * */

ShapeController::ShapeController()
	:ShapeBase(""), solver(NULL), prog(NULL){}

ShapeController::ShapeController(const string &name, Progression* prog, Simplex* solver):
ShapeBase(name), prog(prog), solver(solver){}

size_t ShapeController::shapeCount(){
	return prog->shapeCount(); // this->
}


/* * CLASS SLIDER * */

Slider::Slider(){
}

Slider::Slider(const string &name, Progression* prog, Simplex* solver):
ShapeController(name, prog, solver){}

bool Slider::split(vector<Slider> &out) const{
	out.clear();
	if (this->prog->getSide() == "X"){
		Slider lSide(this->getName(), this->prog, this->solver);
		Slider rSide(this->getName(), this->solver->duplicateProgression(this->prog), this->solver);
		lSide.forceSide("L");
		rSide.forceSide("R");
		out.push_back(lSide);
		out.push_back(rSide);
		return true;
	}
	out.push_back(*this);
	return false;
}


/* * CLASS COMBO * */

Combo::Combo(){
}

Combo::Combo(const string &name, Progression* progression, Simplex* solver, const vector<pair<Slider*, double> > &stateList):
ShapeController(name, progression, solver), stateList(stateList) {
}

vector<double> Combo::getRow(const vector<Slider*>& sliders) const{
	vector<double> newRow;
	size_t i;
	newRow.resize(sliders.size(), 0.0);
	for (auto it=this->stateList.begin(); it!=this->stateList.end(); ++it){ //  <Slider*, double>
		for (i=0; i<sliders.size(); ++i){
			if (sliders[i] == it->first){
				newRow[i] = it->second;
				break;
			}
		}
	}
	return newRow;
}

vector<Combo> Combo::split(const vector<pair<Slider*, vector<Slider*> > > &splitList ) const{
	// TODO, figure out a way to handle this with the new pointer-based setup
	vector< pair< Slider*, vector<Slider*> > > toSplit;
	vector<Combo> out;
	bool contained;
	for (auto it=splitList.begin(); it!=splitList.end(); ++it){
		contained = false;
		for (auto chk=this->stateList.begin(); chk!=this->stateList.end(); ++chk){
			if (it->first == chk->first){
				contained = true;
				break;
			}
		}
		if (contained){
			toSplit.push_back(*it);
		}
	}

	if (toSplit.empty()){
		out.push_back(*this);
		return out;
	}

	// check the sidedness of all non-center shapes
	// if everything is on one side, only use that side of the combo
	// eg. furrow_C*sneer_L*smile_L should only return: furrow_L*sneer_L*smile_L
	
	vector<string> allSides;
	//string curside = "";
	string curside = "N";
	bool hasL = false;
	bool hasR = false;
	
	for (auto it=this->stateList.begin(); it!=this->stateList.end(); ++it){
		allSides.push_back(it->first->getSide());
	}
	for (auto it=allSides.begin(); it!=allSides.end(); ++it){
		if (*it == "L") hasL = true;
		if (*it == "R") hasR = true;
	}
	
	if (hasL != hasR){
		if (hasL) curside = "L";
		if (hasR) curside = "R";
	}
	else if (hasL && hasR){
		// this is a symmetrical shape like: browDown * browFurrow * sneer_L * sneer_R
		// that means all split shapes need to be activated to work
		// eg: browDown_L * browDown_R * browFurrow_L * browFurrow_R * sneer_L * sneer_R
		// see below for output
		curside = "S";
	}
	
	std::vector<std::pair<Slider*, double> > lState (this->stateList);
	std::vector<std::pair<Slider*, double> > rState (this->stateList);

	//inputPoint
	if (curside == "L" || curside == "S" || curside == "N"){
		for (auto it=toSplit.begin(); it!=toSplit.end(); ++it){
			for (auto st=lState.begin(); st!=lState.end(); ++st){
				if (st->first == it->first){
					lState.erase(st);
					break;
				}
			}
		

			double stateVal = 0.0;
			for (auto st=this->stateList.begin(); st!=this->stateList.end(); ++st){
				if (st->first == it->first){
					stateVal = st->second;
					break;
				}
			}
			pair<Slider*, double> tempL (it->second[0], stateVal);
			lState.push_back(tempL);
		}
	}

	if (curside == "R" || curside == "S" || curside == "N"){
		for (auto it=toSplit.begin(); it!=toSplit.end(); ++it){
			for (auto st=rState.begin(); st!=rState.end(); ++st){
				if (st->first == it->first){
					rState.erase(st);
					break;
				}
			}
		
			double stateVal = 0.0;
			for (auto st=this->stateList.begin(); st!=this->stateList.end(); ++st){
				if (st->first == it->first){
					stateVal = st->second;
					break;
				}
			}

			pair<Slider*, double> tempR (it->second[1], stateVal);
			rState.push_back(tempR);
		}
	}

	if (curside == "S"){
		lState.insert(lState.end(), rState.begin(), rState.end());
		out.push_back( Combo(this->getName(), this->prog, this->solver, lState));
		return out;
	}

	Progression* lProg = this->prog;
	Progression* rProg = this->solver->duplicateProgression(this->prog);

	Combo comboL(this->getName(), lProg, this->solver, lState);
	Combo comboR(this->getName(), rProg, this->solver, rState);

	comboL.forceSide("L");
	comboR.forceSide("R");

	if (curside == "L"){
		out.push_back(comboL);
		return out;
	}

	if (curside == "R"){
		out.push_back(comboR);
		return out;
	}

	out.push_back(comboL);
	out.push_back(comboR);
	return out;
}

vector<double> Combo::mkPoint(const vector<Slider*> &sliderList) const{
	vector<double> comboPoint;
	bool found;
	size_t i, j;
	for (i=0; i<sliderList.size(); ++i){
		found = false;
		for (j=0; j<this->stateList.size(); ++j){
			if (sliderList[i] == this->stateList[j].first){
				found = true;
				comboPoint.push_back(this->stateList[j].second);
				break;
			}
		}
		if (!found){
			comboPoint.push_back(0.0);
		}
	}
	return comboPoint;
}


/* * CLASS SHAPESPACE * */

ShapeSpace::ShapeSpace(){
}

void ShapeSpace::addItem(Combo* combo){
	this->progs.push_back(combo);
	this->combos.push_back(combo);
	vector<double> newRow (this->sliders.size(), 0.0);
	vector<double> r = combo->getRow(this->sliders);

	size_t count;
	vector<char> zrow = zeroRow(r, count);
	this->shapeInfluenceCount.push_back(count);
	this->shapeZeroMatrix.push_back(zrow);
	this->shapeMatrix.push_back(r);
	this->shapeMidMatrix.push_back(isMidShape(r));
}

void ShapeSpace::addItem(Slider* slider){
	size_t sln = this->sliders.size();
	this->sliders.push_back(slider);

	vector<double> newRow (sln+1, 0.0);
	newRow[sln] = 1.0;
	for (auto it=this->shapeMatrix.begin(); it!=this->shapeMatrix.end(); ++it){
		it->push_back(0.0);
	}
	auto smPos = this->shapeMatrix.begin() + sln;
	this->shapeMatrix.insert(smPos, newRow);

	size_t count;
	vector<char> zrow = zeroRow(newRow, count);

	auto smiPos = this->shapeInfluenceCount.begin() + sln;
	this->shapeInfluenceCount.insert(smiPos, count);

	for (auto zm = this->shapeZeroMatrix.begin(); zm != this->shapeZeroMatrix.end(); ++zm){
		zm->push_back(1);
	}
	
	auto zrPos = this->shapeZeroMatrix.begin() + sln;
	this->shapeZeroMatrix.insert(zrPos, zrow);
	
	auto prPos = this->progs.begin() + sln;
	this->progs.insert(prPos, slider);
	

	auto msPos = this->shapeMidMatrix.begin() + sln;
	this->shapeMidMatrix.insert(msPos, isMidShape(newRow));
}

bool ShapeSpace::progTypeSlider(size_t idx) const{
	if (idx < this->sliders.size()){
		return true;
	}
	return false;
}

bool ShapeSpace::contains(const Combo &item) const{
	for (auto c=this->combos.begin(); c!=this->combos.end(); ++c){
		if (*c == &item){
			return true;
		}
	}
	return false;
}

bool ShapeSpace::contains(const Slider &item) const{
	for (auto s=this->sliders.begin(); s!=this->sliders.end(); ++s){
		if (*s == &item){
			return true;
		}
	}
	return false;
}

void ShapeSpace::setShapes(vector<Shape> &inshapes){
	this->shapes.clear();
	for (size_t i = 0; i < inshapes.size(); ++i){
		this->shapes.push_back( &(inshapes[i]) );
	}
}


/* * CLASS TRISPACE * */

TriSpace::TriSpace()
	:triangulated(false) {}

vector<int> TriSpace::pointToSimp(const vector<double> &pt) {
	/*
		Each simplex can be represented as a permutation of [(+-)(i+1) for i in range(len(dim))]
		So I will encode these values by the pos/neg direction along a dimension number.
		However, because I can't really deal with -0, I have to encode with dimNumber+1
		Making [-2,4,1,-3] a valid encoding

		The resultant simplex is called a "Schlafli Orthoscheme"
	*/

	vector<pair<int, double> > abspt;
	double v;
	int idx, i, n;
	for (i=0; i<pt.size(); ++i){
		v = pt[i];
		idx = i+1;
		n = isNegative(v) ? -1 : 1;
		abspt.push_back(make_pair(idx*n, v*n));
	}
	std::sort(abspt.begin(), abspt.end(), pairCompare<int>);
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
	//out.push_back(currVec);
	int i, idx, oidx, s, os;
	double val;
	for (i=0; i<simplex.size(); ++i){
		s = simplex[i];
		os = original[i];
		if (s == 0){
			out.push_back(currVec);
			continue;
		}
		// get the user idx
		idx = (s > 0)? s : -s;

		// get the original idx
		oidx = (os > 0)? os : -os;
		val = (os > 0)? 1.0 : -1.0;

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

vector<vector<double> > TriSpace::simplexToCorners(const vector<int> &simplex) const {
	vector<double> currVec (simplex.size()-1, 0.0);
	vector<vector<double> > out;
	//out.push_back(currVec);
	int i, idx, s;
	double val;
	for (i=0; i<simplex.size(); ++i){
		s = simplex[i];
		if (s == 0){
			out.push_back(currVec);
			continue;
		}
		idx = (s > 0)? s : -s;
		val = (s > 0)? 1.0 : -1.0;
		
		if (idx >= simplex.size()){
			idx = idx - int(simplex.size());
			out.push_back(this->userPoints[idx]);
		}
		else {
			currVec[idx-1] = val;
			out.push_back(currVec);
		}
	}
	return out;
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

vector<vector<vector<double> > > TriSpace::splitSimps(const vector<vector<double> > &pts, const vector<vector<int> > &simps) const{
	vector<vector<vector<double> > > out, tmpList;
	vector<double> p, bary; // barycentric coordinates
	vector<vector<double> > ns; // list of decoded corner points
	// pts // list of points to split on
	// simps // integer encoded simplices
	double b;
	size_t i, j, k;

	for (j=0; j<simps.size(); ++j){
		out.push_back(this->simplexToCorners(simps[j]));
	}

	for (i=0; i<pts.size(); ++i){
		p = pts[i];
		tmpList.clear();
		for (j=0; j<out.size(); ++j){
			bary = this->barycentric(out[j], p);
			if (std::all_of(bary.begin(), bary.end(), isPositive)){
				for (k=0; k<bary.size(); ++k){
					b = bary[k];
					if (!isZero(b)){
						ns = out[j];
						ns[k] = p;
						tmpList.push_back(std::move(ns));
					}
				}
			}
			else {
				tmpList.push_back(out[j]);
			}
		}
		out = tmpList;
	}
	return out;
}

void TriSpace::_rec(const vector<double> &point, const vector<int> &oVals, const vector<int> &simp, vector<vector<int> > &out, double eps) {
	if (point.empty()){
		out.push_back(simp);
		return;
	}

	size_t i, mx;
	double maxval, maxabs;
	maxval = point[0];
	maxabs = fabs(maxval);
	for (i=0; i<point.size(); ++i){
		if (fabs(point[i]) > maxabs){
			maxval = point[i];
			maxabs = fabs(maxval);
		}
	}

	vector<size_t> mxs;
	for (i=0; i<point.size(); ++i){
		if (maxabs - fabs(point[i]) < eps){
			mxs.push_back(i);
		}
	}

	vector<double> subpoint;
	vector<int> subvals, nSimp;
	int newval, j;
	if (isZero(maxval)){
		for (i=0; i<mxs.size(); ++i){
			// zero is both positive and negative
			// so I need to do both directions
			for (j=-1; j<2; j+=2){
				mx = mxs[i];
				newval = oVals[mx] + 1;
				newval *= j;

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
	else {
		for (i=0; i<mxs.size(); ++i){
			mx = mxs[i];
			newval = oVals[mx] + 1;
			if (!isPositive(point[mx])){
				newval *= -1;
			}
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

vector<vector<int> > TriSpace::pointToAdjSimp(const vector<double> &pt, double eps=0.01) {
	/*
		Search for simplices that are near the point
		This allows for splitting the simplex, or snapping a
		point to a nearby progression
	*/

	// Point, OrderedValues, CurrentSimplex, Output

	vector<vector<int> > out;
	vector<int> rn, simp;
	for (int i=0; i<pt.size(); ++i){
		rn.push_back(i);
	}
	simp.push_back(0);
	TriSpace::_rec(pt, rn, simp, out, eps);
	return out;
}

vector<pair<vector<double>, double> > TriSpace::getUserValues(const vector<double> &vec) const{
	vector<vector<int> > simps;
	vector<vector<double> > expandedSimp;
	vector<double> b;
	vector<pair<vector<double>, double> > out;

	vector<int> majorSimp = this->pointToSimp(vec);
	for (auto oSimp = this->overrideSimplices.begin(); oSimp != this->overrideSimplices.end(); ++oSimp){
		if (majorSimp == *oSimp){
			// gotta use .at for some reason
			simps = this->simplexMap.at(majorSimp);
			break;
		}
	}
	if (simps.empty()){
		return out;
	}

	for (auto simp = simps.begin(); simp != simps.end(); ++simp){
		expandedSimp = this->userSimplexToCorners(*simp, majorSimp);
		b = this->barycentric(expandedSimp, vec);
		if (std::all_of(b.begin(), b.end(), isPositive)){
			for (size_t i = 0; i<b.size(); ++i){
				if (isMidShape(expandedSimp[i])){ // only return the user point values
					out.push_back(make_pair(expandedSimp[i], b[i]));
				}
			}
			return out;
		}
	}
	return out;
}

void TriSpace::triangulate() {
	this->triangulated = true;
	double eps = 0.01;
	
	vector<vector<int> > rawSimps;
	
	unordered_map<vector<int>, vector<vector<double> > ,vectorHash<int> > d;

	// Grab all non-corner points
	for (auto v=this->shapeMatrix.begin(); v!=this->shapeMatrix.end(); ++v){
		for (auto i=v->begin(); i!=v->end(); ++i){
			if (!floatEQ(abs(*i), 1.0, eps*eps) && !floatEQ(abs(*i), 0.0, eps*eps)){
				this->userPoints.push_back(*v);	
				rawSimps = this->pointToAdjSimp(*v);
				// add the point to the simplex-keyed dict
				for (auto rawSimp=rawSimps.begin(); rawSimp!=rawSimps.end(); ++rawSimp){
					d[*rawSimp].push_back(*v);
				}
				break;
			}
		}
	}

	// now that I have all the simplices with their contained points, I can split them
	vector<vector<int> > singleSimp;
	vector<vector<vector<double> > > ext;
	
	vector<int> newSimp;
	size_t idx;

	//unordered_map<vector<int>, vector<vector<int> >, vectorHash<int> > simplexMap;

	//this->simplices.clear();
	this->simplexMap.clear();

	this->overrideSimplices.clear();
	for (auto p=d.begin(); p!=d.end(); ++p){
		this->overrideSimplices.push_back(p->first);

		// split the simplex by all of it's contained points
		singleSimp.clear();
		singleSimp.push_back(p->first);
		ext = this->splitSimps(p->second, singleSimp);
		// ext[simplexIdx][cornerIdx][valueIdx]

		// construct the new integer-encoding for each new simplex
		for (auto userSimplex=ext.begin(); userSimplex!=ext.end(); ++userSimplex){
			newSimp.clear();
			for (size_t cornerIdx=0; cornerIdx<userSimplex->size(); ++cornerIdx){
				auto findIt = std::find(this->userPoints.begin(), this->userPoints.end(), (*userSimplex)[cornerIdx]);
				if (findIt == this->userPoints.end()){ // not found
					newSimp.push_back(p->first[cornerIdx]);
				}
				else{
					idx = std::distance(this->userPoints.begin(), findIt);
					newSimp.push_back(int(p->first.size() + idx));
				}
			}
			//this->simplices.push_back(newSimp);
			this->simplexMap[p->first].push_back(newSimp);
		}
	}
}


/* * CLASS CONTROLSPACE * */

ControlSpace::ControlSpace()
	:triangulated(false){}

void ControlSpace::setExactSolve(bool exact){
	this->exactSolve = exact;
}

bool ControlSpace::hasCommon(const unordered_set<size_t> &a, const unordered_set<size_t> &b) const{
	for (auto i = a.begin(); i != a.end(); ++i){
		if (b.count(*i) != 0){
			return true;
		}
	}
	return false;
}

vector<array<size_t, 2> > getIndexRanges(const vector<double> *a){
	vector<array<size_t, 2> > aranges, acmp;
	double curVal;
	array<size_t, 2> minmax;
	size_t i;
	vector<pair<size_t, double> > azip;

	// zip the abs values of &a with it's enumeration and sort it
	for (i = 0; i<a->size(); ++i){
		azip.push_back(make_pair(i, fabs( (*a)[i] ) ));
	}
	sort(azip.begin(), azip.end(), pairCompare<size_t>);

	// Get the ranges for the a vector

	curVal = azip[0].second;
	minmax[0] = 0;
	for (i = 0; i<azip.size(); ++i){
		if (!floatEQ(curVal, azip[i].second)){
			minmax[1] = i - 1;
			aranges.push_back(minmax);
			minmax[0] = i;
			curVal = azip[i].second;
		}
	}
	minmax[1] = i - 1;
	aranges.push_back(minmax);

	// backfill the ranges into the cmp order
	size_t rindex = 0;
	acmp.resize(azip.size());
	for (i = 0; i<azip.size(); ++i){
		if (i<aranges[rindex][0] || i>aranges[rindex][1]){
			++rindex;
		}
		acmp[azip[i].first] = aranges[rindex];
	}
	return acmp;
}

bool orthoschemeMatch(const vector<double> *a, const vector<double> *b){
	vector<array<size_t, 2> > acmp, bcmp;
	acmp = getIndexRanges(a);
	bcmp = getIndexRanges(b);

	for (size_t i = 0; i<acmp.size(); ++i){
		if (acmp[i][1] < bcmp[i][0]) return false;
		if (bcmp[i][1] < acmp[i][0]) return false;
	}
	return true;
}

void rowCheck(size_t j, vector<unordered_set<size_t> > &indexSets, unordered_set<size_t> *&curRow, bool &found){
	size_t k;
	for (k = 0; k<indexSets.size(); ++k){
		if (indexSets[k].count(j)){
			indexSets[k].insert(curRow->begin(), curRow->end());
			curRow = &indexSets[k];
			curRow->insert(j);
			found = true;
			return;
		}
	}
	curRow->insert(j);
}

void ControlSpace::triangulate(){
	vector<unordered_set<size_t> > indexSets, leftover, groups;
	unordered_set<size_t> seed, used, keyset;
	size_t i, j;
	vector<size_t> floaterIdx;
	unordered_map < vector<size_t>, vector<size_t>, vectorHash<size_t> > sliderGroupingMap;

	// grab the floater points
	// and group the floaters by sliders used
	vector< vector<double>* > floaters;
	for (i = 0; i<this->shapeMatrix.size(); ++i){
		if (this->shapeMidMatrix[i]){
			floaters.push_back(&(this->shapeMatrix[i]));
			floaterIdx.push_back(i);
			keyset.clear();
			for (j = 0; j < this->shapeMatrix[i].size(); ++j){
				if (!isZero(this->shapeMatrix[i][j])){
					keyset.insert(j);
				}
			}
			vector<size_t> key;
			key.resize(keyset.size());
			key.assign(keyset.begin(), keyset.end());
			sort(key.begin(), key.end());
			
			sliderGroupingMap[key].push_back(i);
		}
	}

	/*
	// group the floaters by orthoscheme
	used.clear();
    bool found;
    unordered_set<size_t> *curRow;
	unordered_set<size_t> row;
	for (i = 0; i < floaters.size() - 1; ++i){
		row.clear();
		curRow = &row;
		found = false;
		rowCheck(i, indexSets, curRow, found);
    	for (j = i + 1; j < floaters.size(); ++j){
    		if (orthoschemeMatch(floaters[i], floaters[j])){
				rowCheck(j, indexSets, curRow, found);
			}
		}
		if (!found){
			indexSets.push_back(row);
		}
	}
	
	for (i = 0; i < indexSets.size(); ++i){
		row.clear();
		for (auto it = indexSets[i].begin(); it != indexSets[i].end(); ++it){
			row.insert(floaterIdx[*it]);
		}
		groups.push_back(row);
	}
	*/

	// Get slider indices	
	this->tsIndices.clear();
	this->triSpaces.clear();

	for (auto it = sliderGroupingMap.begin(); it != sliderGroupingMap.end(); ++it){
		vector<size_t> sliderIdx = it->first;
		vector<size_t> comboIdx = it->second;

		this->tsIndices.push_back(sliderIdx);

		TriSpace ts;
		for (i = 0; i < sliderIdx.size(); ++i){
			if (this->progTypeSlider(sliderIdx[i])){
				ts.addItem(this->sliders[sliderIdx[i]]);
			}
		}

		for (auto gi = comboIdx.begin(); gi != comboIdx.end(); ++gi){
			ts.addItem(this->combos[*gi - this->sliders.size()]);
		}

		ts.triangulate();
		this->triSpaces.push_back(std::move(ts));
	}

	this->triangulated = true;
}

void ControlSpace::clamp(const vector<double> &vec, vector<double> &cVector, vector<double> &rem, double &maxval) const{
	for (auto v=vec.begin(); v!=vec.end(); v++){
		if (*v > 1.0){
			maxval = MAX(maxval, *v);
			cVector.push_back(1.0);
			rem.push_back(*v - 1.0);
		}
		else if (*v < -1.0){
			maxval = MAX(maxval, -*v);
			cVector.push_back(-1.0);
			rem.push_back(*v + 1.0);
		}
		else {
			maxval = MAX(maxval, fabs(*v));
			cVector.push_back(*v);
			rem.push_back(0.0);
		}
	}
}

vector<double> ControlSpace::getSubVector(const vector<double> &over, const vector<size_t> &idxList) const{
	vector<double> out(idxList.size(), 0.0);
	for (size_t i=0; i<idxList.size(); ++i){
		out[i] = over[idxList[i]];
	}
	return out;
}

vector<double> ControlSpace::getSuperVector(const vector<double> &under, const vector<size_t> &idxList, size_t size) const{
	vector<double> out(size, 0.0);
	for (size_t i=0; i<idxList.size(); ++i){
		out[idxList[i]] = under[i];
	}
	return out;
}

double ControlSpace::applyMask(const vector<double> &vec, const vector<double> &mask, bool allowNeg, bool exactSolve) const{
	// This is where the actual condiditonal solve takes place
	vector<double> check;
	size_t i;
	double val, flip;

	flip = 1.0;
	for (i = 0; i < mask.size(); ++i){
		if (!isZero(mask[i])){
			// mask[i] will either be -1 or 1
			// Other values are handled in the n-space solver
			val = vec[i] * mask[i];
			if (allowNeg && (val < 0.0)){
				// Allow neg is only true for non-combos
				flip = -1.0;
				val = -val;
			}
			double mul = MAX(0.0, val);
			check.push_back(mul);
		}
	}
	if (check.size() == 0){
		return 0.0;
	}
	else if (check.size() == 1){
		// The only possibility if this is not a combo
		return check[0] * flip;
	}

	/*
	OK, here's the thing.
	The modeler wants *perfect* interpolation for ther process.
	However, animation doesn't care about getting exact numbers, they just care about making it look good

	Therefore:
	// TODO //
	Add an option to switch between the powf() "fuzzy" interpolation
	and the min() "exact" interpolation.
	Set exact interpolation for the modelers so they can do their job
	Set fuzzy interpolation for the animators so they don't get hitches
	*/

	double X = check[0];
	double Y = check[0];
	for (i = 1; i < check.size(); ++i){
		Y = MIN(Y, check[i]);
		X = MAX(X, check[i]);
	}
	if (isZero(X) || isZero(Y)) {
		return 0.0;
	}

    if (exactSolve) {
        return Y;
    }

	// Other possibilities
	// -log(exp(-X) + exp(-Y)) + log(exp(-X) + 1.0) + log(exp(-Y) + 1.0);

	double n = 4.0;
	double h = 0.025;
	double p = 2.0;
	double q = 1.0 / p;

	double d = 2.0 * (powf(1.0 + h, q) - powf(h, q));
	double s = powf(h, q);
	double z = powf(powf(X, p) + h, q) + powf(powf(Y, p) + h, q) - powf(powf(X - Y, p) + h, q);
	return (z - s) / d;

}

vector<pair<Shape*, double> > ControlSpace::deltaSolver(const std::vector<double> &rawVec) const{
	vector<double> inVector, rem, subVector, superVector;
	Progression * prog;
	vector<pair<Shape*, double> > out, ext; // (shapeIndex, factor)
	unordered_map<size_t, pair<Shape*, double> > idxMap;
	unordered_map<size_t, double> conds;
	vector<pair<vector<double>, double> > rawPairs;
	unordered_map<vector<double>, double, vectorHash<double> > valuePairs;
	double maxVal, maskVal;
	size_t i;
	
	this->clamp(rawVec, inVector, rem, maxVal); // output: inVector, rem
	size_t dim = inVector.size();

	// pass the correct sub-point to each tri space
	for (i = 0; i<this->triSpaces.size(); ++i){
		subVector = this->getSubVector(inVector, this->tsIndices[i]);
		rawPairs = this->triSpaces[i].getUserValues(subVector);
		for (auto it = rawPairs.begin(); it != rawPairs.end(); ++it){
			superVector = this->getSuperVector(it->first, this->tsIndices[i], dim);
			valuePairs[superVector] = it->second;
		}
	}

	// *****************
	// Conditional Solve
	// *****************

	for (i = 0; i < this->shapeMatrix.size(); ++i){
		const vector<double> &condition = this->shapeMatrix[i];
		if (this->shapeMidMatrix[i]) {
			maskVal = 0;
			if (valuePairs.count(condition)){
				maskVal = valuePairs.at(condition);
			}
		}
		else {
			maskVal = this->applyMask(rawVec, condition, i<condition.size(), this->exactSolve);
		}
		
		if (!isZero(maskVal))
			conds[i] += maskVal;
	}

	for (auto cond = conds.begin(); cond != conds.end(); ++cond){
		prog = this->progs[cond->first]->prog;
		ext = prog->getShapeValues(cond->second);
		for (i = 0; i < ext.size(); ++i){
			auto iii = ext[i].first->getIndex();

			if (idxMap.find(iii) == idxMap.end()){
				idxMap[ext[i].first->getIndex()] = make_pair(ext[i].first, ext[i].second);
			}
			else{
				idxMap[ext[i].first->getIndex()].second += ext[i].second;
			}
		}
	}

    if (this->shapes.size() == 0u){
        return out;
    }

	// set the rest shape value
	idxMap[0] = make_pair(this->shapes[0], 1.0 - maxVal);

	// unravel idxMap
	for (auto x = idxMap.begin(); x != idxMap.end(); ++x){
		out.push_back(x->second);
	}
	return out;
}


/* * CLASS SIMPLEX * */

Simplex::Simplex():built(false), loaded(false), hasParseError(false), exactSolve(true){
	this->clear();
}

void Simplex::setExactSolve(bool exact) {
	this->exactSolve = exact;
	if (this->built) {
		this->controlSpace.setExactSolve(this->exactSolve);
	}
}

bool Simplex::getExactSolve() const{
	return this->exactSolve;
}

void Simplex::clear(){
	this->shapes.clear();
	this->progs.clear();
	this->sliders.clear();
	this->combos.clear();

	this->progMap.clear();
	this->sliderMap.clear();
	this->shapeMap.clear();
	this->comboMap.clear();

    this->parseError.clear();
    this->built = false;
    this->hasParseError = false;
	this->loaded = false;
    this->parseErrorOffset = 0;

    this->controlSpace = ControlSpace();
}

Simplex::Simplex(const string &json){
	this->clear();
	this->parseJSON(json);
}

Simplex::Simplex(const char *json){
	this->clear();
	this->parseJSON(string(json));
}

bool Simplex::parseJSONv1(const rapidjson::Document &d){
	const rapidjson::Value &jshapes = d["shapes"];
	const rapidjson::Value &jsliders = d["sliders"];
	const rapidjson::Value &jcombos = d["combos"];
	const rapidjson::Value &jprogs = d["progressions"];

	if (!jshapes.IsArray()) return false;
	if (!jsliders.IsArray()) return false;
	if (!jcombos.IsArray()) return false;
	if (!jprogs.IsArray()) return false;

	rapidjson::SizeType i, j;

	for (i = 0; i<jshapes.Size(); ++i){
		if (!jshapes[i].IsString()) return false;
		string name(jshapes[i].GetString());
		this->shapes.push_back(Shape(name, (size_t)i));
		this->shapeMap[name] = &this->shapes[this->shapes.size() - 1];
	}

	vector<pair<Shape*, double> > pairs;
	size_t x;
	double y;
	
	for (i = 0; i<jprogs.Size(); ++i){
		if (!jprogs[i].IsArray()) return false;
		pairs.clear();
		const rapidjson::Value &jindices = jprogs[i][1];
		const rapidjson::Value &jweights = jprogs[i][2];
		if (jweights.IsArray() && jindices.IsArray()){
			for (j = 0; j<jindices.Size(); ++j){
				//if (!(jindices.IsInt() && jweights.IsNumber())) return false;
			
				x = (size_t)jindices[j].GetInt();
				y = (double)jweights[j].GetDouble();
				pairs.push_back(make_pair(&this->shapes[x], y));
				
			}

			if (!jprogs[i][0u].IsString()) return false;
			string name(jprogs[i][0u].GetString());
			
			string interp;
			if (jprogs[i].Size() > 3){
				if (!jprogs[i][3].IsString()) return false;
				interp = jprogs[i][3].GetString();
			}
			else {
				interp = "spline";
			}

			Progression p(name, pairs, interp); // needs to be 0u
			this->progs.push_back(std::move(p));
			this->progMap[name] = &this->progs[this->progs.size() - 1];
		}
		else{
			return false;
		}
	}

	size_t slidx;
	for (i = 0; i<jsliders.Size(); ++i){
		if (!jsliders[i][1].IsInt()) return false;
		if (!jsliders[i][0u].IsString()) return false;

		slidx = size_t(jsliders[i][1].GetInt());
		string name(jsliders[i][0u].GetString()); // needs to be 0u

		Slider s(name, &this->progs[slidx], this);
		this->sliders.push_back(std::move(s));
		this->sliderMap[name] = &this->sliders[this->sliders.size() - 1];
	}

	for (i = 0; i<jcombos.Size(); ++i){
		const rapidjson::Value &jcstate = jcombos[i][2];
		vector<pair<Slider*, double> > state;
		
		for (j = 0; j<jcstate.Size(); ++j){
			if (!jcstate[j][0u].IsInt()) return false;
			if (!jcstate[j][1].IsNumber()) return false;
			state.push_back(make_pair(&this->sliders[size_t(jcstate[j][0u].GetInt())], double(jcstate[j][1].GetDouble())));
		}

		if (!jcombos[i][0u].IsString()) return false;
		if (!jcombos[i][1].IsInt()) return false;

		string name(jcombos[i][0u].GetString());
		Combo c(name, &this->progs[jcombos[i][1].GetInt()], this, state);
		this->combos.push_back(std::move(c));
		this->comboMap[name] = &this->combos[this->combos.size() - 1];
	}

	this->loaded = true;
	return true;
}

bool Simplex::parseJSONv2(const rapidjson::Document &d){
	const rapidjson::Value &jshapes = d["shapes"];
	const rapidjson::Value &jsliders = d["sliders"];
	const rapidjson::Value &jcombos = d["combos"];
	const rapidjson::Value &jprogs = d["progressions"];

	if (!jshapes.IsArray()) return false;
	if (!jsliders.IsArray()) return false;
	if (!jcombos.IsArray()) return false;
	if (!jprogs.IsArray()) return false;

	rapidjson::SizeType i;

	for (i = 0; i<jshapes.Size(); ++i){
        auto &shapeVal = jshapes[i];

		if (!jshapes[i].IsObject()) return false;

        auto nameIt = jshapes[i].FindMember("name");
        if (nameIt == jshapes[i].MemberEnd()) return false;
        if (!nameIt->value.IsString()) return false;

        string name(nameIt->value.GetString());

        Shape s(name, (size_t)i);

		this->shapes.push_back(s);
		this->shapeMap[name] = &this->shapes[this->shapes.size() - 1];
	}

	for (i = 0; i<jprogs.Size(); ++i){
        auto &progVal = jprogs[i];

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
        string interp(nameIt->value.GetString());
        vector<pair<Shape*, double> > pairs;

        auto &pairsVal = pairsIt->value;
        for (auto it = pairsVal.Begin(); it != pairsVal.End(); ++it){
			auto &ival = *it;
			if (!ival.IsArray()) return false;
            if (!ival[0].IsInt()) return false;
            if (!ival[1].IsDouble()) return false;

            size_t x = (size_t)ival[0].GetInt();
            double y = (double)ival[1].GetDouble();
            pairs.push_back(make_pair(&this->shapes[x], y));
        }

        Progression p(name, pairs, interp); // needs to be 0u
        this->progs.push_back(std::move(p));
        this->progMap[name] = &this->progs[this->progs.size() - 1];
    }

	for (i = 0; i<jsliders.Size(); ++i){
        auto &sliVal = jsliders[i];
		if (!sliVal.IsObject()) return false;

        auto nameIt = sliVal.FindMember("name");
        if (nameIt == sliVal.MemberEnd()) return false;
        if (!nameIt->value.IsString()) return false;

        auto progIt = sliVal.FindMember("prog");
        if (progIt == sliVal.MemberEnd()) return false;
        if (!progIt->value.IsInt()) return false;

        string name(nameIt->value.GetString());
        size_t slidx = size_t(progIt->value.GetInt());

		Slider s(name, &this->progs[slidx], this);
		this->sliders.push_back(std::move(s));
		this->sliderMap[name] = &this->sliders[this->sliders.size() - 1];
    }

	for (i = 0; i<jcombos.Size(); ++i){
        auto &comboVal = jcombos[i];
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
            state.push_back(make_pair(&this->sliders[x], y));
        }
        
        size_t pidx = (size_t)progIt->value.GetInt();
		Combo c(name, &this->progs[pidx], this, state);

		this->combos.push_back(std::move(c));
		this->comboMap[name] = &this->combos[this->combos.size() - 1];
    }

	this->loaded = true;
	return true;
}

bool Simplex::parseJSON(const string &json){
	// Make sure when getting the 0 index from a rapidjson Value
	// always use rapidjson::SizeType, or 0u because the compiler
	// can't decide between 0 and a null string
	this->built = false;
	
	rapidjson::Document d;
	d.Parse<0>(json.c_str());

	this->hasParseError = false;
	if (d.HasParseError()){
		this->hasParseError = true;
		this->parseError = string(rapidjson::GetParseError_En(d.GetParseError()));
		this->parseErrorOffset = d.GetErrorOffset();
		return false;
	}

	if (!d.HasMember("shapes")) return false;
	if (!d.HasMember("sliders")) return false;
	if (!d.HasMember("combos")) return false;
	if (!d.HasMember("progressions")) return false;
	if (!d.HasMember("encodingVersion")) return false;

	const rapidjson::Value &ev = d["encodingVersion"];

	if (!ev.IsInt()) return false;

	auto encoding = ev.GetUint();
	if (encoding == 1) {
		return this->parseJSONv1(d);
	}
	else if (encoding == 2) {
		return this->parseJSONv2(d);
	}
	return false;
}

void Simplex::buildControlSpace(){
	this->built = true;
	size_t i;
	for (i=0; i<this->sliders.size(); ++i){
		this->controlSpace.addItem(&this->sliders[i]);
	}

	for (i=0; i<this->combos.size(); ++i){
		this->controlSpace.addItem(&this->combos[i]);
	}
	this->controlSpace.triangulate();
	this->controlSpace.setShapes(this->shapes);
	this->controlSpace.setExactSolve(this->exactSolve);
}

vector<pair<Shape*, double> > Simplex::getDeltaShapeValues(const vector<double> &vec) {
	if (!this->built) this->buildControlSpace();
	return this->controlSpace.deltaSolver(vec);
}

vector<double> Simplex::getDeltaIndexValues(const vector<double> &vec) {
	if (!this->built) this->buildControlSpace();
	vector<pair<Shape*, double> > shapevals = this->getDeltaShapeValues(vec);
	vector<pair<string, double> > tester;

	vector<double> out(this->shapes.size(), 0.0);
	for (auto it = shapevals.begin(); it != shapevals.end(); ++it){
		out[it->first->getIndex()] = it->second;
		if (!isZero(it->second)){
			tester.push_back(make_pair(it->first->getName(), it->second));
		}
	}
	if (tester.size() > 0u){
		int x = 1 + 1;
	}
	if (this->shapes.size() == 0u){
		// make sure that we're at least dealing with some data
		out.push_back(0.0); 
	}
	return out;
}

void Simplex::splitSliders(){
	vector<Slider> newSliders, sp;
	vector< pair< Slider*, vector<Slider*> > > splitList;
	vector<Slider*> passList;
	bool splitHappened;

	for (auto slider=this->sliders.begin(); slider!=this->sliders.end(); ++slider){
		sp.clear();
		passList.clear();
		splitHappened = slider->split(sp); // OutValue SP
		if (splitHappened){
			for (auto ns=sp.begin(); ns!=sp.end(); ++ns){
				newSliders.push_back(*ns);
				passList.push_back(&newSliders[newSliders.size()-1]);
			}
			splitList.push_back(make_pair(&(*slider), passList));
		}
		else {
			newSliders.push_back(*slider);
		}
	}
	
	vector<Combo> newCombos, sc;
	for (auto combo=this->combos.begin(); combo!=this->combos.end(); ++combo){
		sc = combo->split(splitList);
		newCombos.insert(newCombos.end(), sc.begin(), sc.end());
	}
	this->combos = newCombos;
	this->sliders = newSliders;
}

size_t Simplex::shapeLen() const{
	return this->shapes.size();
}

size_t Simplex::progLen() const{
	return this->progs.size();
}

size_t Simplex::sliderLen() const{
	return this->sliders.size();
}

size_t Simplex::comboLen() const{
	return this->combos.size();
}

Progression * Simplex::duplicateProgression(Progression * p){
	Progression newProg(*p);
	this->progs.push_back(newProg);
	return &this->progs[this->progs.size()-1];
}

void Simplex::updateProgTimes(const string& name, const std::vector<double>& newTimes){
	Progression* p = this->progMap[name];
	p->setTimes(newTimes);
}
