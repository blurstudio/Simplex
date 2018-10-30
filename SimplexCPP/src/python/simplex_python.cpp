#include <Python.h>
#include <structmember.h>

#include "simplex.h"
#include <string>
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
        self->definition = PyString_FromString("");
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
        jsValue = PyString_FromString("");
    }

    if (! PyString_Check(jsValue)) {
        PyErr_SetString(PyExc_TypeError, "The simplex definition must be a string");
        return -1;
    }

    PyObject *tmp = self->definition;
    Py_INCREF(jsValue);
    self->definition = jsValue;
    Py_DECREF(tmp);

    // set the definition in the solver
    self->sPointer->parseJSON(std::string(PyString_AsString(self->definition)));

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
    {NULL}  /* Sentinel */
};

static PyTypeObject PySimplexType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "pysimplex.PySimplex",             /* tp_name */
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

#ifndef PyMODINIT_FUNC	/* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif
PyMODINIT_FUNC
initpysimplex(void)
{
    PyObject* m;

    if (PyType_Ready(&PySimplexType) < 0)
        return;

    m = Py_InitModule3("pysimplex", module_methods,
                       "The Simplex blendshape solver in Python");

    if (m == NULL)
        return;

    Py_INCREF(&PySimplexType);
    PyModule_AddObject(m, "PySimplex", (PyObject *)&PySimplexType);
}
