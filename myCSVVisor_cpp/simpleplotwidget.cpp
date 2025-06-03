#include "simpleplotwidget.h"
#include <algorithm> // For std::min/max if needed
#include <limits>    // For std::numeric_limits
#include <QDebug>    // For optional debug messages
#include <QApplication> // Added for QApplication::font()
#include <QFontInfo>    // Added for QFontInfo

SimplePlotWidget::SimplePlotWidget(QWidget* parent)
    : QWidget(parent)
{
    xLabelText = "X-Axis";
    yLabelText = "Y-Axis";
    titleText = "Plot";
    dataBoundingRect = QRectF(0, 0, 1, 1);
    setMinimumSize(200, 150);
}

void SimplePlotWidget::setData(const QVector<QPointF>& data,
                               const QVector<int>& emitterIds,
                               const QMap<int, QColor>& colorMap,
                               const QString& xLabel,
                               const QString& yLabel,
                               const QString& title)
{
    plotData = data;
    pointEmitterIds = emitterIds;
    currentColorScheme = colorMap;
    xLabelText = xLabel;
    yLabelText = yLabel;
    titleText = title;
    calculateDataBoundingRect();
    update();
}

void SimplePlotWidget::calculateDataBoundingRect()
{
    if (plotData.isEmpty()) {
        dataBoundingRect = QRectF(0, 0, 1, 1);
        return;
    }

    double minX = plotData[0].x();
    double maxX = plotData[0].x();
    double minY = plotData[0].y();
    double maxY = plotData[0].y();

    for (const QPointF& point : plotData) {
        if (point.x() < minX) minX = point.x();
        if (point.x() > maxX) maxX = point.x();
        if (point.y() < minY) minY = point.y();
        if (point.y() > maxY) maxY = point.y();
    }

    if (minX == maxX) {
        minX -= 0.5;
        maxX += 0.5;
    }
    if (minY == maxY) {
        minY -= 0.5;
        maxY += 0.5;
    }

    double width = maxX - minX;
    double height = maxY - minY;
    if (width == 0) width = 1.0;
    if (height == 0) height = 1.0;

    dataBoundingRect = QRectF(minX, minY, width, height);
}

void SimplePlotWidget::paintEvent(QPaintEvent* event)
{
    Q_UNUSED(event);
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);

    int marginTop = 30;
    int marginBottom = 50;
    int marginLeft = 60;
    int marginRight = 20;

    QRect plotRect(marginLeft, marginTop,
                   width() - marginLeft - marginRight,
                   height() - marginTop - marginBottom);

    if (!plotRect.isValid() || plotRect.width() < 1 || plotRect.height() < 1) {
        return;
    }

    painter.fillRect(plotRect, Qt::white);
    painter.setPen(Qt::black);
    painter.drawRect(plotRect);

    QFont titleFont = painter.font();
    titleFont.setBold(true);
    titleFont.setPointSize(titleFont.pointSize() + 2);
    painter.setFont(titleFont);
    painter.drawText(QRect(0, 0, width(), marginTop), Qt::AlignCenter, titleText);

    QFont labelFont = painter.font();
    labelFont.setBold(false);

    int defaultPointSize = QFontInfo(QApplication::font()).pointSize();
    if (titleFont.pointSize() != defaultPointSize) { // Check if title font was different
         labelFont.setPointSize(defaultPointSize);
    }
    painter.setFont(labelFont);

    painter.drawText(QRect(marginLeft, height() - marginBottom + 15, plotRect.width(), marginBottom - 15), Qt::AlignCenter, xLabelText);

    painter.save();
    painter.translate(marginLeft - 45, plotRect.y() + plotRect.height() / 2.0);
    painter.rotate(-90);
    painter.drawText(QRect(0, 0, plotRect.height(), 20), Qt::AlignCenter, yLabelText);
    painter.restore();

    if (plotData.isEmpty() || dataBoundingRect.width() <= 0 || dataBoundingRect.height() <= 0) {
        return;
    }

    painter.setClipRect(plotRect.adjusted(1, 1, -1, -1));

    double sx = plotRect.width() / dataBoundingRect.width();
    double sy = plotRect.height() / dataBoundingRect.height();

    painter.setPen(Qt::NoPen);

    for (int i = 0; i < plotData.size(); ++i) {
        const QPointF& dataPoint = plotData[i];
        int emitterId = pointEmitterIds.value(i, -1);
        QColor pointColor = currentColorScheme.value(emitterId, Qt::gray);

        painter.setBrush(pointColor);

        double pointX = plotRect.left() + (dataPoint.x() - dataBoundingRect.left()) * sx;
        double pointY = plotRect.bottom() - (dataPoint.y() - dataBoundingRect.top()) * sy;

        painter.drawRect(QRectF(pointX - 2, pointY - 2, 4, 4));
    }
    painter.setClipping(false);
}
