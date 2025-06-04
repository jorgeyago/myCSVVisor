#include "mainwindow.h"

#include <QApplication>
#include <QHeaderView>
#include <QScreen>
#include <QFileInfo>
#include <QPainter>
#include <QDebug>
#include <QStackedWidget>
#include <QAction>
#include <QTextStream>
#include <QFile>
#include <QSet>
#include <algorithm>
#include <QFileDialog>
#include <QPixmap>
#include <QLineEdit>
#include <QPushButton>
#include <QHBoxLayout>

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent),
      plotWidget(nullptr),
      plot3DPlaceholder(nullptr),
      plotStackedWidget(nullptr),
      legendTextEdit(nullptr),
      csvLoader(nullptr),
      toggleViewAction(nullptr),
      saveImageAction(nullptr),
      resetViewAction(nullptr),
      exportFilteredAction(nullptr),
      filterControlsWidget(nullptr),
      is3DViewActive(false),
      nextColorIndex(0)
{
    tableModel = new QStandardItemModel(this);
    tableView = new QTableView;
    tableView->setModel(tableModel);
    tableView->horizontalHeader()->setSectionsClickable(false);
    tableView->setEditTriggers(QAbstractItemView::NoEditTriggers);

    plotWidget = new SimplePlotWidget(this);
    plotWidget->setMinimumSize(200, 150);

    plot3DPlaceholder = new Placeholder3DWidget(this);
    plot3DPlaceholder->setMinimumSize(200,150);

    plotStackedWidget = new QStackedWidget(this);
    plotStackedWidget->addWidget(plotWidget);
    plotStackedWidget->addWidget(plot3DPlaceholder);

    legendTextEdit = new QTextEdit(this);
    legendTextEdit->setReadOnly(true);
    legendTextEdit->setMaximumHeight(100);

    createFilterControls();

    QWidget* mainContentWidget = new QWidget;
    QVBoxLayout* mainContentLayout = new QVBoxLayout(mainContentWidget);

    centralSplitter = new QSplitter(Qt::Vertical, this);
    centralSplitter->addWidget(plotStackedWidget);

    QWidget* tableAreaWidget = new QWidget;
    QVBoxLayout* tableAreaLayout = new QVBoxLayout(tableAreaWidget);
    tableAreaLayout->setContentsMargins(0,0,0,0);
    tableAreaLayout->addWidget(filterControlsWidget);
    tableAreaLayout->addWidget(tableView);
    centralSplitter->addWidget(tableAreaWidget);

    mainContentLayout->addWidget(centralSplitter);
    mainContentLayout->addWidget(legendTextEdit);
    setCentralWidget(mainContentWidget);

    plotStackedWidget->setCurrentWidget(plotWidget);

    QList<int> initialSizes;
    QScreen* screen = QGuiApplication::primaryScreen();
    if (screen) {
        QRect screenGeometry = screen->geometry();
        mainContentLayout->setStretchFactor(centralSplitter, 1);
        mainContentLayout->setStretchFactor(legendTextEdit, 0);
        initialSizes << static_cast<int>(screenGeometry.height() * 0.60);
        initialSizes << static_cast<int>(screenGeometry.height() * 0.25);
    } else {
        initialSizes << 600 << 250;
    }
    centralSplitter->setSizes(initialSizes);

    populateDefaultColors();
    loadEmitterReference();

    createMenuBar();
    createToolBar();
    statusBar();

    if (zLabel) zLabel->hide();
    if (zComboBox) zComboBox->hide();

    connect(xComboBox, &QComboBox::currentTextChanged, this, &MainWindow::updatePlot);
    connect(yComboBox, &QComboBox::currentTextChanged, this, &MainWindow::updatePlot);

    setWindowTitle("myCSVVisor C++");
    if (screen) {
        QRect screenGeometry = screen->geometry();
        resize(static_cast<int>(screenGeometry.width() * 0.8), static_cast<int>(screenGeometry.height() * 0.8));
    } else {
        resize(1024, 860);
    }
    updateTableDisplay();
    updateLegend();
}

MainWindow::~MainWindow()
{
    if (csvLoader && csvLoader->isRunning()) {
        csvLoader->cancel();
        csvLoader->wait();
    }
}

