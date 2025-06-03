#ifndef QCUSTOMPLOT_H
#define QCUSTOMPLOT_H

#include <QtWidgets/QWidget>
#include <QtGui/QPainter>
#include <QtCore/QObject>
#include <QtCore/QVector>
#include <QtCore/QString>
#include <QtCore/QFlags>

// Forward declarations
class QCPPainter;
class QCPAxis;
class QCPGraph;

#define QCP_BEGIN_NAMESPACE
#define QCP_END_NAMESPACE
#define QCP_USE_NAMESPACE

QCP_BEGIN_NAMESPACE

namespace QCP {
    enum Interaction { iRangeDrag = 0x001, iRangeZoom = 0x002, iSelectPlottables = 0x004 };
    Q_DECLARE_FLAGS(Interactions, Interaction)
}

class QCustomPlot : public QWidget {
    Q_OBJECT
public:
    explicit QCustomPlot(QWidget *parent = nullptr);
    virtual ~QCustomPlot();

    void addGraph();
    QCPGraph* graph(int index = 0);
    void replot();
    void setInteractions(QCP::Interactions interactions); // Keep this, will fix usage in mainwindow
    void rescaleAxes(); // Added dummy method

    QCPAxis* xAxis = nullptr;
    QCPAxis* yAxis = nullptr;
    QCPAxis* xAxis2 = nullptr;
    QCPAxis* yAxis2 = nullptr;
};

class QCPPainter : public QPainter {
public:
    QCPPainter() {}
    QCPPainter(QPaintDevice* dev) : QPainter(dev) {}
    enum PainterMode { pmDefault };
    Q_DECLARE_FLAGS(PainterModes, PainterMode)
};

class QCPAxis : public QObject {
    Q_OBJECT
public:
    explicit QCPAxis(QObject* parent = nullptr) : QObject(parent) {}
    void setLabel(const QString&) {}
    void setVisible(bool) {}
    void setTicks(bool) {}
    void setTickLabels(bool) {}
};

class QCPGraph : public QObject {
    Q_OBJECT
public:
    explicit QCPGraph(QCPAxis* keyAxis, QCPAxis* valueAxis) : QObject(nullptr) {}
    void setData(const QVector<double>& keys, const QVector<double>& values) {}

    enum LineStyle { lsNone };
    void setLineStyle(LineStyle) {}

    enum ScatterShape { ssNone, ssCircle };
    struct QCPScatterStyle { // Now a distinct struct, not nested for simplicity here
        ScatterShape shape;
        // Dummy constructors to match usage in mainwindow.cpp
        QCPScatterStyle(ScatterShape s = ssNone) : shape(s) {}
        QCPScatterStyle(ScatterShape s, const QColor&, const QColor&, int) : shape(s) {}
        QCPScatterStyle(ScatterShape s, const QColor&, int) : shape(s) {}
        QCPScatterStyle(ScatterShape s, Qt::GlobalColor, Qt::GlobalColor, int) : shape(s) {}


    };
    void setScatterStyle(const QCPScatterStyle&) {}
};

QCP_END_NAMESPACE

#endif // QCUSTOMPLOT_H
