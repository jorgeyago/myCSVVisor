#include "csvloader.h"
#include <QFile>
#include <QTextStream>
#include <QDebug> // For debugging output, can be removed later

CsvLoader::CsvLoader(const QString& filePath, QObject* parent)
    : QThread(parent), filePath(filePath)
{
}

void CsvLoader::cancel()
{
    isCancelled = true;
}

void CsvLoader::run()
{
    CsvData csvData;
    QFile file(filePath);

    if (!file.exists()) {
        emit errorOccurred(QString("File not found: %1").arg(filePath));
        return;
    }

    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        emit errorOccurred(QString("Failed to open file: %1. Error: %2").arg(filePath, file.errorString()));
        return;
    }

    QTextStream in(&file);
    long long fileSize = file.size();
    long long bytesRead = 0;
    int rowsLoaded = 0;

    // Read header
    if (!in.atEnd()) {
        QString headerLine = in.readLine();
        bytesRead += headerLine.toUtf8().size() + 1; // +1 for newline
        QStringList headerFields = headerLine.split(',');
        for (const QString& field : headerFields) {
            csvData.headers.push_back(field.trimmed().toStdString());
        }
        emit progressUpdated(0, "Header loaded.");
    } else {
        emit errorOccurred("File is empty or header could not be read.");
        file.close();
        return;
    }

    if (isCancelled) {
        file.close();
        emit errorOccurred("Loading cancelled by user.");
        return;
    }

    // Read rows
    while (!in.atEnd() && rowsLoaded < MAX_ROWS_TO_LOAD) {
        if (isCancelled) {
            break;
        }
        QString line = in.readLine();
        bytesRead += line.toUtf8().size() + 1; // +1 for newline

        // Basic CSV parsing: split by comma
        // This simple parsing does not handle quoted fields containing commas or escaped quotes.
        QStringList stringFields = line.split(',');
        std::vector<std::string> row;
        for (const QString& field : stringFields) {
            row.push_back(field.trimmed().toStdString());
        }
        csvData.rows.push_back(row);
        rowsLoaded++;

        if (rowsLoaded % 1000 == 0) { // Update progress every 1000 rows
            int percentage = (fileSize > 0) ? static_cast<int>((bytesRead * 100) / fileSize) : 0;
            if (percentage > 100) percentage = 100; // Cap at 100
            emit progressUpdated(percentage, QString("%1 rows loaded...").arg(rowsLoaded));
        }
    }

    file.close();

    if (isCancelled) {
        emit errorOccurred("Loading cancelled by user during row processing.");
    } else if (rowsLoaded == 0 && csvData.headers.empty()) {
        // This case might be redundant if header check already covers it
        emit errorOccurred("No data loaded from CSV.");
    } else if (rowsLoaded == 0 && !csvData.headers.empty()) {
        // Headers loaded but no data rows
        emit loadingFinished(csvData);
    }
    else {
        // Ensure final progress update
        emit progressUpdated(100, QString("Finished loading %1 rows.").arg(rowsLoaded));
        emit loadingFinished(csvData);
    }
}
