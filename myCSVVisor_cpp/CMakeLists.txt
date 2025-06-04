cmake_minimum_required(VERSION 3.16)
project(myCSVVisorCpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets)

add_executable(myCSVVisorCpp
    main.cpp
    mainwindow.cpp
    mainwindow.h
    csvloader.cpp
    csvloader.h
    simpleplotwidget.cpp
    simpleplotwidget.h
    placeholder3dwidget.cpp # Added Placeholder3DWidget
    placeholder3dwidget.h
)

target_link_libraries(myCSVVisorCpp PRIVATE Qt6::Widgets)