void MainWindow::createFilterControls()
{
    filterControlsWidget = new QWidget(this);
    QHBoxLayout* layout = new QHBoxLayout(filterControlsWidget);
    layout->setContentsMargins(0, 5, 0, 5);

    QPushButton* applyButton = new QPushButton(tr("Apply Filters"), this);
    connect(applyButton, &QPushButton::clicked, this, &MainWindow::applyTableFilters);
    layout->addWidget(applyButton);

    QPushButton* clearButton = new QPushButton(tr("Clear Filters"), this);
    connect(clearButton, &QPushButton::clicked, this, &MainWindow::clearTableFilters);
    layout->addWidget(clearButton);

    layout->addStretch();
    filterControlsWidget->setLayout(layout);
}


void MainWindow::populateDefaultColors()
{
    vibrantColors << QColor(Qt::green).darker(120)
                  << QColor(Qt::blue)
                  << QColor(Qt::cyan).darker(150)
                  << QColor(Qt::magenta)
                  << QColor(Qt::yellow).darker(150)
                  << QColor(Qt::darkBlue)
                  << QColor(Qt::darkGreen)
                  << QColor(Qt::darkCyan)
                  << QColor(Qt::darkMagenta)
                  << QColor(Qt::darkYellow)
                  << QColor(Qt::gray)
                  << QColor("#FF5733")
                  << QColor("#33FFBD")
                  << QColor("#A233FF")
                  << QColor("#FFC300");
}

void MainWindow::loadEmitterReference()
{
    emitterReference.clear();
    QFile file(":/reference_emitters.txt");
    if (!file.exists()) {
        QString appDirPath = QCoreApplication::applicationDirPath();
        QDir dir(appDirPath);
        #ifdef Q_OS_MACOS
        dir.cdUp(); dir.cdUp(); dir.cdUp();
        #endif
        QString filePath = dir.filePath("../myCSVVisor_cpp/reference_emitters.txt");
        if (!QFile::exists(filePath)) filePath = dir.filePath("../../myCSVVisor_cpp/reference_emitters.txt");
        if (!QFile::exists(filePath)) filePath = "reference_emitters.txt";
        if (!QFile::exists(filePath)) filePath = "../reference_emitters.txt";
        file.setFileName(filePath);
    }

    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        qDebug() << "Could not open reference_emitters.txt. Tried: " << file.fileName() << "Error:" << file.errorString();
        statusBar()->showMessage("Could not load emitter reference file. Using defaults.", 5000);
        emitterReference[-1] = "Noise Source (default)";
        emitterReference[0] = "Unknown Emitter (default)";
        emitterReference[1] = "Alpha Emitter (default)";
        return;
    }
    QTextStream in(&file);
    while (!in.atEnd()) {
        QString line = in.readLine();
        QStringList parts = line.split('=');
        if (parts.size() == 2) {
            QString name = parts[0].trimmed();
            bool ok;
            int id = parts[1].trimmed().toInt(&ok);
            if (ok) emitterReference[id] = name;
            else qDebug() << "Warning: Could not parse emitter ID in reference file:" << line;
        }
    }
    file.close();
    qDebug() << "Loaded" << emitterReference.size() << "emitter references from" << file.fileName();
    if (emitterReference.isEmpty()){
        qDebug() << "Emitter reference is empty. Using defaults.";
        emitterReference[-1] = "Noise Source (default)";
        emitterReference[0] = "Unknown Emitter (default)";
        emitterReference[1] = "Alpha Emitter (default)";
    }
}

QColor MainWindow::getEmitterColor(int emitterId)
{
    if (emitterId == -2) return Qt::red;
    if (emitterId < 0) return Qt::darkGray;
    if (emitterColorMap.contains(emitterId)) return emitterColorMap.value(emitterId);
    if (vibrantColors.isEmpty()) {
        populateDefaultColors();
        if(vibrantColors.isEmpty()) return Qt::black;
    }
    QColor newColor = vibrantColors[nextColorIndex % vibrantColors.size()];
    nextColorIndex++;
    emitterColorMap.insert(emitterId, newColor);
    return newColor;
}

