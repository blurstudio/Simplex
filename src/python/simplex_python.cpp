#include <Python.h>
#include <structmember.h>

#include "simplex.h"
#include <string>
#include <codecvt>
#include <vector>

typedef struct {
    PyObject_HEAD // No Semicolon for this Macro;
    PyObject *definition;
    simplex::Simplex *sPointer;
} PySimplex;

static void
PySimplex_dealloc(PySimplex* self) {
    Py_XDECREF(self->definition);
    if (self->sPointer != NULL)
		delete self->sPointer;
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject *
PySimplex_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    PySimplex *self;
    self = (PySimplex *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->definition = PyUnicode_FromString("");
        if (self->definition == NULL) {
            Py_DECREF(self);
            return NULL;
        }
        self->sPointer = new simplex::Simplex();
    }

    return (PyObject *)self;
}

static PyObject *
PySimplex_getdefinition(PySimplex* self, void* closure){
    Py_INCREF(self->definition);
    return self->definition;
}

static int
PySimplex_setdefinition(PySimplex* self, PyObject* jsValue, void* closure){
    if (jsValue == NULL || jsValue == Py_None){
        jsValue = PyUnicode_FromString("");
    }

    if (! PyUnicode_Check(jsValue)) {
        PyErr_SetString(PyExc_TypeError, "The simplex definition must be a string");
        return -1;
    }

    PyObject *tmp = self->definition;
    Py_INCREF(jsValue);
    self->definition = jsValue;
    Py_DECREF(tmp);

#if PY_MAJOR_VERSION >= 3
    // Get the unicode as a wstring, and a wstring to string converter
    std::wstring simDefw = std::wstring(PyUnicode_AsWideCharString(self->definition, NULL));
    std::wstring_convert<std::codecvt_utf8<wchar_t>> myconv;
    std::string simDef = myconv.to_bytes(simDefw);
#else
    std::string simDef = std::string(PyString_AsString(self->definition);
#endif
    // set the definition in the solver
    self->sPointer->clear();
    self->sPointer->parseJSON(simDef);
    self->sPointer->build();

    return 0;
}

static PyObject *
PySimplex_getexactsolve(PySimplex* self, void* closure){
    if (self->sPointer->getExactSolve()){
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}

static int
PySimplex_setexactsolve(PySimplex* self, PyObject* exact, void* closure){
    int truthy = PyObject_IsTrue(exact);
    if (truthy == -1){
        PyErr_SetString(PyExc_TypeError, "The value passed cannot be cast to boolean");
        return -1;
    }

    self->sPointer->setExactSolve((truthy == 1));
    return 0;
}

static int
PySimplex_init(PySimplex *self, PyObject *args, PyObject *kwds) {
    PyObject *jsValue=NULL, *tmp=NULL;
    static char *kwlist[] = {"jsValue", NULL};

    if (! PyArg_ParseTupleAndKeywords(args, kwds, "|O", kwlist, &jsValue))
        return -1;

    return PySimplex_setdefinition(self, jsValue, NULL);
}

static PyObject *
PySimplex_solve(PySimplex* self, PyObject* vec){
    if (! PySequence_Check(vec)){
        PyErr_SetString(PyExc_TypeError, "Input must be a list or tuple");
        return NULL;
    }

    PyObject *item;
    std::vector<double> stdVec, outVec;
    for (Py_ssize_t i=0; i<PySequence_Size(vec); ++i){
        item = PySequence_ITEM(vec, i);
        if (! PyNumber_Check(item)) {
            PyErr_SetString(PyExc_TypeError, "Input list can contain only numbers");
            return NULL;
        }
        stdVec.push_back(PyFloat_AsDouble(PyNumber_Float(item)));
        Py_DECREF(item);
    }

	self->sPointer->clearValues();
    outVec = self->sPointer->solve(stdVec);

    PyObject *out = PyList_New(outVec.size());
    for (size_t i=0; i<outVec.size(); ++i){
        PyList_SET_ITEM(out, i, PyFloat_FromDouble(outVec[i]));
    }
    return out;
}


static PyObject *
PySimplex_solveBuffer(PySimplex* self, PyObject* args){
    PyObject *input, *output;
	if (!PyArg_ParseTuple(args, "OO", &input, &output)) {
		return NULL;
	}

    if (PyObject_CheckBuffer(input) == 0){
        PyErr_SetString(PyExc_TypeError, "Input must be a buffer");
        return NULL;
    }
    if (PyObject_CheckBuffer(output) == 0){
        PyErr_SetString(PyExc_TypeError, "Output must be a buffer");
        return NULL;
    }

    // Buffer WAY
    Py_buffer inView, outView;

    if (PyObject_GetBuffer(input, &inView, PyBUF_STRIDED_RO) != 0){
        PyErr_SetString(PyExc_TypeError, "Cannot read input buffer");
        return NULL;
    }

    if (PyObject_GetBuffer(output, &outView, PyBUF_STRIDED) != 0){
        PyErr_SetString(PyExc_TypeError, "Cannot read output buffer");
        PyBuffer_Release(&inView);
        return NULL;
    }

    if (inView.ndim != 1){
        PyErr_SetString(PyExc_ValueError, "Input must have exactly 1 dimension");
        PyBuffer_Release(&inView);
        PyBuffer_Release(&outView);
        return NULL;
    }

    if (outView.ndim != 1){
        PyErr_SetString(PyExc_ValueError, "Output must have exactly 1 dimension");
        PyBuffer_Release(&inView);
        PyBuffer_Release(&outView);
        return NULL;
    }

    std::vector<double> stdVec, outVec;
    stdVec.resize((size_t)inView.shape[0]);
	Py_ssize_t inSize = inView.itemsize;
		
    char *iptr = (char *)inView.buf;
    for (Py_ssize_t i = 0; i<inView.shape[0]; ++i){
        if (inSize == sizeof(double)){
            stdVec[i] = *(double *)iptr;
        }
        else {
            stdVec[i] = (double)(*(float *)iptr);
        }
        iptr += inView.strides[0];
    }

	self->sPointer->clearValues();
    outVec = self->sPointer->solve(stdVec);

    if (outView.shape[0] < outVec.size()){
        PyErr_SetString(PyExc_ValueError, "Output must have enough space allocated");
        PyBuffer_Release(&inView);
        PyBuffer_Release(&outView);
        return NULL;
    }

	Py_ssize_t outSize = outView.itemsize;
    if (outSize == sizeof(double)){
		memcpy(outView.buf, outVec.data(), outVec.size() * sizeof(double));
    }
    else {
        std::vector<float> outFloatVec;
        outFloatVec.resize(outVec.size());
        std::copy(outVec.begin(), outVec.end(), outFloatVec.begin());
        memcpy(outView.buf, outVec.data(), outFloatVec.size()*sizeof(float));
    }

    PyBuffer_Release(&inView);
    PyBuffer_Release(&outView);
	Py_RETURN_NONE;
}



static PyGetSetDef PySimplex_getseters[] = {
    {"definition",
     (getter)PySimplex_getdefinition, (setter)PySimplex_setdefinition,
     "Simplex structure definition string",
     NULL},

    {"exactSolve",
     (getter)PySimplex_getexactsolve, (setter)PySimplex_setexactsolve,
     "Run the solve with the exact min() solver",
     NULL},
    {NULL}  /* Sentinel */
};

static PyMethodDef PySimplex_methods[] = {
    {"solve", (PyCFunction)PySimplex_solve, METH_O,
     "Supply an input list to the solver, and recieve and output list"
    },
    {"solveBuffer", (PyCFunction)PySimplex_solveBuffer, METH_VARARGS,
     "Supply an input list to the solver, and recieve and output buffer"
    },
    {NULL}  /* Sentinel */
};

static PyTypeObject PySimplexType = {
    PyVarObject_HEAD_INIT(NULL, 0)
#if PY_MAJOR_VERSION >= 3
    "pysimplex3.PySimplex",             /* tp_name */
#else
    "pysimplex.PySimplex",             /* tp_name */
#endif
    sizeof(PySimplex),             /* tp_basicsize */
    0,                         /* tp_itemsize */
    (destructor)PySimplex_dealloc, /* tp_dealloc */
    0,                         /* tp_print */
    0,                         /* tp_getattr */
    0,                         /* tp_setattr */
    0,                         /* tp_compare */
    0,                         /* tp_repr */
    0,                         /* tp_as_number */
    0,                         /* tp_as_sequence */
    0,                         /* tp_as_mapping */
    0,                         /* tp_hash */
    0,                         /* tp_call */
    0,                         /* tp_str */
    0,                         /* tp_getattro */
    0,                         /* tp_setattro */
    0,                         /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT |
        Py_TPFLAGS_BASETYPE,   /* tp_flags */
    "PySimplex objects",       /* tp_doc */
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    0,                         /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    PySimplex_methods,         /* tp_methods */
    0,                         /* tp_members */
    PySimplex_getseters,       /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)PySimplex_init,  /* tp_init */
    0,                         /* tp_alloc */
    PySimplex_new,             /* tp_new */
};

static PyMethodDef module_methods[] = {
    {NULL}  /* Sentinel */
};



static PyObject * localInit(void)
{
    PyObject* m;

    if (PyType_Ready(&PySimplexType) < 0)
        return NULL;

#if PY_MAJOR_VERSION >= 3
    static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "pysimplex3",     /* m_name */
        "The Simplex blendshape solver in Python",  /* m_doc */
        -1,                  /* m_size */
        module_methods,      /* m_methods */
        NULL,                /* m_reload */
        NULL,                /* m_traverse */
        NULL,                /* m_clear */
        NULL,                /* m_free */
    };
    m = PyModule_Create(&moduledef);
#else
    m = Py_InitModule3("pysimplex", module_methods,
        "The Simplex blendshape solver in Python");
#endif

    if (m == NULL)
        return NULL;

    Py_INCREF(&PySimplexType);
    PyModule_AddObject(m, "PySimplex", (PyObject *)&PySimplexType);
    return m;
}

#if PY_MAJOR_VERSION >= 3
PyMODINIT_FUNC PyInit_pysimplex3(void) {
    return localInit();
}
#else
PyMODINIT_FUNC initpysimplex(void) {
    localInit();
}
#endif
