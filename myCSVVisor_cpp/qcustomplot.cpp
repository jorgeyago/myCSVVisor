#include "qcustomplot.h"
#include <QtGui/QColor> // For QColor in QCPScatterStyle dummy constructor

QCP_BEGIN_NAMESPACE

QCustomPlot::QCustomPlot(QWidget *parent) : QWidget(parent) {
    xAxis = new QCPAxis(this);
    yAxis = new QCPAxis(this);
    xAxis2 = new QCPAxis(this);
    yAxis2 = new QCPAxis(this);
}

QCustomPlot::~QCustomPlot() {}

void QCustomPlot::addGraph() {
}

QCPGraph* QCustomPlot::graph(int index) {
    // This is problematic if multiple graphs are expected or if it's stored.
    // For a single graph(0) usage, a static might appear to work but isn't correct.
    // Let's make it a member to be slightly more robust for the dummy.
    // Proper QCP manages a list of graphs.
    static QCPGraph dummyGraphInstance(nullptr, nullptr); // Still not great, but avoids direct static return issues
    if (!mGraphs.isEmpty()) return mGraphs.first(); // Simplistic
    mGraphs.append(new QCPGraph(xAxis, yAxis)); // Create one if accessed
    return mGraphs.first();

}

void QCustomPlot::replot() {}

void QCustomPlot::setInteractions(QCP::Interactions interactions) {}

void QCustomPlot::rescaleAxes() {} // Added dummy method

// Dummy QCPGraph member to hold one graph for graph(0)
// This is a hack for the minimal version.
QVector<QCPGraph*> QCustomPlot::mGraphs;


QCP_END_NAMESPACE