QString MainWindow::getEmitterLabel(int emitterId)
{
    if (emitterId == -2) return "Invalid Emitter ID";
    return emitterReference.value(emitterId, QString("Emitter %1").arg(emitterId));
}

void MainWindow::updateLegend()
{
    if (!legendTextEdit) return;
    legendTextEdit->clear();

    if (is3DViewActive) {
        legendTextEdit->setHtml("<font color='gray'><i>Legend not applicable for 3D view.</i></font>");
        return;
    }
    if (currentlyDisplayedData.rows.empty()) { // Use .empty() for std::vector
        legendTextEdit->setHtml("<font color='gray'><i>Legend will appear here once data is loaded and filters applied.</i></font>");
        return;
    }

    int emitterColIdx = -1;
    if (!currentEmitterColumn.isEmpty()) {
        for (int i = 0; i < currentlyDisplayedData.headers.size(); ++i) {
            if (QString::fromStdString(currentlyDisplayedData.headers[i]) == currentEmitterColumn) {
                emitterColIdx = i;
                break;
            }
        }
    }

    if (emitterColIdx == -1 && !currentEmitterColumn.isEmpty()) {
         legendTextEdit->setHtml("<font color='red'><i>Selected emitter column ('" + currentEmitterColumn + "') not found in displayed data.</i></font>");
        return;
    }
    if (currentEmitterColumn.isEmpty()){
        legendTextEdit->setHtml("<font color='gray'><i>Select an 'Emitter' column to see legend.</i></font>");
        return;
    }

    QSet<int> uniqueEmitterIdsInData;
    for (const auto& row : currentlyDisplayedData.rows) {
        if (row.size() > emitterColIdx) {
            bool ok;
            int id = QString::fromStdString(row[emitterColIdx]).toInt(&ok);
            if (ok) uniqueEmitterIdsInData.insert(id);
            else uniqueEmitterIdsInData.insert(-2);
        }
    }

    if (uniqueEmitterIdsInData.isEmpty()) {
        legendTextEdit->setHtml("<font color='gray'><i>No valid emitter IDs found in the displayed data.</i></font>");
        return;
    }

    QString legendHtml;
    QList<int> sortedIds = uniqueEmitterIdsInData.values();
    std::sort(sortedIds.begin(), sortedIds.end());

    for (int id : sortedIds) {
        QColor color = getEmitterColor(id);
        QString label = getEmitterLabel(id);
        legendHtml += QString("<font color='%1'>⬤</font> %2 (%3)<br>").arg(color.name()).arg(label).arg(id);
    }
    legendTextEdit->setHtml(legendHtml);
}


void MainWindow::createMenuBar()
{
    QMenu *fileMenu = menuBar()->addMenu(tr("&File"));
    QAction *loadCsvAction = new QAction(tr("&Load CSV..."), this);
    connect(loadCsvAction, &QAction::triggered, this, &MainWindow::openCsvFile);
    fileMenu->addAction(loadCsvAction);

    saveImageAction = new QAction(tr("&Save Image..."), this);
    connect(saveImageAction, &QAction::triggered, this, &MainWindow::savePlotImage);
    fileMenu->addAction(saveImageAction);

    exportFilteredAction = new QAction(tr("Export Filtered Data..."), this);
    connect(exportFilteredAction, &QAction::triggered, this, &MainWindow::exportFilteredData);
    fileMenu->addAction(exportFilteredAction);

    fileMenu->addSeparator();
    QAction *exitAction = new QAction(tr("E&xit"), this);
    connect(exitAction, &QAction::triggered, this, &QWidget::close);
    fileMenu->addAction(exitAction);

    QMenu *viewMenu = menuBar()->addMenu(tr("&View"));
    toggleViewAction = new QAction(tr("Switch to 3D Mode"), this);
    connect(toggleViewAction, &QAction::triggered, this, &MainWindow::toggleViewMode);
    viewMenu->addAction(toggleViewAction);

    resetViewAction = new QAction(tr("&Reset View"), this);
    connect(resetViewAction, &QAction::triggered, this, &MainWindow::resetPlotView);
    viewMenu->addAction(resetViewAction);

    saveImageAction->setEnabled(false);
    resetViewAction->setEnabled(false);
    exportFilteredAction->setEnabled(false);
}

