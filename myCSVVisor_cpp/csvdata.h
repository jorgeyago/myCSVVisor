#ifndef CSVDATA_H
#define CSVDATA_H

#include <vector>
#include <string>
#include <numeric> // For std::all_of if needed, or other utilities

struct CsvData {
    std::vector<std::string> headers;
    std::vector<std::vector<std::string>> rows;

    void clear() {
        headers.clear();
        rows.clear();
    }

    bool isEmpty() const {
        return headers.empty() && rows.empty();
    }
};

#endif // CSVDATA_H
