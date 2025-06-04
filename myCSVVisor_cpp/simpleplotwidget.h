#ifndef SIMPLEPLOTWIDGET_H
#define SIMPLEPLOTWIDGET_H

#include <QWidget>
#include <QPainter>
#include <QVector>
#include <QString>
#include <QRectF>
#include <QPointF>
#include <QPaintEvent>
#include <QMap>   // Added
#include <QColor> // Added

class SimplePlotWidget : public QWidget
{
    Q_OBJECT

public:
    explicit SimplePlotWidget(QWidget* parent = nullptr);
    // Modified setData signature
    void setData(const QVector<QPointF>& data,
                 const QVector<int>& emitterIds,
                 const QMap<int, QColor>& colorMap,
                 const QString& xLabel,
                 const QString& yLabel,
                 const QString& title);

protected:
    void paintEvent(QPaintEvent* event) override;

private:
    QVector<QPointF> plotData;
    QVector<int> pointEmitterIds;      // Added
    QMap<int, QColor> currentColorScheme; // Added

    QString xLabelText;
    QString yLabelText;
    QString titleText;
    QRectF dataBoundingRect;

    void calculateDataBoundingRect();
};

#endif // SIMPLEPLOTWIDGET_H