void MainWindow::toggleViewMode()
{
    is3DViewActive = !is3DViewActive;
    if (is3DViewActive) {
        plotStackedWidget->setCurrentWidget(plot3DPlaceholder);
        if (zLabel) zLabel->show();
        if (zComboBox) zComboBox->show();
        if (toggleViewAction) toggleViewAction->setText(tr("Switch to 2D Mode"));
    } else {
        plotStackedWidget->setCurrentWidget(plotWidget);
        if (zLabel) zLabel->hide();
        if (zComboBox) zComboBox->hide();
        if (toggleViewAction) toggleViewAction->setText(tr("Switch to 3D Mode"));
    }
    bool canInteractWithPlot = !is3DViewActive && plotWidget != nullptr && !currentPlotPoints.empty();
    if (saveImageAction) saveImageAction->setEnabled(canInteractWithPlot);
    if (resetViewAction) resetViewAction->setEnabled(canInteractWithPlot);
    updatePlot();
    updateLegend();
}


void MainWindow::createToolBar()
{
    axisToolBar = new QToolBar(tr("Axes"), this);
    addToolBar(Qt::TopToolBarArea, axisToolBar);
    axisToolBar->addWidget(new QLabel("X:", this));
    xComboBox = new QComboBox(this);
    xComboBox->setMinimumWidth(150);
    axisToolBar->addWidget(xComboBox);
    axisToolBar->addSeparator();
    axisToolBar->addWidget(new QLabel("Y:", this));
    yComboBox = new QComboBox(this);
    yComboBox->setMinimumWidth(150);
    axisToolBar->addWidget(yComboBox);
    axisToolBar->addSeparator();
    zLabel = new QLabel("Z:", this);
    axisToolBar->addWidget(zLabel);
    zComboBox = new QComboBox(this);
    zComboBox->setMinimumWidth(150);
    axisToolBar->addWidget(zComboBox);
}

void MainWindow::openCsvFile()
{
    QString filePath = QFileDialog::getOpenFileName(this, tr("Open CSV File"), QString(), tr("CSV Files (*.csv);;All Files (*)"));
    if (filePath.isEmpty()) return;
    if (csvLoader && csvLoader->isRunning()) { csvLoader->cancel(); csvLoader->wait(); }
    delete csvLoader;
    csvLoader = new CsvLoader(filePath, this);
    csvLoader->setProperty("filePath", filePath);
    connect(csvLoader, &CsvLoader::loadingFinished, this, &MainWindow::handleCsvLoadingFinished);
    connect(csvLoader, &CsvLoader::errorOccurred, this, &MainWindow::handleCsvLoadingError);
    connect(csvLoader, &CsvLoader::progressUpdated, this, &MainWindow::handleCsvLoadingProgress);
    csvLoader->start();
    statusBar()->showMessage(tr("Loading CSV: %1").arg(QFileInfo(filePath).fileName()));
}

void MainWindow::handleCsvLoadingFinished(const CsvData& data)
{
    currentCsvData.clear();
    currentCsvData = data;

    clearTableFilters(); // This will set currentlyDisplayedData and call updateTableDisplay, updatePlot, updateLegend

    QStringList headersQt;
    for (const std::string& header : currentCsvData.headers) {
        headersQt << QString::fromStdString(header);
    }
    xComboBox->clear(); yComboBox->clear(); zComboBox->clear();
    xComboBox->addItems(headersQt); yComboBox->addItems(headersQt); zComboBox->addItems(headersQt);

    currentEmitterColumn = "";
    int emitterColIdx = -1;
    for (int i = 0; i < headersQt.size(); ++i) {
        if (headersQt[i].contains("emitter", Qt::CaseInsensitive) || headersQt[i].contains("EmitterID", Qt::CaseSensitive)) {
            currentEmitterColumn = headersQt[i];
            emitterColIdx = i;
            qDebug() << "Emitter column identified:" << currentEmitterColumn << "at index" << emitterColIdx;
            break;
        }
    }

    emitterColorMap.clear();
    nextColorIndex = 0;

    if (emitterColIdx != -1) {
        QSet<int> uniqueEmitterIds;
        for (const auto& row : currentCsvData.rows) {
            if (row.size() > emitterColIdx) {
                bool ok;
                int id = QString::fromStdString(row[emitterColIdx]).toInt(&ok);
                if (ok) uniqueEmitterIds.insert(id);
                else uniqueEmitterIds.insert(-2);
            }
        }
        for (int id : uniqueEmitterIds) getEmitterColor(id);
    }

    QString loadedFilePath = csvLoader ? csvLoader->property("filePath").toString() : "";
    statusBar()->showMessage(tr("CSV loaded: %1 rows from %2").arg(data.rows.size()).arg(QFileInfo(loadedFilePath).fileName()), 5000);

    if(csvLoader) { csvLoader->deleteLater(); csvLoader = nullptr; }

    bool canInteract = !is3DViewActive && plotWidget != nullptr && !currentlyDisplayedData.rows.empty();
    if (saveImageAction) saveImageAction->setEnabled(canInteract);
    if (resetViewAction) resetViewAction->setEnabled(canInteract);
    if (exportFilteredAction) exportFilteredAction->setEnabled(!currentlyDisplayedData.rows.empty());
}

