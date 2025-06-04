#ifndef CSVLOADER_H
#define CSVLOADER_H

#include <QThread>
#include <QString>
#include <QObject> // Required for Q_OBJECT
#include "csvdata.h"

class CsvLoader : public QThread
{
    Q_OBJECT

public:
    explicit CsvLoader(const QString& filePath, QObject* parent = nullptr);
    void cancel();

signals:
    void progressUpdated(int value, const QString& message);
    void loadingFinished(const CsvData& data); // Pass by const reference
    void errorOccurred(const QString& message);

protected:
    void run() override;

private:
    QString filePath;
    volatile bool isCancelled = false; // Marked volatile as it's accessed by different threads
    const int MAX_ROWS_TO_LOAD = 50000;
};

#endif // CSVLOADER_H
