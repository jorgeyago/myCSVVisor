#include "placeholder3dwidget.h"
#include <QtGui/QPalette> // For setting background color
#include <QtGui/QColor>   // For QColor

Placeholder3DWidget::Placeholder3DWidget(QWidget* parent)
    : QWidget(parent)
{
    QVBoxLayout* layout = new QVBoxLayout(this);
    QLabel* label = new QLabel("3D View Not Yet Implemented", this);
    label->setAlignment(Qt::AlignCenter);

    QFont font = label->font();
    font.setPointSize(16);
    label->setFont(font);

    layout->addWidget(label);
    setLayout(layout);

    // Set background color
    QPalette pal = palette();
    pal.setColor(QPalette::Window, QColor(Qt::darkGray).lighter(120)); // Lighter dark gray
    setAutoFillBackground(true);
    setPalette(pal);

    setMinimumSize(200, 150); // Consistent with SimplePlotWidget
}