void MainWindow::handleCsvLoadingError(const QString& message)
{
    QMessageBox::critical(this, tr("Loading Error"), message);
    statusBar()->showMessage(tr("Error loading CSV: %1").arg(message), 5000);
    currentCsvData.clear();
    currentlyDisplayedData = currentCsvData;
    clearTableFilters(); // Call to reset filters and update display properly

    xComboBox->clear(); yComboBox->clear(); zComboBox->clear();
    // updatePlot() and updateLegend() are called by clearTableFilters

    if (saveImageAction) saveImageAction->setEnabled(false);
    if (resetViewAction) resetViewAction->setEnabled(false);
    if (exportFilteredAction) exportFilteredAction->setEnabled(false);
    if(csvLoader) { csvLoader->deleteLater(); csvLoader = nullptr; }
}

void MainWindow::handleCsvLoadingProgress(int value, const QString& message)
{
    statusBar()->showMessage(tr("Loading... %1% (%2)").arg(value).arg(message));
}

void MainWindow::updateTableDisplay()
{
    tableModel->clear();
    // When clearing filters, headerFilters might be empty if no data was loaded prior.
    // So, clear them only if they were populated.
    if (!headerFilters.isEmpty()) {
      qDeleteAll(headerFilters);
      headerFilters.clear();
    }


    const CsvData& dataToDisplay = currentlyDisplayedData; // Use this consistently

    if (dataToDisplay.headers.empty() && dataToDisplay.rows.empty() && !currentCsvData.headers.empty()) {
        // Case: Filters resulted in no data, but we have original headers to show filter boxes for.
        tableModel->setColumnCount(currentCsvData.headers.size());
        QStringList qHeaders;
        for(const std::string& h : currentCsvData.headers) qHeaders << QString::fromStdString(h);
        tableModel->setHorizontalHeaderLabels(qHeaders);
        tableModel->insertRow(0);
        for (int j = 0; j < currentCsvData.headers.size(); ++j) {
            QLineEdit* filterEdit = new QLineEdit();
            filterEdit->setPlaceholderText(tr("Filter..."));
            headerFilters.append(filterEdit);
            tableView->setIndexWidget(tableModel->index(0, j), filterEdit);
        }
    } else { // Display dataToDisplay (could be all data or filtered data)
        tableModel->setColumnCount(dataToDisplay.headers.size());
        QStringList qHeaders;
        for(const std::string& h : dataToDisplay.headers) qHeaders << QString::fromStdString(h);
        tableModel->setHorizontalHeaderLabels(qHeaders);

        int dataRowOffset = 0;
        if (!dataToDisplay.headers.empty()) {
            tableModel->insertRow(0);
            dataRowOffset = 1;
            for (int j = 0; j < dataToDisplay.headers.size(); ++j) {
                QLineEdit* filterEdit = new QLineEdit();
                filterEdit->setPlaceholderText(tr("Filter..."));
                headerFilters.append(filterEdit);
                tableView->setIndexWidget(tableModel->index(0, j), filterEdit);
            }
        }
        tableModel->setRowCount(dataToDisplay.rows.size() + dataRowOffset);
        for (int i = 0; i < dataToDisplay.rows.size(); ++i) {
            const auto& rowData = dataToDisplay.rows[i];
            for (int j = 0; j < rowData.size() && j < dataToDisplay.headers.size(); ++j) {
                tableModel->setItem(i + dataRowOffset, j, new QStandardItem(QString::fromStdString(rowData[j])));
            }
        }
    }
}

