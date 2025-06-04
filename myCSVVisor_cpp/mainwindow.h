#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include <QSplitter>
#include <QTableView>
#include <QStandardItemModel>
#include <QToolBar>
#include <QComboBox>
#include <QMenuBar>
#include <QMenu>
#include <QFileDialog>
#include <QVBoxLayout>
#include <QLabel>
#include <QStatusBar>
#include <QMessageBox>
#include <QAction>
#include <QStackedWidget>
#include <QMap>
#include <QColor>
#include <QTextEdit>
#include <QList>
#include <QPixmap>
#include <QPointF>
#include <QLineEdit>    // Added for headerFilters

#include "csvloader.h"
#include "csvdata.h"
#include "simpleplotwidget.h"
#include "placeholder3dwidget.h"

// Forward declare QPushButton for filter buttons if not including the header here
class QPushButton;

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    MainWindow(QWidget *parent = nullptr);
    ~MainWindow();

private slots:
    void openCsvFile();
    void handleCsvLoadingFinished(const CsvData& data);
    void handleCsvLoadingError(const QString& message);
    void handleCsvLoadingProgress(int value, const QString& message);
    void updateTableDisplay();
    void updatePlot();
    void toggleViewMode();
    void savePlotImage();
    void resetPlotView();
    void applyTableFilters();     // New slot for filtering
    void clearTableFilters();     // New slot for clearing filters
    void exportFilteredData();    // New slot for export

private:
    void createMenuBar();
    void createToolBar();
    void createFilterControls(); // Helper for creating filter buttons
    void loadEmitterReference();
    void populateDefaultColors();
    QColor getEmitterColor(int emitterId);
    QString getEmitterLabel(int emitterId);
    void updateLegend();

    // UI Elements
    QSplitter* centralSplitter;
    SimplePlotWidget* plotWidget;
    Placeholder3DWidget* plot3DPlaceholder;
    QStackedWidget* plotStackedWidget;
    QTextEdit* legendTextEdit;

    QTableView* tableView;
    QStandardItemModel* tableModel;

    QToolBar* axisToolBar;
    QComboBox* xComboBox;
    QComboBox* yComboBox;
    QComboBox* zComboBox;
    QLabel* zLabel;

    QAction* toggleViewAction;
    QAction* saveImageAction;
    QAction* resetViewAction;
    QAction* exportFilteredAction; // Action for export

    // Filter controls
    QWidget* filterControlsWidget = nullptr; // Container for filter buttons
    QList<QLineEdit*> headerFilters;

    // State
    bool is3DViewActive = false;

    // Data and Loader
    CsvLoader* csvLoader = nullptr;
    CsvData currentCsvData;         // Original loaded data
    CsvData currentlyDisplayedData; // Data currently shown in table (can be filtered)
    QString currentEmitterColumn;

    // Emitter and Color Data
    QMap<int, QString> emitterReference;
    QMap<int, QColor> emitterColorMap;
    QList<QColor> vibrantColors;
    int nextColorIndex = 0;

    // For storing current 2D plot data for reset
    QVector<QPointF> currentPlotPoints;
    QVector<int> currentPlotEmitterIds;
    QString currentPlotXLabel;
    QString currentPlotYLabel;
    QString currentPlotTitle;
};

#endif // MAINWINDOW_H