void MainWindow::applyTableFilters()
{
    CsvData tempFilteredData; // Correctly declare here
    tempFilteredData.headers = currentCsvData.headers;
    // tempFilteredData.rows.clear(); // Done by default constructor

    QVector<QString> activeFilters;
    activeFilters.resize(headerFilters.size());
    bool anyFilterActive = false;
    for(int i=0; i<headerFilters.size(); ++i) {
        if (headerFilters[i]) {
            activeFilters[i] = headerFilters[i]->text().trimmed();
            if (!activeFilters[i].isEmpty()) anyFilterActive = true;
        }
    }

    if (!anyFilterActive) {
        currentlyDisplayedData = currentCsvData;
    } else {
        for (const auto& row : currentCsvData.rows) {
            bool matchesAllFilters = true;
            if (row.size() < headerFilters.size()) { // Should not happen if headers match data
                 matchesAllFilters = false; // Or handle error, skip row
            } else {
                for (int j = 0; j < headerFilters.size() && j < row.size(); ++j) { // Iterate only up to available filters/row cells
                    if (!activeFilters[j].isEmpty()) {
                        QString cellValue = QString::fromStdString(row[j]);
                        QString filterText = activeFilters[j];
                        bool currentFilterMatches = false;

                        bool isNumericComparison = false;
                        if (filterText.startsWith('>') || filterText.startsWith('<') || filterText.startsWith('=')) {
                            bool okCell, okFilter;
                            double cellNum = cellValue.toDouble(&okCell);
                             // Handle "=="
                            QString numPart = filterText.mid(filterText.startsWith("==") || filterText.startsWith(">=") || filterText.startsWith("<=") ? 2 : 1);
                            double filterNum = numPart.toDouble(&okFilter);
                            if (okCell && okFilter) {
                                isNumericComparison = true;
                                if (filterText.startsWith(">=")) currentFilterMatches = (cellNum >= filterNum);
                                else if (filterText.startsWith("<=")) currentFilterMatches = (cellNum <= filterNum);
                                else if (filterText.startsWith('>')) currentFilterMatches = (cellNum > filterNum);
                                else if (filterText.startsWith('<')) currentFilterMatches = (cellNum < filterNum);
                                else if (filterText.startsWith("==")) currentFilterMatches = (cellNum == filterNum);
                                else if (filterText.startsWith('=')) currentFilterMatches = (cellNum == filterNum);
                            }
                        } else if (filterText.contains(':')) {
                            QStringList rangeParts = filterText.split(':');
                            if (rangeParts.size() == 2) {
                                bool okMin, okMax, okCell;
                                double cellNum = cellValue.toDouble(&okCell);
                                double minVal = rangeParts[0].toDouble(&okMin);
                                double maxVal = rangeParts[1].toDouble(&okMax);
                                if (okCell && okMin && okMax) {
                                    isNumericComparison = true;
                                    currentFilterMatches = (cellNum >= minVal && cellNum <= maxVal);
                                }
                            }
                        }

                        if (!isNumericComparison) {
                            currentFilterMatches = cellValue.contains(filterText, Qt::CaseInsensitive);
                        }

                        if (!currentFilterMatches) {
                            matchesAllFilters = false;
                            break;
                        }
                    }
                }
            }
            if (matchesAllFilters) {
                tempFilteredData.rows.push_back(row);
            }
        }
        currentlyDisplayedData = tempFilteredData;
    }

    updateTableDisplay();
    updatePlot();
    updateLegend();
    if (exportFilteredAction) exportFilteredAction->setEnabled(!currentlyDisplayedData.rows.empty());
}

void MainWindow::clearTableFilters()
{
    for (QLineEdit* filterEdit : headerFilters) {
        if (filterEdit) filterEdit->clear();
    }
    currentlyDisplayedData = currentCsvData;
    updateTableDisplay(); // Will re-setup filters in first row
    updatePlot();
    updateLegend();
    if (exportFilteredAction) exportFilteredAction->setEnabled(!currentlyDisplayedData.rows.empty());
}


void MainWindow::updatePlot()
{
    currentPlotPoints.clear();
    currentPlotEmitterIds.clear();
    currentPlotXLabel = "X-Axis";
    currentPlotYLabel = "Y-Axis";
    currentPlotTitle = "Plot";

    if (is3DViewActive) {
        if (plotWidget) plotWidget->setData(currentPlotPoints, currentPlotEmitterIds, emitterColorMap, currentPlotXLabel, currentPlotYLabel, "3D View Active");
        if (saveImageAction) saveImageAction->setEnabled(false);
        if (resetViewAction) resetViewAction->setEnabled(false);
        return;
    }

    if (!plotWidget) return;

    QString xColName = xComboBox->currentText();
    QString yColName = yComboBox->currentText();
    QString plotTitleText = "2D Plot: " + yColName + " vs " + xColName;

    QVector<QPointF> points;
    QVector<int> emitterIdsForPlot;

    if (xColName.isEmpty() || yColName.isEmpty() || currentlyDisplayedData.rows.empty()) {
        plotWidget->setData(points, emitterIdsForPlot, emitterColorMap, "X-Axis", "Y-Axis", "Plot");
        currentPlotPoints = points; currentPlotEmitterIds = emitterIdsForPlot; currentPlotXLabel = "X-Axis"; currentPlotYLabel = "Y-Axis"; currentPlotTitle = "Plot";
        bool canInteract = !is3DViewActive && plotWidget != nullptr && !currentPlotPoints.empty();
        if (saveImageAction) saveImageAction->setEnabled(canInteract);
        if (resetViewAction) resetViewAction->setEnabled(canInteract);
        return;
    }

    int xColIdx = -1, yColIdx = -1, emitterColIdx = -1;
    for (int i = 0; i < currentlyDisplayedData.headers.size(); ++i) {
        QString header = QString::fromStdString(currentlyDisplayedData.headers[i]);
        if (header == xColName) xColIdx = i;
        if (header == yColName) yColIdx = i;
        if (header == currentEmitterColumn) emitterColIdx = i;
    }

    if (xColIdx == -1 || yColIdx == -1) {
        qDebug() << "Selected column(s) for plotting not found in headers.";
        plotWidget->setData(points, emitterIdsForPlot, emitterColorMap,
                               xColName.isEmpty() ? "X-Axis (Error)" : xColName,
                               yColName.isEmpty() ? "Y-Axis (Error)" : yColName,
                               "Invalid Columns");
        currentPlotPoints = points; currentPlotEmitterIds = emitterIdsForPlot; currentPlotXLabel = xColName.isEmpty() ? "X-Axis (Error)" : xColName; currentPlotYLabel = yColName.isEmpty() ? "Y-Axis (Error)" : yColName; currentPlotTitle = "Invalid Columns";
        bool canInteract = !is3DViewActive && plotWidget != nullptr && !currentPlotPoints.empty();
        if (saveImageAction) saveImageAction->setEnabled(canInteract);
        if (resetViewAction) resetViewAction->setEnabled(canInteract);
        return;
    }

    points.reserve(currentlyDisplayedData.rows.size());
    if (emitterColIdx != -1) {
        emitterIdsForPlot.reserve(currentlyDisplayedData.rows.size());
    }

    bool conversionOkX, conversionOkY, conversionOkEmitter;
    for (const auto& row : currentlyDisplayedData.rows) {
        if (row.size() > xColIdx && row.size() > yColIdx) {
            double xVal = QString::fromStdString(row[xColIdx]).toDouble(&conversionOkX);
            double yVal = QString::fromStdString(row[yColIdx]).toDouble(&conversionOkY);

            int emitterId = -1;
            if (emitterColIdx != -1 && row.size() > emitterColIdx) {
                emitterId = QString::fromStdString(row[emitterColIdx]).toInt(&conversionOkEmitter);
                if (!conversionOkEmitter) emitterId = -2;
            }

            if (conversionOkX && conversionOkY) {
                points.append(QPointF(xVal, yVal));
                emitterIdsForPlot.append(emitterId);
            } else {
                 qDebug() << "Conversion error for point data, X:" << QString::fromStdString(row[xColIdx]) << "Y:" << QString::fromStdString(row[yColIdx]);
            }
        }
    }

    currentPlotPoints = points;
    currentPlotEmitterIds = emitterIdsForPlot;
    currentPlotXLabel = xColName;
    currentPlotYLabel = yColName;
    currentPlotTitle = plotTitleText;

    plotWidget->setData(currentPlotPoints, currentPlotEmitterIds, emitterColorMap, currentPlotXLabel, currentPlotYLabel, currentPlotTitle);
    bool canInteract = !currentPlotPoints.empty(); // Check if there are points to interact with
    if (saveImageAction) saveImageAction->setEnabled(!is3DViewActive && plotWidget != nullptr && canInteract);
    if (resetViewAction) resetViewAction->setEnabled(!is3DViewActive && plotWidget != nullptr && canInteract);
}


void MainWindow::savePlotImage()
{
    if (is3DViewActive || !plotWidget || !plotWidget->isVisible()) {
        QMessageBox::information(this, tr("Save Image"), tr("Save image is not available for the 3D view or when the 2D plot is not visible."));
        return;
    }
    if (currentPlotPoints.empty()) { // Use .empty() for QVector
        QMessageBox::information(this, tr("Save Image"), tr("No data to save in the plot."));
        return;
    }

    QString filePath = QFileDialog::getSaveFileName(this, tr("Save Plot Image"), "", tr("PNG Images (*.png);;JPEG Images (*.jpg *.jpeg);;All Files (*)"));
    if (filePath.isEmpty()) {
        return;
    }

    QPixmap pixmap(plotWidget->size());
    plotWidget->render(&pixmap);
    bool success = pixmap.save(filePath);

    if (success) {
        statusBar()->showMessage(tr("Plot saved to %1").arg(filePath), 5000);
    } else {
        QMessageBox::warning(this, tr("Save Image Error"), tr("Could not save image to %1.").arg(filePath));
    }
}

void MainWindow::resetPlotView()
{
    if (is3DViewActive || !plotWidget) {
        QMessageBox::information(this, tr("Reset View"), tr("Reset view is not applicable to the 3D view or if the plot is not available."));
        return;
    }
    plotWidget->setData(currentPlotPoints, currentPlotEmitterIds, emitterColorMap, currentPlotXLabel, currentPlotYLabel, currentPlotTitle);
    statusBar()->showMessage(tr("Plot view reset."), 3000);
}

void MainWindow::exportFilteredData()
{
    if (currentlyDisplayedData.rows.empty()) { // Use .empty() for std::vector
        QMessageBox::information(this, tr("Export Data"), tr("No filtered data to export."));
        return;
    }

    QString filePath = QFileDialog::getSaveFileName(this, tr("Export Filtered Data"), "", tr("CSV Files (*.csv);;All Files (*)"));
    if (filePath.isEmpty()) {
        return;
    }

    QFile file(filePath);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Text)) {
        QMessageBox::warning(this, tr("Export Error"), tr("Could not open file for writing: %1").arg(file.errorString()));
        return;
    }

    QTextStream out(&file);

    QStringList qHeaders;
    for(const std::string& h : currentlyDisplayedData.headers) { // Use .headers
        qHeaders << QString::fromStdString(h);
    }
    out << qHeaders.join(',') << "\n";

    for (const auto& row : currentlyDisplayedData.rows) { // Use .rows
        QStringList qRow;
        for (const std::string& field : row) {
            QString qField = QString::fromStdString(field);
            if (qField.contains(',') || qField.contains('"') || qField.contains('\n')) {
                qField.replace("\"", "\"\"");
                qField = "\"" + qField + "\"";
            }
            qRow << qField;
        }
        out << qRow.join(',') << "\n";
    }

    file.close();
    statusBar()->showMessage(tr("Filtered data exported to %1").arg(filePath), 5000);
}
