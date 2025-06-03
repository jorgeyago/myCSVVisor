import sys
import os
import pandas as pd
import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from dataclasses import dataclass
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QComboBox, QFileDialog, QTableWidget, QTableWidgetItem,
    QSplitter, QLabel, QMessageBox, QHeaderView, QLineEdit,
    QMenuBar, QMenu, QDockWidget, QTextEdit, QToolBar, QProgressDialog,
    QDialog, QScrollArea, QSizePolicy, QGridLayout, QStatusBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6 import QtGui
from PyQt6.QtGui import QIcon, QColor, QBrush, QFont, QPalette, QKeySequence, QAction, QPixmap
from PyQt6.QtCore import QThread, pyqtSignal
import threading

try:
    import psutil
except ImportError:
    psutil = None


# --- Dataclass para colores de ejes y otros colores globales ---
@dataclass
class AxisColors:
    x: str = '#ff3333'  # Rojo eje X
    y: str = '#33ff33'  # Verde eje Y
    z: str = '#3399ff'  # Azul eje Z (por si se usa en el futuro)

AXIS_COLORS = AxisColors()

# Constantes globales para colores - Sin rojo para mejor contraste con el marcador de selección
VIBRANT_COLORS = [
    '#00FF00',  # Verde brillante
    '#0000FF',  # Azul
    '#00FFFF',  # Cian
    '#FF00FF',  # Magenta
    '#FFFF00',  # Amarillo
    '#1E90FF',  # Azul dodger
    '#00CED1',  # Turquesa oscuro
    '#32CD32',  # Verde lima
    '#9370DB',  # Púrpura medio
    '#20B2AA',  # Verde mar claro
    '#00FA9A',  # Verde primavera medio
    '#4169E1',  # Azul real
    '#7B68EE',  # Azul pizarra medio
    '#6495ED',  # Azul aciano
    '#48D1CC',  # Turquesa medio
    '#3CB371',  # Verde mar medio
    '#87CEEB',  # Azul cielo
    '#40E0D0',  # Turquesa
    '#4682B4',  # Azul acero
    '#66CDAA',  # Aguamarina medio
    '#008B8B',  # Cian oscuro
    '#006400',  # Verde oscuro
    '#0000CD',  # Azul medio
    '#483D8B'   # Azul pizarra oscuro
]
NOISE_COLOR = '#888888'
MAX_CSV_ROWS_TO_LOAD = 50000  # Maximum number of rows to load from a CSV file

# Configurar PyQtGraph
pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', '#2b2b2b')
pg.setConfigOption('foreground', 'w')

class CSVLoaderThread(QThread):
    progress_updated = pyqtSignal(int, str)
    loading_finished = pyqtSignal(pd.DataFrame)
    error_occurred = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            # Fase 1: Lectura del archivo
            chunks = []
            total_rows = 0
            processed_rows = 0
            # Contar filas totales
            with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
                total_rows = sum(1 for _ in f)
            if total_rows == 0:
                raise Exception("El archivo está vacío.")
            chunk_size = MAX_CSV_ROWS_TO_LOAD
            for idx, chunk in enumerate(pd.read_csv(
                self.file_path,
                dtype=str,
                keep_default_na=False,
                chunksize=chunk_size
            )):
                if self._is_cancelled:
                    return
                # Limitar la cantidad de filas cargadas
                if processed_rows + len(chunk) > MAX_CSV_ROWS_TO_LOAD:
                    chunk = chunk.iloc[:MAX_CSV_ROWS_TO_LOAD - processed_rows]
                chunks.append(chunk)
                processed_rows += len(chunk)
                # Emitir progreso
                progress = int(100 * processed_rows / MAX_CSV_ROWS_TO_LOAD)
                message = (
                    f"Cargando {os.path.basename(self.file_path)}...\n"
                    f"Filas procesadas: {processed_rows:,} de {min(total_rows, MAX_CSV_ROWS_TO_LOAD):,} "
                    f"({min(processed_rows, MAX_CSV_ROWS_TO_LOAD)/MAX_CSV_ROWS_TO_LOAD:.1%})"
                )
                self.progress_updated.emit(progress, message)
                if processed_rows >= MAX_CSV_ROWS_TO_LOAD:
                    # Mensaje especial si hay más de MAX_CSV_ROWS_TO_LOAD filas
                    if total_rows > MAX_CSV_ROWS_TO_LOAD:
                        self.error_occurred.emit(f"El archivo tiene más de {MAX_CSV_ROWS_TO_LOAD} filas")
                        return
                    break
            if not chunks:
                self.error_occurred.emit("No se pudieron cargar datos del archivo.")
                return
            df = pd.concat(chunks, ignore_index=True)
            self.progress_updated.emit(100, "Procesando tipos de datos...")

            # Fase 2: Conversión de tipos
            def convert_column(column):
                try:
                    float_col = pd.to_numeric(column, errors='coerce')
                    if float_col.isnull().any():
                        return column
                    if all(float_col % 1 == 0):
                        return float_col.astype(int)
                    return float_col.map(lambda x: f"{x:.3f}" if not pd.isnull(x) else x)
                except:
                    return column

            cols = df.columns
            for i, col in enumerate(cols):
                if self._is_cancelled:
                    return
                
                df[col] = convert_column(df[col])
                progress = 100 + int(100 * (i + 1) / len(cols))
                self.progress_updated.emit(
                    progress, 
                    f"Procesando columna {i+1} de {len(cols)}: {col}"
                )

            # Emitir resultado final
            self.loading_finished.emit(df)

        except Exception as e:
            self.error_occurred.emit(str(e))

class NoSciAxis(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [f"{v:.3f}".rstrip('0').rstrip('.') if abs(v) < 1e6 else f"{v:.0f}" for v in values]

class InfiniteGrid(gl.GLGridItem):
    def __init__(self, orientation='xy', color='#555555'):
        super().__init__()
        self.orientation = orientation
        self.rotate(90, 1, 0, 0) if orientation == 'xz' else None
        self.rotate(90, 0, 1, 0) if orientation == 'yz' else None
        
        self.setColor(color)
        self.setSpacing(1, 1, 1)
        
        if orientation == 'xy':
            self.setSize(x=1000, y=1000, z=0)
        elif orientation == 'xz':
            self.setSize(x=1000, y=0, z=1000)
        elif orientation == 'yz':
            self.setSize(x=0, y=1000, z=1000)
        
        self.setGLOptions('opaque')

class GLPlotWidget(gl.GLViewWidget):
    pointSelected = pyqtSignal(int)
    
    def __init__(self, parent=None, emitter_color_map=None):
        super().__init__(parent)
        self.emitter_color_map = emitter_color_map or {}
        self.color_index = 0
        self.color_step = 1
        self.setBackgroundColor('#2b2b2b')
        self.setCameraPosition(distance=50, elevation=30, azimuth=45)
        
        self.scatter = None
        self.highlighted_point = None
        self.df = None
        self.x_col = None
        self.y_col = None
        self.z_col = None
        self.axis_labels = []
        
        # Configurar planos y ejes
        self.xy_plane = InfiniteGrid(orientation='xy', color='#555555')
        self.xz_plane = InfiniteGrid(orientation='xz', color='#444444')
        self.yz_plane = InfiniteGrid(orientation='yz', color='#333333')
        
        self.addItem(self.xy_plane)
        self.addItem(self.xz_plane)
        self.addItem(self.yz_plane)
        self.add_infinite_axes()

    def clear(self):
        """Sobrescribe el método clear para manejar correctamente las etiquetas"""
        # Primero eliminar las etiquetas
        if hasattr(self, 'axis_labels'):
            for label in self.axis_labels:
                self.removeItem(label)
            self.axis_labels.clear()
        
        # Eliminar todos los demás items
        items_to_remove = [item for item in self.items if item not in [self.x_axis, self.y_axis, self.z_axis]]
        for item in items_to_remove:
            self.removeItem(item)

    def create_axis_label(self, pos, text, color):
        """Crea una etiqueta de texto para un eje"""
        text_item = gl.GLTextItem(pos=pos, text=text, color=color, font=QtGui.QFont('Helvetica', 16))
        self.axis_labels.append(text_item)
        self.addItem(text_item)
        return text_item
        

    def add_infinite_axes(self, axis_length=1e6, x_label="X", y_label="Y", z_label="Z"):
        # Usar los nombres de los combos para los ejes
        self.axis_label_coords = [
            (np.array([axis_length, 0, 0]), x_label, 'color: #ff3333; font-weight: bold;'),
            (np.array([0, axis_length, 0]), y_label, 'color: #33ff33; font-weight: bold;'),
            (np.array([0, 0, axis_length]), z_label, 'color: #33bfff; font-weight: bold;'),
        ]
        # Limpiar etiquetas existentes
        for label in getattr(self, 'axis_labels', []):
            if hasattr(label, 'deleteLater'):
                label.deleteLater()
        self.axis_labels = []

        # Crear los ejes
        self.x_axis = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [axis_length, 0, 0]]),
            color=(1, 0, 0, 1), width=2, antialias=True, mode='lines'
        )
        self.y_axis = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [0, axis_length, 0]]),
            color=(0, 1, 0, 1), width=2, antialias=True, mode='lines'
        )
        self.z_axis = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [0, 0, axis_length]]),
            color=(0, 0.7, 1, 1), width=2, antialias=True, mode='lines'
        )

        # Añadir ejes
        self.addItem(self.x_axis)
        self.addItem(self.y_axis)
        self.addItem(self.z_axis)

        self.update()

    def plot_data(self, df, x_col, y_col, z_col, emitter_col=None):
        try:
            if df is None or x_col not in df.columns or y_col not in df.columns or z_col not in df.columns:
                return

            # Guardamos referencia de los ejes y etiquetas
            preserved_items = [self.xy_plane, self.xz_plane, self.yz_plane, 
                             self.x_axis, self.y_axis, self.z_axis]
            preserved_items.extend(self.axis_labels)
                    
            # Limpiamos solo los elementos de datos
            items_to_remove = [item for item in self.items if item not in preserved_items]
            for item in items_to_remove:
                self.removeItem(item)

            self.df = df
            self.x_col = x_col
            self.y_col = y_col
            self.z_col = z_col
            
            x = pd.to_numeric(df[x_col], errors='coerce').fillna(0).values
            y = pd.to_numeric(df[y_col], errors='coerce').fillna(0).values
            z = pd.to_numeric(df[z_col], errors='coerce').fillna(0).values
            
            # Normalizar datos para mejor visualización
            def normalize(arr):
                arr_min, arr_max = arr.min(), arr.max()
                return (arr - arr_min) / (arr_max - arr_min) * 20 if arr_max != arr_min else arr
                
            x = normalize(x)
            y = normalize(y)
            z = normalize(z)
            if emitter_col and emitter_col in df.columns:
                emitters = df[emitter_col].unique()
                
                for emitter in emitters:
                    mask = (df[emitter_col] == emitter).values
                    emitter_x = x[mask]
                    emitter_y = y[mask]
                    emitter_z = z[mask]
                    
                    if len(emitter_x) > 0:
                        pos = np.column_stack([emitter_x, emitter_y, emitter_z])
                        color = self.get_emitter_color(emitter, for_3d=True)
                        
                        # Convertir color a RGBA normalizado para OpenGL
                        def to_rgba(color):
                            if isinstance(color, str):
                                qcolor = QColor(color)
                                return (
                                    qcolor.red() / 255.0,
                                    qcolor.green() / 255.0,
                                    qcolor.blue() / 255.0,
                                    1.0
                                )
                            elif isinstance(color, (tuple, list)) and len(color) == 4:
                                # Si ya es RGBA normalizado
                                return tuple(float(c) for c in color)
                            return (0.5, 0.5, 0.5, 1.0)
                        scatter = gl.GLScatterPlotItem(
                            pos=pos,
                            color=to_rgba(color),
                            size=4,
                            pxMode=True,
                            glOptions='additive'
                        )
                        self.addItem(scatter)
            else:
                pos = np.column_stack([x, y, z])                # Color por defecto en formato RGBA correcto para OpenGL
                default_color = (0.26, 0.65, 0.96, 1.0)
                scatter = gl.GLScatterPlotItem(
                    pos=pos,
                    color=default_color,
                    size=4,
                    pxMode=True,
                    glOptions='additive'
                )
                self.addItem(scatter)
            
            self.auto_range()
            
        except Exception as e:
            print(f"Error plotting 3D data: {e}")
            QMessageBox.warning(self, "Error", f"No se pudo graficar en 3D:\n{str(e)}")
    
    def get_emitter_color(self, emitter, for_3d=False):
        # Determinar el color base
        if emitter is None or (isinstance(emitter, str) and emitter.strip() == ""):
            color = NOISE_COLOR
        else:
            try:
                if isinstance(emitter, str):
                    emitter = int(emitter)
                
                if emitter < 0:
                    color = NOISE_COLOR
                else:
                    if emitter not in self.emitter_color_map:
                        # Si es el primer emisor, inicializar el mapa de colores
                        if not self.emitter_color_map:
                            # Contar emisores únicos para optimizar la distribución de colores
                            unique_emitters = set()
                            try:
                                if hasattr(self, 'df') and self.df is not None:
                                    emitter_col = next((col for col in self.df.columns if 'emit' in col.lower()), None)
                                    if emitter_col:
                                        unique_emitters = set(self.df[emitter_col].unique())
                            except Exception:
                                pass
                            
                            # Ajustar el espaciado de colores según el número de emisores
                            num_emitters = max(len(unique_emitters), 1)
                            step = max(1, len(VIBRANT_COLORS) // num_emitters)
                            self.color_index = 0
                            self.color_step = step
                        
                        # Asignar color con espaciado uniforme
                        color_idx = (self.color_index * self.color_step) % len(VIBRANT_COLORS)
                        color = VIBRANT_COLORS[color_idx]
                        self.emitter_color_map[emitter] = color
                        self.color_index += 1
                    
                    color = self.emitter_color_map[emitter]
            except Exception:
                color = NOISE_COLOR

        # Convertir a formato RGBA para OpenGL si es necesario
        if for_3d:
            try:
                if isinstance(color, str):
                    qcolor = QColor(color)
                    if not qcolor.isValid():
                        print(f"Color inválido: {color}, usando color por defecto")
                        return (0.5, 0.5, 0.5, 1.0)  # Gray as default
                    # Ensure float values between 0 and 1
                    return (qcolor.redF(), qcolor.greenF(), qcolor.blueF(), 1.0)
                elif isinstance(color, (tuple, list)):
                    if len(color) == 3:
                        # Convert RGB to RGBA with alpha=1.0
                        rgb = [c/255 if isinstance(c, int) else float(c) for c in color]
                        return (rgb[0], rgb[1], rgb[2], 1.0)
                    elif len(color) == 4:
                        # Convert RGBA values to floats between 0 and 1
                        return tuple(c/255 if isinstance(c, int) else float(c) for c in color)
                print(f"Formato de color no soportado: {color}, usando color por defecto")
                return (0.5, 0.5, 0.5, 1.0)  # Gray as default
            except Exception as e:
                print(f"Error al convertir color: {e}, usando color por defecto")
                return (0.5, 0.5, 0.5, 1.0)  # Gray as default
        
        return color
        
        return color
        
    def auto_range(self):
        bounds = None
        for item in self.items:
            if isinstance(item, gl.GLScatterPlotItem):
                pos = item.pos
                if pos is not None and len(pos) > 0:
                    min_bounds = pos.min(axis=0)
                    max_bounds = pos.max(axis=0)
                    if bounds is None:
                        bounds = (min_bounds, max_bounds)
                    else:
                        bounds = (
                            np.minimum(bounds[0], min_bounds),
                            np.maximum(bounds[1], max_bounds)
                        )

        if bounds:
            center = (bounds[0] + bounds[1]) / 2
            size = np.linalg.norm(bounds[1] - bounds[0])
            center_vector = pg.Vector(center[0], center[1], center[2])
            self.setCameraPosition(pos=center_vector, distance=size * 2)
            
    def highlight_point(self, index):

        if index is None or self.df is None or self.x_col is None or self.y_col is None or self.z_col is None:
            if self.highlighted_point:
                for item in self.highlighted_point:
                    if item in self.items:
                        self.removeItem(item)
                self.highlighted_point = None
            return

        try:
            if index < 0 or index >= len(self.df):
                if self.highlighted_point:
                    for item in self.highlighted_point:
                        if item in self.items:
                            self.removeItem(item)
                    self.highlighted_point = None
                return

            # Obtener valores originales
            x = pd.to_numeric(self.df.iloc[index][self.x_col], errors='coerce')
            y = pd.to_numeric(self.df.iloc[index][self.y_col], errors='coerce')
            z = pd.to_numeric(self.df.iloc[index][self.z_col], errors='coerce')

            # Normalizar igual que en plot_data
            def normalize_val(val, arr):
                arr_min, arr_max = arr.min(), arr.max()
                if arr_max != arr_min:
                    return (val - arr_min) / (arr_max - arr_min) * 20
                else:
                    return val

            # Usar los mismos datos que plot_data
            x_arr = pd.to_numeric(self.df[self.x_col], errors='coerce').fillna(0).values
            y_arr = pd.to_numeric(self.df[self.y_col], errors='coerce').fillna(0).values
            z_arr = pd.to_numeric(self.df[self.z_col], errors='coerce').fillna(0).values
            x = normalize_val(x, x_arr)
            y = normalize_val(y, y_arr)
            z = normalize_val(z, z_arr)

            if np.isnan(x) or np.isnan(y) or np.isnan(z):
                if self.highlighted_point:
                    for item in self.highlighted_point:
                        if item in self.items:
                            self.removeItem(item)
                    self.highlighted_point = None
                return

            if self.highlighted_point:
                for item in self.highlighted_point:
                    if item in self.items:
                        self.removeItem(item)
                self.highlighted_point = None

            # Tamaños aún más pequeños y proporcionales al rango normalizado (0-20)
            data_range = 20.0
            halo_size = data_range * 0.035  # 0.7
            border_size = data_range * 0.018  # 0.36
            core_size = data_range * 0.011  # 0.22

            halo = gl.GLScatterPlotItem(
                pos=np.array([[x, y, z]]),
                size=halo_size,
                color=(1, 0, 0, 0.28),  # rojo translúcido
                pxMode=False,
                glOptions='additive'
            )
            border = gl.GLScatterPlotItem(
                pos=np.array([[x, y, z]]),
                size=border_size,
                color=(1, 0, 0, 0.7),  # rojo intenso
                pxMode=False,
                glOptions='additive'
            )
            core = gl.GLScatterPlotItem(
                pos=np.array([[x, y, z]]),
                size=core_size,
                color=(1, 0, 0, 1),  # rojo puro
                pxMode=False,
                glOptions='additive'
            )
            self.addItem(halo)
            self.addItem(border)
            self.addItem(core)
            self.highlighted_point = (halo, border, core)

            current_distance = self.opts['distance']
            self.opts['center'] = pg.Vector(x, y, z)
            self.setCameraPosition(pos=self.opts['center'], distance=current_distance)

        except Exception as e:
            print(f"Error highlighting 3D point: {e}")
            if self.highlighted_point:
                for item in self.highlighted_point:
                    if item in self.items:
                        self.removeItem(item)
                self.highlighted_point = None

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)

class HistogramWindow(QDialog):
    def __init__(self, parent, columns, data):
        super().__init__(parent)
        self.setWindowTitle("Histogramas de pulsos")
        self.setMinimumWidth(900)
        self.setMinimumHeight(700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.data = data
        self.columns = columns

        # Scroll area para permitir desplazamiento si hay muchas columnas
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        main_widget = QWidget()
        scroll.setWidget(main_widget)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll)

        # GridLayout para los histogramas, responsive
        grid = QGridLayout(main_widget)
        grid.setSpacing(20)
        main_widget.setLayout(grid)

        # Crear un histograma por columna
        self.hist_plots = []
        self.tooltip_labels = []

        n_cols = 2 if len(self.columns) < 4 else 3
        for idx, col in enumerate(self.columns):
            plot_widget = pg.PlotWidget()
            plot_widget.setBackground('#232323')
            plot_widget.getAxis('bottom').setPen('w')
            plot_widget.getAxis('left').setPen('w')
            plot_widget.showGrid(x=True, y=True, alpha=0.3)
            plot_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            plot_widget.setMinimumHeight(250)
            plot_widget.setMinimumWidth(350)

            # Etiqueta flotante para mostrar el valor
            tooltip_label = QLabel(plot_widget)
            tooltip_label.setStyleSheet(
                "background-color: #232323; color: #fff; border: 1px solid #888; padding: 2px; border-radius: 3px;"
            )
            tooltip_label.setVisible(False)
            tooltip_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            # Calcular histograma
            series = pd.to_numeric(self.data[col], errors='coerce')
            series = series.dropna()
            if not series.empty:
                bins = min(50, max(10, int(np.sqrt(len(series)))))
                y, x = np.histogram(series, bins=bins)
                bg = pg.BarGraphItem(x=x[:-1], height=y, width=(x[1]-x[0]), brush='#42A5F5')
                plot_widget.addItem(bg)
                plot_widget.setLabel('bottom', col)
                plot_widget.setLabel('left', 'Cantidad de pulsos')
                plot_widget.setTitle(f"Histograma de {col}")
                # Guardar datos para tooltip
                plot_widget._hist_x = x
                plot_widget._hist_y = y
                plot_widget._hist_series = series  # <-- Guardar la serie real para el tooltip
            else:
                plot_widget._hist_x = None
                plot_widget._hist_y = None
                plot_widget._hist_series = None

            # Conectar evento de mouse
            def make_mouse_move_handler(plot_widget):
                def on_mouse_moved(pos):
                    if (not hasattr(plot_widget, "_hist_x") or plot_widget._hist_x is None or 
                        plot_widget._hist_y is None or plot_widget._hist_series is None):
                        tooltip_label.setVisible(False)
                        return
                    vb = plot_widget.getViewBox()
                    mouse_point = vb.mapSceneToView(pos)
                    x_val = mouse_point.x()
                    y_val = mouse_point.y()
                    x_bins = plot_widget._hist_x
                    y_bins = plot_widget._hist_y
                    series = plot_widget._hist_series
                    idx_bin = np.searchsorted(x_bins, x_val, side='right') - 1
                    if 0 <= idx_bin < len(y_bins):
                        bin_left = x_bins[idx_bin]
                        bin_right = x_bins[idx_bin+1]
                        count = y_bins[idx_bin]
                        if bin_left <= x_val < bin_right and y_val >= 0:
                            # Filtrar los valores que caen en el bin
                            real_xs = series[(series >= bin_left) & (series < bin_right)]
                            real_xs_str = ", ".join([f"{v:.3f}" for v in real_xs[:10]])
                            if len(real_xs) > 10:
                                real_xs_str += ", ..."
                            tooltip_label.setText(f"Pulsos: {count}\nValores X: {real_xs_str}")
                            cursor_pos = plot_widget.mapFromGlobal(QtGui.QCursor.pos())
                            tooltip_label.move(cursor_pos.x() + 10, cursor_pos.y() - 20)
                            tooltip_label.setVisible(True)
                            return
                    tooltip_label.setVisible(False)
                return on_mouse_moved

            plot_widget.scene().sigMouseMoved.connect(make_mouse_move_handler(plot_widget))

            self.hist_plots.append(plot_widget)
            self.tooltip_labels.append(tooltip_label)
            row = idx // n_cols
            col_idx = idx % n_cols
            grid.addWidget(plot_widget, row, col_idx)

        # --- NUEVO: Botones de filtros en la parte inferior ---
        button_layout = QHBoxLayout()
        self.clear_filters_btn = QPushButton("Limpiar Filtros")
        self.apply_filters_btn = QPushButton("Aplicar Filtros")
        button_layout.addWidget(self.clear_filters_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.apply_filters_btn)
        layout.addLayout(button_layout)

        # Conectar los botones a las funciones del app principal
        self.clear_filters_btn.clicked.connect(self.on_clear_filters)
        self.apply_filters_btn.clicked.connect(self.on_apply_filters)

    def on_clear_filters(self):
        if hasattr(self.parent(), 'clear_filters'):
            self.parent().clear_filters()

    def on_apply_filters(self):
        if hasattr(self.parent(), 'apply_filters'):
            self.parent().apply_filters()

class CSVPlotterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setStatusBar(QStatusBar(self))  # Asegura que la barra de estado siempre esté visible
        self.setWindowTitle("Umbrella Visor Classic")
        self.setGeometry(0, 0, 1024, 768)
        
        self.emitter_reference = self.load_emitter_reference()
        self.df = None
        self.filtered_df = None
        self.emitter_col = None
        self.is_3d_view = False
        self.opengl_available = True
        self.emitter_color_map = {}
        self.legend_window = None
        self.legend_text = None
        self.status_update_timer = None
        self.last_status_base = ""
        self.histogram_window = None
        
        self.init_ui()
        self.showMaximized()
        

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Configurar barra de menú
        menubar = self.menuBar()

        # Menú Archivo
        file_menu = menubar.addMenu("Archivo")
        action_cargar = file_menu.addAction("Cargar CSV")
        action_cargar.setShortcut(QKeySequence("Ctrl+O"))
        action_cargar.triggered.connect(self.load_csv)

        action_guardar = file_menu.addAction("Guardar Imagen")
        action_guardar.setShortcut(QKeySequence("Ctrl+S"))
        action_guardar.triggered.connect(self.save_image)

        action_salir = file_menu.addAction("Salir")
        action_salir.setShortcut(QKeySequence("Ctrl+Q"))
        action_salir.triggered.connect(self.close)

        # Nueva opción para exportar datos filtrados
        action_exportar = file_menu.addAction("Exportar Filtrado")
        action_exportar.setShortcut(QKeySequence("Ctrl+E"))
        action_exportar.triggered.connect(self.export_filtered_data)

        # Menú Vista
        view_menu = menubar.addMenu("Vista")
        self.toggle_3d_action = view_menu.addAction("Modo 3D")
        self.toggle_3d_action.setShortcut(QKeySequence("F6"))
        self.toggle_3d_action.triggered.connect(self.toggle_3d_view)

        action_reset = view_menu.addAction("Resetear Vista")
        action_reset.setShortcut(QKeySequence("F5"))
        action_reset.triggered.connect(self.auto_range_action)

        # Nueva opción para mostrar/ocultar la leyenda
        action_toggle_legend = view_menu.addAction("Mostrar Leyenda")
        action_toggle_legend.setShortcut(QKeySequence("F11"))
        action_toggle_legend.triggered.connect(self.toggle_legend)

        # Nueva opción para "Unir pulsos"
        action_merge_pulses = view_menu.addAction("Unir pulsos")
        action_merge_pulses.triggered.connect(self.show_merge_pulses_dialog)

        # --- NUEVO: Opción de menú para histogramas ---
        action_histogram = view_menu.addAction("Histogramas")
        action_histogram.setShortcut(QKeySequence("F7"))
        action_histogram.triggered.connect(self.show_histogram_window)
        # --- FIN NUEVO ---

        # Barra de herramientas para los ejes
        toolbar = QToolBar("Ejes")
        toolbar.setMovable(True)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        logo_label = QLabel()
        logo_pixmap = QPixmap("logo.png")
        logo_label.setPixmap(logo_pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        logo_label.setContentsMargins(0, 0, 10, 0)
        toolbar.addWidget(logo_label)

        # Comboboxes para los ejes en la barra de herramientas
        # Etiquetas de ejes con color igual al eje en el visor 2D

        x_label = QLabel("Eje X:")
        x_label.setContentsMargins(0, 0, 10, 0)
        x_label.setStyleSheet(f"color: {AXIS_COLORS.x}; font-weight: bold;")
        toolbar.addWidget(x_label)
        self.x_combo = QComboBox()
        self.x_combo.setMinimumWidth(150)
        toolbar.addWidget(self.x_combo)

        y_label = QLabel("Eje Y:")
        y_label.setContentsMargins(0, 0, 10, 0)
        y_label.setStyleSheet(f"color: {AXIS_COLORS.y}; font-weight: bold;")
        toolbar.addWidget(y_label)
        self.y_combo = QComboBox()
        self.y_combo.setMinimumWidth(150)
        toolbar.addWidget(self.y_combo)

        # Crear pero NO añadir el label y combobox del eje Z todavía
        self.z_label = QLabel("Eje Z:")
        self.z_label.setContentsMargins(0, 0, 10, 0)
        self.z_label.setStyleSheet(f"color: {AXIS_COLORS.z}; font-weight: bold;")  # Azul eje Z
        self.z_combo = QComboBox()
        self.z_combo.setMinimumWidth(150)
        # No añadir aquí: toolbar.addWidget(self.z_label), toolbar.addWidget(self.z_combo)

        # Área dividida para gráfico y tabla
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Contenedor para los gráficos
        self.plot_container = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_container)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)

        # Crear gráfico 2D
        self.plot_2d = pg.PlotWidget(axisItems={'bottom': NoSciAxis(orientation='bottom')})
        self.plot_2d.highlighted_point = None
        self.plot_2d.highlight_point = self.highlight_point_2d
        self.plot_2d.setLabel('bottom', 'X', color=AXIS_COLORS.x)
        self.plot_2d.setLabel('left', 'Y', color=AXIS_COLORS.y)
        self.plot_2d.showGrid(x=True, y=True, alpha=0.3)
        self.plot_2d.getAxis('bottom').enableAutoSIPrefix(False)

        # Colorear los ejes X e Y
        self.plot_2d.getAxis('bottom').setPen(pg.mkPen(AXIS_COLORS.x, width=2))
        self.plot_2d.getAxis('left').setPen(pg.mkPen(AXIS_COLORS.y, width=2))

        # Intentar crear gráfico 3D
        try:
            self.plot_3d = GLPlotWidget(emitter_color_map=self.emitter_color_map)
        except Exception as e:
            print(f"Error al inicializar GLPlotWidget: {e}")
            self.opengl_available = False
            self.plot_3d = QLabel("Visualización 3D no disponible (Error OpenGL)")
            self.plot_3d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.plot_3d.setStyleSheet("color: red; font-size: 16px;")
            self.toggle_3d_action.setEnabled(False)
            self.z_combo.setEnabled(False)

        self.plot_layout.addWidget(self.plot_2d)
        self.plot_3d.hide()

        # Widget para la tabla
        self.table_container = QWidget()
        table_container_layout = QVBoxLayout(self.table_container)

        # Botones de filtro
        filter_buttons_widget = QWidget()
        filter_buttons_layout = QHBoxLayout(filter_buttons_widget)
        filter_buttons_layout.setContentsMargins(0, 0, 0, 5)
        filter_buttons_layout.addStretch()  # Alinea los botones a la derecha
        self.clear_filters_btn = QPushButton("Limpiar Filtros")
        self.clear_filters_btn.clicked.connect(self.clear_filters)
        self.apply_filters_btn = QPushButton("Aplicar Filtros")
        self.apply_filters_btn.clicked.connect(self.apply_filters)
        filter_buttons_layout.addWidget(self.clear_filters_btn)
        filter_buttons_layout.addWidget(self.apply_filters_btn)
        table_container_layout.addWidget(filter_buttons_widget)

        self.table_widget = QTableWidget()
        self.table_widget.setSortingEnabled(False)
        self.table_widget.itemSelectionChanged.connect(self.on_table_selection_changed)
        table_container_layout.addWidget(self.table_widget)

        self.central_splitter.addWidget(self.plot_container)
        self.central_splitter.addWidget(self.table_container)
        self.central_splitter.setSizes([700, 300])

        # --- NUEVO: Sección de leyenda lateral ---
        self.legend_panel = QWidget()
        legend_layout = QVBoxLayout(self.legend_panel)
        legend_layout.setContentsMargins(8, 8, 8, 8)
        legend_layout.setSpacing(4)
        legend_title = QLabel("Leyenda de emisores")
        legend_title.setStyleSheet("font-weight: bold; font-size: 15px; color: #fff; margin-bottom: 8px;")
        legend_layout.addWidget(legend_title)
        self.legend_text = QTextEdit()
        self.legend_text.setReadOnly(True)
        self.legend_text.setStyleSheet("background-color: #232323; color: #fff; font-size: 13px;")
        legend_layout.addWidget(self.legend_text)
        self.legend_panel.setMinimumWidth(260)
        self.legend_panel.setMaximumWidth(350)
        self.legend_panel.hide()  # Oculta por defecto

        # Añadir widgets al splitter principal
        self.main_splitter.addWidget(self.central_splitter)
        self.main_splitter.addWidget(self.legend_panel)
        self.main_splitter.setSizes([1000, 300])

        main_layout.addWidget(self.main_splitter)

        # Configurar estilos
        self.configure_styles()

        self.x_combo.currentTextChanged.connect(self.plot_data)
        self.y_combo.currentTextChanged.connect(self.plot_data)
        self.z_combo.currentTextChanged.connect(self.plot_data)
        # Conectar para actualizar los nombres de los ejes 3D
        self.x_combo.currentTextChanged.connect(self.update_3d_axis_labels)
        self.y_combo.currentTextChanged.connect(self.update_3d_axis_labels)
        self.z_combo.currentTextChanged.connect(self.update_3d_axis_labels)

    def update_3d_axis_labels(self):
        if self.is_3d_view and self.opengl_available:
            self.plot_3d.add_infinite_axes(
                x_label=self.x_combo.currentText(),
                y_label=self.y_combo.currentText(),
                z_label=self.z_combo.currentText()
            )

    def configure_styles(self):
        # Estilo para comboboxes
        combo_style = """
            QComboBox {
                padding: 5px;
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
            }
        """
        self.x_combo.setStyleSheet(combo_style)
        self.y_combo.setStyleSheet(combo_style)
        self.z_combo.setStyleSheet(combo_style)
        
        # Estilo para botones
        button_style = """
            QPushButton {
                padding: 5px 10px;
                font-size: 12px;
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """
        self.apply_filters_btn.setStyleSheet(button_style)
        self.clear_filters_btn.setStyleSheet(button_style)
        
        # Estilo para tabla
        self.table_widget.setStyleSheet("""
            QTableWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                gridline-color: #3e3e3e;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #1e1e1e;
                color: #ffffff;
                padding: 6px;
                border: 1px solid #3e3e3e;
                font-weight: bold;
            }
            QTableWidget::item {
                border: 1px solid #3e3e3e;
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #4a4a4a;
                color: #ffffff;
            }
        """)
        self.table_widget.horizontalHeader().setSectionsClickable(True)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def highlight_point_2d(self, index):
        if index is None or self.filtered_df is None:
            if hasattr(self.plot_2d, 'highlighted_point') and self.plot_2d.highlighted_point:
                self.plot_2d.removeItem(self.plot_2d.highlighted_point)
                self.plot_2d.highlighted_point = None
            return
            
        try:
            x_col = self.x_combo.currentText()
            y_col = self.y_combo.currentText()
            
            if x_col not in self.filtered_df.columns or y_col not in self.filtered_df.columns:
                return
                
            x = float(self.filtered_df.iloc[index][x_col])
            y = float(self.filtered_df.iloc[index][y_col])
            
            if hasattr(self.plot_2d, 'highlighted_point') and self.plot_2d.highlighted_point:
                self.plot_2d.removeItem(self.plot_2d.highlighted_point)
                
            self.plot_2d.highlighted_point = pg.ScatterPlotItem(
                x=[x],
                y=[y],
                size=12,
                pen=pg.mkPen('r', width=2),
                brush=pg.mkBrush((0, 0, 0, 0)),
                symbol='o'
            )
            self.plot_2d.addItem(self.plot_2d.highlighted_point)
            
            view_box = self.plot_2d.getViewBox()
            current_range = view_box.viewRange()
            x_range = current_range[0][1] - current_range[0][0]
            y_range = current_range[1][1] - current_range[1][0]
            view_box.setRange(
                xRange=(x - x_range / 2, x + x_range / 2),
                yRange=(y - y_range / 2, y + y_range / 2),
                padding=0
            )
            
        except Exception as e:            
            print(f"Error highlighting 2D point: {e}")
            if hasattr(self.plot_2d, 'highlighted_point') and self.plot_2d.highlighted_point:
                self.plot_2d.removeItem(self.plot_2d.highlighted_point)
                self.plot_2d.highlighted_point = None

    def toggle_3d_view(self):
        print("\nDebug: Iniciando toggle_3d_view")
        print(f"Debug: Estado actual is_3d_view = {self.is_3d_view}")
        
        # Verificar disponibilidad de OpenGL
        if not self.opengl_available and not self.is_3d_view:
            QMessageBox.warning(self, "Error", "OpenGL no está disponible. No se puede activar el modo 3D.")
            return
        
        # Cambiar el estado antes de actualizar la UI
        self.is_3d_view = not self.is_3d_view
        
        # Mostrar/ocultar combobox y etiqueta del eje Z correctamente
        if self.is_3d_view:
            # Añadir al toolbar si no están
            if self.z_label.parent() is None:
                self.findChild(QToolBar).addWidget(self.z_label)
            if self.z_combo.parent() is None:
                self.findChild(QToolBar).addWidget(self.z_combo)
            self.z_label.show()
            self.z_combo.show()
            self.plot_layout.removeWidget(self.plot_2d)
            self.plot_2d.hide()
            self.plot_layout.removeWidget(self.plot_2d)
            
            # Luego configurar y mostrar el gráfico 3D
            self.plot_layout.addWidget(self.plot_3d)
            self.plot_3d.show()
            self.toggle_3d_action.setText("Modo 2D")
            
            # Actualizar nombres de ejes 3D
            self.plot_3d.add_infinite_axes(
                x_label=self.x_combo.currentText(),
                y_label=self.y_combo.currentText(),
                z_label=self.z_combo.currentText()
            )
            
            # Actualizar el gráfico si hay datos
            if (self.filtered_df is not None and 
                all(col and col in self.filtered_df.columns 
                    for col in [self.x_combo.currentText(), 
                              self.y_combo.currentText(), 
                              self.z_combo.currentText()])):
                self.plot_3d.plot_data(
                    df=self.filtered_df,
                    x_col=self.x_combo.currentText(),
                    y_col=self.y_combo.currentText(),
                    z_col=self.z_combo.currentText(),
                    emitter_col=self.emitter_col
                )
        else:
            # Quitar del toolbar si están
            if self.z_label.parent() is not None:
                self.findChild(QToolBar).removeWidget(self.z_label)
            if self.z_combo.parent() is not None:
                self.findChild(QToolBar).removeWidget(self.z_combo)
            self.plot_layout.removeWidget(self.plot_3d)
            self.plot_3d.hide()
            self.plot_layout.removeWidget(self.plot_3d)
            
            # Luego mostrar el gráfico 2D
            self.plot_layout.addWidget(self.plot_2d)
            self.plot_2d.show()
            self.toggle_3d_action.setText("Modo 3D")
            
            # Actualizar el gráfico 2D si hay datos
            if self.filtered_df is not None:
                self.plot_data()
        
        print(f"Debug: Finalizado toggle_3d_view. Widget Z visible: {self.z_widget.isVisible()}")


    def reset_3d_view(self):
        if self.is_3d_view and self.opengl_available:
            self.plot_3d.clear()
            self.plot_3d.add_infinite_axes()
            if self.filtered_df is not None:
                self.plot_3d.plot_data(
                    df=self.filtered_df,
                    x_col=self.x_combo.currentText(),
                    y_col=self.y_combo.currentText(),
                    z_col=self.z_combo.currentText(),
                    emitter_col=self.emitter_col
                )
            self.plot_3d.auto_range()
            self.clear_highlights()

    def toggle_legend(self):
        """Mostrar u ocultar la ventana flotante de la leyenda."""
        if not self.legend_window:
            self.legend_window = QDockWidget("Leyenda", self)
            self.legend_window.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
            self.legend_window.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
            self.legend_window.setFloating(True)
            self.legend_window.resize(300, 350)
            self.legend_text = QTextEdit()
            self.legend_text.setReadOnly(True)
            self.legend_text.setStyleSheet("background-color: #232323; color: #fff; font-size: 13px;")
            self.legend_window.setWidget(self.legend_text)
            self.legend_window.setWindowFlags(self.legend_window.windowFlags() | Qt.WindowType.WindowCloseButtonHint)
            self.legend_window.closeEvent = self.close_legend_window

        if self.legend_window.isVisible():
            self.legend_window.hide()
        else:
            self.update_legend(self.filtered_df)
            self.legend_window.show()

    # El método close_legend_window ya no es necesario

    def update_legend(self, data):
        """Actualizar la leyenda con los emisores visibles en los datos proporcionados."""
        print("\nDebug update_legend:")
        print(f"legend_text exists: {self.legend_text is not None}")
        print(f"data exists: {data is not None}")
        print(f"data empty: {data.empty if data is not None else True}")
        print(f"emitter_col: {self.emitter_col}")
        print(f"columns in data: {data.columns.tolist() if data is not None else []}")
        
        if not self.legend_text or data is None or data.empty or self.emitter_col not in data.columns:
            print("Debug: No se puede actualizar la leyenda - condiciones no cumplidas")
            if self.legend_text:
                self.legend_text.clear()
            return

        emitters = sorted(data[self.emitter_col].unique(), key=lambda x: (x == -1, x))
        print(f"Debug: Emisores encontrados: {emitters}")
        legend_content = ""

        for emitter in emitters:
            color = self.get_emitter_color(emitter)
            label = self.get_emitter_label(emitter)
            color_hex = pg.mkColor(color).name()
            legend_content += f'<span style="color:{color_hex};">⬤</span> {label}<br>'
            print(f"Debug: Añadido emisor {emitter} con etiqueta {label} y color {color_hex}")

        print(f"Debug: Contenido final de la leyenda:\n{legend_content}")
        self.legend_text.setHtml(legend_content)

    def get_emitter_label(self, emitter):
        """Devuelve el nombre descriptivo del emisor según reglas de ruido."""
        # Si viene vacío, None o no convertible a int, tratar como desconocido
        if emitter is None or (isinstance(emitter, str) and emitter.strip() == ""):
            return "Desconocido"
        if isinstance(emitter, str):
            try:
                emitter = int(emitter)
            except Exception:
                return "Desconocido"

        if emitter == -1:
            return "Ruido espurio"
        elif emitter < 0:
            return "Ruido conocido"
        elif emitter in self.emitter_reference:
            return f"Emisor {emitter}: {self.emitter_reference[emitter]}"
        return f"Emisor {emitter}"

    def load_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Abrir archivo CSV", "", "CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return

        # Contar filas totales del archivo
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            total_rows = sum(1 for _ in f)

        # Si el archivo tiene más de MAX_CSV_ROWS_TO_LOAD filas, cargar solo MAX_CSV_ROWS_TO_LOAD y avisar
        if total_rows > MAX_CSV_ROWS_TO_LOAD:
            sample_rows = MAX_CSV_ROWS_TO_LOAD
            df = pd.read_csv(file_path, nrows=sample_rows, dtype=str, keep_default_na=False)
            self.df = df
            self.filtered_df = self.df.copy()
            # Buscar columna de emisor (igual que en finish_loading)
            self.emitter_col = None
            frec_cols = [col for col in self.df.columns if "emitter" in col.lower()]
            if frec_cols:
                self.emitter_col = frec_cols[0]
            self.update_combo_values()
            self.display_data_table()
            self.plot_data()
            self.statusBar().showMessage(
                f"Se han cargado solo {MAX_CSV_ROWS_TO_LOAD:,} filas. El archivo tiene más de {MAX_CSV_ROWS_TO_LOAD:,} filas. Puede cargar más desde el diálogo.", 10000
            )
            # Mostrar diálogo de opciones después de cargar y graficar
            dlg = CSVLoadOptionsDialog(self, total_rows, sample_rows)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                if dlg.selected_option == 'sample':
                    # No hacer nada, ya está cargada la muestra
                    pass
                elif dlg.selected_option == 'all':
                    self._reload_csv_rows(file_path, total_rows)
                elif dlg.selected_option == 'custom':
                    self._reload_csv_rows(file_path, dlg.selected_rows)
                elif dlg.selected_option == 'extra':
                    self._reload_csv_rows(file_path, dlg.selected_rows)
                # Si cancela, se queda con la muestra
            return

        file_name = os.path.basename(file_path)
        self.progress = QProgressDialog(
            f"Preparando carga de {file_name}...",
            "Cancelar", 0, 200, self
        )
        self.progress.setWindowTitle(f"Cargando {file_name}")
        self.progress.setWindowModality(Qt.WindowModality.NonModal)  # <-- Siempre NonModal
        self.progress.setMinimumDuration(0)
        self.progress.setValue(0)
        self.progress.setAutoClose(False)
        self.progress.canceled.connect(self.cancel_loading)
        self.progress.show()

        # 1. Mostrar diálogo de carga
        self.progress.setLabelText("Preparando carga de datos...")
        self.progress.setValue(10)
        QApplication.processEvents()

        # 2. Lanzar hilo para cargar el archivo completo usando CSVLoaderThread
        self.loader_thread = CSVLoaderThread(file_path)
        self.loader_thread.progress_updated.connect(self.update_progress)
        self.loader_thread.loading_finished.connect(lambda df: self.finish_loading(df, file_path))
        self.loader_thread.error_occurred.connect(self.handle_loading_error)
        self.loader_thread.start()

    def cancel_loading(self):
        if hasattr(self, 'loader_thread'):
            self.loader_thread.cancel()
        if hasattr(self, 'progress') and self.progress.isVisible():
            self.progress.close()

    def update_progress(self, value, message):
        if hasattr(self, 'progress'):
            self.progress.setValue(value)
            self.progress.setLabelText(message)
        QApplication.processEvents()

    def finish_loading(self, df, file_path):
        try:
            # Procesamiento rápido en el hilo principal
            self.df = df
            self.filtered_df = self.df.copy()
            
            # Buscar columna de emisor
            self.emitter_col = None
            # Primero buscar una columna que se llame exactamente "Emitter"
            if 'Emitter' in self.df.columns.values:
                self.emitter_col = 'Emitter'
            elif 'EMITTER' in self.df.columns.values:
                self.emitter_col = 'EMITTER'
            else:
                # Si no, buscar cualquier columna que contenga "emitter" en cualquier caso
                emitter_cols = [col for col in self.df.columns if "emitter" in col.lower()]
                if emitter_cols:
                    self.emitter_col = emitter_cols[0]
            
            print(f"\nDebug finish_loading: Buscando columna de emisor")
            print(f"Columnas disponibles: {self.df.columns.tolist()}")
            print(f"Columna de emisor seleccionada: {self.emitter_col}")
            
            # Mensaje especial si hay más de 100000 filas
            num_registros = len(self.df)
            if num_registros > 100000:
                msg = f"Actualizando interfaz gráfica...Por favor, espere. Número de registros elevado: {num_registros:,}"
            else:
                msg = "Actualizando interfaz gráfica..."
            self.update_progress(190, msg)
            self.update_combo_values()
            self.display_data_table()
            
            base_name = os.path.basename(file_path)
            self.last_status_base = f"Datos de entrada: {base_name} | Número de pulsos: {num_registros:,}"
            self.update_status_bar_with_resources()
            self.start_status_update_timer()

            self.plot_data()
            
            # Si está en modo 3D y OpenGL disponible, ajustar vista y ejes
            if self.is_3d_view and self.opengl_available:
                self.plot_3d.auto_range()
                self.plot_3d.add_infinite_axes()
            
            self.update_progress(200, f"Carga completada!\nFilas totales: {len(self.df):,}")
            QTimer.singleShot(1000, lambda: self.progress.close() if hasattr(self, 'progress') and self.progress.isVisible() else None)
        except Exception as e:
            self.handle_loading_error(str(e))

    def update_status_bar_with_resources(self):
        status = self.last_status_base
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            ram_mb = process.memory_info().rss / (1024 * 1024)
            cpu_percent = psutil.cpu_percent(interval=0.1)
            status += f" | RAM: {ram_mb:.1f} MB | CPU: {cpu_percent:.1f}%"
        except Exception:
            pass
        self.statusBar().showMessage(status)

    def start_status_update_timer(self):
        if self.status_update_timer is not None:
            self.status_update_timer.stop()
        self.status_update_timer = QTimer(self)
        self.status_update_timer.timeout.connect(self.update_status_bar_with_resources)
        self.status_update_timer.start(10000)  # 10 segundos

    def handle_loading_error(self, error_msg):
        if hasattr(self, 'progress') and self.progress.isVisible():
            self.progress.close()
        QMessageBox.critical(self, "Error", f"No se pudo cargar el archivo:\n{error_msg}")
    
    def update_combo_values(self):
        self.x_combo.clear()
        self.y_combo.clear()
        self.z_combo.clear()
        
        columns = self.df.columns
        self.x_combo.addItems(columns)
        self.y_combo.addItems(columns)
        self.z_combo.addItems(columns)

        # Seleccionar automáticamente columnas comunes
        toa_column = next((col for col in columns if 'TOA' in col.upper()), None)
        pri_column = next((col for col in columns if 'PRI' in col.upper()), None)

        # Buscar columna de emisor de forma consistente con finish_loading
        if 'Emitter' in columns:
            self.emitter_col = 'Emitter'
            emitter_column = 'Emitter'
        elif 'EMITTER' in columns:
            self.emitter_col = 'EMITTER'
            emitter_column = 'EMITTER'
        else:
            emitter_cols = [col for col in columns if "emitter" in col.lower()]
            if emitter_cols:
                self.emitter_col = emitter_cols[0]
                emitter_column = emitter_cols[0]
            else:
                emitter_column = None

        print(f"\nDebug update_combo_values:")
        print(f"Columnas disponibles: {columns.tolist()}")
        print(f"Columna de emisor seleccionada: {self.emitter_col}")

        if toa_column:
            self.x_combo.setCurrentText(toa_column)
        if pri_column:
            self.y_combo.setCurrentText(pri_column)
        if emitter_column:
            self.z_combo.setCurrentText(emitter_column)

    def display_data_table(self):
        if self.filtered_df is None:
            return
        
        self.table_widget.itemSelectionChanged.disconnect()
        
        self.table_widget.setRowCount(self.filtered_df.shape[0] + 1)  # +1 para la fila de filtros
        self.table_widget.setColumnCount(self.filtered_df.shape[1])
        self.table_widget.setHorizontalHeaderLabels(self.filtered_df.columns)
        
        for col in range(self.filtered_df.shape[1]):
            if not self.table_widget.cellWidget(0, col):
                filter_edit = QLineEdit()
                filter_edit.setPlaceholderText("Filtrar...")
                # Cambiar el color de fondo y texto del tooltip para modo oscuro
                filter_edit.setToolTip(
                    "<span style='color:#fff; background-color:#232323;'>"
                    "Ayuda para Filtros:<br>"
                    "- '&gt;' o '&lt;': Mayor o menor.<br>"
                    "- '=': Igual a.<br>"
                    "- 'min:max': Intervalo (ej. 10:20).<br>"
                    "- ':max': Menor o igual a max.<br>"
                    "- 'min:': Mayor o igual a min."
                    "</span>"
                )
                self.table_widget.setCellWidget(0, col, filter_edit)

        for i, (index, row) in enumerate(self.filtered_df.iterrows()):
            for j, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setData(Qt.ItemDataRole.UserRole, index)

                if i % 2 == 0:
                    item.setBackground(QColor('#333333'))
                else:
                    item.setBackground(QColor('#2b2b2b'))

                item.setForeground(QBrush(QColor('#ffffff')))
                self.table_widget.setItem(i + 1, j, item)

        self.table_widget.itemSelectionChanged.connect(self.on_table_selection_changed)
        self.table_widget.setSortingEnabled(True)
        
    def clear_filters(self):
        if self.df is None:
            return
        
        for col_idx in range(self.table_widget.columnCount()):
            filter_edit = self.table_widget.cellWidget(0, col_idx)
            if filter_edit:
                filter_edit.clear()
        
        self.filtered_df = self.df.copy()
        self.display_data_table()
        self.plot_data()

    def auto_range_action(self):
        """Realiza auto range en el gráfico activo (2D o 3D), equivalente a pulsar la 'A' pequeña."""
        if self.is_3d_view and self.opengl_available:
            if hasattr(self.plot_3d, 'auto_range'):
                self.plot_3d.auto_range()
        else:
            vb = self.plot_2d.getViewBox()
            if hasattr(vb, 'autoRange'):
                vb.autoRange()

    def on_table_selection_changed(self):
        try:
            selected_items = self.table_widget.selectedItems()
            if not selected_items:
                self.clear_highlights()
                return

            selected_row = selected_items[0].row() - 1
            
            if selected_row < 0 or selected_row >= len(self.filtered_df):
                self.clear_highlights()
                return
            
            if self.is_3d_view:
                self.plot_3d.highlight_point(selected_row)
            else:
                if hasattr(self.plot_2d, 'highlight_point'):
                    self.plot_2d.highlight_point(selected_row)
                    
            self.table_widget.scrollToItem(selected_items[0], QTableWidget.ScrollHint.PositionAtCenter)
            
        except Exception as e:
            print(f"Error in table selection: {str(e)}")
            self.clear_highlights()

    def clear_highlights(self):
        if self.is_3d_view:
            if hasattr(self.plot_3d, 'highlighted_point') and self.plot_3d.highlighted_point:
                for item in self.plot_3d.highlighted_point:
                    self.plot_3d.removeItem(item)
                self.plot_3d.highlighted_point = None
        else:
            if hasattr(self.plot_2d, 'highlighted_point') and self.plot_2d.highlighted_point:
                self.plot_2d.removeItem(self.plot_2d.highlighted_point)
                self.plot_2d.highlighted_point = None

    def plot_data(self):
        """Actualizar la visualización según el modo actual."""
        if not self.opengl_available and self.is_3d_view:
            QMessageBox.warning(self, "OpenGL no disponible", 
                "No se puede mostrar la vista 3D porque OpenGL no está disponible.")
            return

        if self.filtered_df is None or self.filtered_df.empty:
            # Limpiar gráficos si no hay datos
            if self.is_3d_view:
                self.plot_3d.clear()
            else:
                self.plot_2d.clear()
            return

        try:
            if self.is_3d_view:
                if (self.x_combo.currentText() and 
                    self.y_combo.currentText() and 
                    self.z_combo.currentText()):
                    
                    if (self.x_combo.currentText() not in self.filtered_df.columns or
                        self.y_combo.currentText() not in self.filtered_df.columns or
                        self.z_combo.currentText() not in self.filtered_df.columns):
                        print("Error: Columnas seleccionadas no encontradas en los datos")
                        return
                    
                    try:
                        # Crear una copia del DataFrame para trabajar
                        plot_df = self.filtered_df.copy()
                        
                        # Convertir las columnas a numéricas de forma segura
                        plot_df[self.x_combo.currentText()] = pd.to_numeric(plot_df[self.x_combo.currentText()], errors='coerce')
                        plot_df[self.y_combo.currentText()] = pd.to_numeric(plot_df[self.y_combo.currentText()], errors='coerce')
                        plot_df[self.z_combo.currentText()] = pd.to_numeric(plot_df[self.z_combo.currentText()], errors='coerce')
                        
                        # Filtrar filas con valores no numéricos
                        valid_mask = ~(
                            plot_df[self.x_combo.currentText()].isna() | 
                            plot_df[self.y_combo.currentText()].isna() | 
                            plot_df[self.z_combo.currentText()].isna()
                        )
                        
                        if not valid_mask.any():
                            print("Error: No hay datos válidos para graficar")
                            return
                        
                        # Aplicar la máscara a todo el DataFrame
                        plot_df = plot_df[valid_mask]
                        
                        # Limpiar el gráfico 3D
                        self.plot_3d.clear()
                        self.plot_3d.add_infinite_axes(
                            x_label=self.x_combo.currentText(),
                            y_label=self.y_combo.currentText(),
                            z_label=self.z_combo.currentText()
                        )
                        
                        # Si hay columna de emisor, pintar cada uno con su color
                        if self.emitter_col and self.emitter_col in plot_df.columns:
                            emitters = plot_df[self.emitter_col].unique()
                            for emitter in emitters:
                                mask = plot_df[self.emitter_col] == emitter
                                color = self.get_emitter_color(emitter, for_3d=True)  # Obtener color en formato RGBA
                                emitter_data = plot_df[mask]
                                
                                scatter = gl.GLScatterPlotItem(
                                    pos=np.column_stack((
                                        emitter_data[self.x_combo.currentText()],
                                        emitter_data[self.y_combo.currentText()],
                                        emitter_data[self.z_combo.currentText()]
                                    )),
                                    color=color,
                                    size=5,
                                    pxMode=True
                                )
                                self.plot_3d.addItem(scatter)
                        else:
                            # Si no hay emisor, todos del mismo color (blanco)
                            scatter = gl.GLScatterPlotItem(
                                pos=np.column_stack((
                                    plot_df[self.x_combo.currentText()],
                                    plot_df[self.y_combo.currentText()],
                                    plot_df[self.z_combo.currentText()]
                                )),
                                color=(1.0, 1.0, 1.0, 1.0),
                                size=5,
                                pxMode=True
                            )
                            self.plot_3d.addItem(scatter)
                        
                        self.plot_3d.auto_range()
                        
                    except Exception as e:
                        print(f"Error al convertir o graficar datos: {e}")
                        import traceback
                        traceback.print_exc()
                        return
            else:
                if self.x_combo.currentText() and self.y_combo.currentText():
                    if (self.x_combo.currentText() not in self.filtered_df.columns or
                        self.y_combo.currentText() not in self.filtered_df.columns):
                        print("Error: Columnas seleccionadas no encontradas en los datos")
                        return
                        
                    x_col = pd.to_numeric(self.filtered_df[self.x_combo.currentText()], errors='coerce')
                    y_col = pd.to_numeric(self.filtered_df[self.y_combo.currentText()], errors='coerce')
                    
                    # Filtrar datos no numéricos
                    valid_mask = ~(x_col.isna() | y_col.isna())
                    x_col = x_col[valid_mask]
                    y_col = y_col[valid_mask]
                    
                    self.plot_2d.clear()
                    if self.emitter_col and self.emitter_col in self.filtered_df.columns:
                        # Si hay columna de emisor, pintar cada uno con su color
                        emitters = self.filtered_df[valid_mask][self.emitter_col].unique()
                        for emitter in emitters:
                            mask = self.filtered_df[valid_mask][self.emitter_col] == emitter
                            color = self.get_emitter_color(emitter)
                            scatter = pg.ScatterPlotItem(
                                x=x_col[mask],
                                y=y_col[mask],
                                pen=None,
                                brush=color,
                                symbol='o',
                                size=5
                            )
                            self.plot_2d.addItem(scatter)
                    else:
                        # Si no hay emisor, todos del mismo color
                        scatter = pg.ScatterPlotItem(
                            x=x_col,
                            y=y_col,
                            pen=None,
                            brush='w',
                            symbol='o',
                            size=5
                        )
                        self.plot_2d.addItem(scatter)
                    
                    self.plot_2d.getViewBox().autoRange()
                    
        except Exception as e:
            print(f"Error al graficar los datos: {e}")
            QMessageBox.warning(self, "Error", f"No se pudo graficar:\n{str(e)}")
        
    def get_emitter_color(self, emitter):
        # Manejar valores vacíos o None
        if emitter is None or (isinstance(emitter, str) and emitter.strip() == ""):
            return NOISE_COLOR
        if isinstance(emitter, str):
            try:
                emitter = int(emitter)
            except Exception:
                return NOISE_COLOR

        if emitter < 0:
            return NOISE_COLOR

        if emitter not in self.emitter_color_map:
            assigned = len(self.emitter_color_map)
            color = VIBRANT_COLORS[assigned % len(VIBRANT_COLORS)]
            self.emitter_color_map[emitter] = color
        return self.emitter_color_map[emitter]
    
    def apply_filters(self):
        if self.df is None:
            return
            
        mask = pd.Series([True] * len(self.df), index=self.df.index)
        
        for col_idx in range(self.table_widget.columnCount()):
            col_name = self.table_widget.horizontalHeaderItem(col_idx).text()
            filter_edit = self.table_widget.cellWidget(0, col_idx)
            filter_text = filter_edit.text().strip()
            
            if filter_text and col_name in self.df.columns:
                try:
                    numeric_series = pd.to_numeric(self.df[col_name], errors='coerce')
                    col_mask = self.process_filter_expression(numeric_series, filter_text)
                    mask = mask & col_mask
                except Exception as e:
                    self.statusBar().showMessage(f"Error en filtro {col_name}: {str(e)}", 3000)
                    return
        
        self.filtered_df = self.df[mask].copy()
        self.display_data_table()
        self.plot_data()
        # --- NUEVO: Actualizar leyenda si está visible ---
        if self.legend_window and self.legend_window.isVisible():
            self.update_legend(self.filtered_df)

    def process_filter_expression(self, series, expression):
        if ':' in expression:
            try:
                min_val, max_val = expression.split(':')
                min_val = float(min_val) if min_val else -np.inf
                max_val = float(max_val) if max_val else np.inf
                return (series >= min_val) & (series <= max_val)
            except ValueError:
                raise ValueError("Formato de intervalo inválido. Use 'min:max'.")

        parts = expression.split()
        if len(parts) == 1:
            part = parts[0]
            if part.startswith(('>', '<', '=')):
                if part.startswith('>'):
                    value = float(part[1:])
                    return series > value
                elif part.startswith('<'):
                    value = float(part[1:])
                    return series < value
                elif part.startswith('='):
                    value = float(part[1:])
                    return series == value
            else:
                value = float(part)
                return series == value
        else:
            mask = pd.Series([True] * len(series), index=series.index)
            i = 0
            while i < len(parts):
                part = parts[i]
                if part in ['>', '<']:
                    if i + 1 >= len(parts):
                        raise ValueError("Expresión incompleta")
                    
                    value = float(parts[i+1])
                    if part == '>':
                        mask = mask & (series > value)
                    elif part == '<':
                        mask = mask & (series < value)
                    i += 2
                else:
                    raise ValueError(f"Operador no reconocido: {part}")
            return mask

    def save_image(self):
        if not self.is_3d_view and not hasattr(self.plot_2d, 'plotItem'):
            return
        if self.is_3d_view and not hasattr(self.plot_3d, 'opts'):
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar imagen", "", 
            "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)"
        )
        
        if file_path:
            try:
                if self.is_3d_view:
                    img = self.plot_3d.grabFramebuffer()
                    img.save(file_path)
                else:
                    exporter = pg.exporters.ImageExporter(self.plot_2d.plotItem)
                    exporter.export(file_path)
                
                self.statusBar().showMessage(f"Imagen guardada: {file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo guardar la imagen:\n{str(e)}")    
    
    def export_filtered_data(self):
        """Exportar los datos filtrados a un archivo CSV."""
        if self.filtered_df is None or self.filtered_df.empty:
            QMessageBox.warning(self, "Advertencia", "No hay datos filtrados para exportar.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar archivo CSV", "", "CSV Files (*.csv);;All Files (*)"
        )
        if file_path:
            try:
                self.filtered_df.to_csv(file_path, index=False)
                QMessageBox.information(self, "Éxito", f"Datos filtrados exportados a:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo exportar el archivo:\n{str(e)}")

    def load_emitter_reference(self):
        """Carga el archivo reference_emitters.txt y crea un diccionario con los códigos y nombres de los emisores."""
        emitter_ref = {}
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            ref_file = os.path.join(script_dir, 'reference_emitters.txt')
            
            if os.path.exists(ref_file):
                with open(ref_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and '=' in line:
                            name, code = line.rsplit('=', 1)
                            try:
                                code = int(code)
                                emitter_ref[code] = name.strip()
                            except ValueError:
                                print(f"Error parsing emitter code in line: {line}")
        except Exception as e:
            print(f"Error loading reference_emitters.txt: {e}")
        
        return emitter_ref

    def show_merge_pulses_dialog(self):
        """Mostrar ventana emergente para unir pulsos."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSpacerItem, QSizePolicy, QCheckBox, QLineEdit

        class MergePulsesDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Unir pulsos")
                self.setModal(True)
                self.setMinimumWidth(400)
                self.setMinimumHeight(220)
                layout = QVBoxLayout(self)

                # Checkbox "Por emisores"
                self.by_emitter_checkbox = QCheckBox("Por emisores")
                layout.addWidget(self.by_emitter_checkbox)

                # Campo editable para distancia entre TOAs conectados
                dist_layout = QHBoxLayout()
                dist_label = QLabel("Distancia entre TOAs conectados (ns):")
                self.dist_edit = QLineEdit()
                self.dist_edit.setText("100")
                self.dist_edit.setMaximumWidth(100)
                dist_layout.addWidget(dist_label)
                dist_layout.addWidget(self.dist_edit)
                dist_layout.addStretch()
                layout.addLayout(dist_layout)

                layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

                button_layout = QHBoxLayout()
                self.clear_btn = QPushButton("Limpiar")
                self.apply_btn = QPushButton("Aplicar")
                button_layout.addWidget(self.clear_btn)
                button_layout.addStretch()
                button_layout.addWidget(self.apply_btn)
                layout.addLayout(button_layout)

                self.clear_btn.clicked.connect(self.clear_options)
                self.apply_btn.clicked.connect(self.apply_options)

            def clear_options(self):
                self.by_emitter_checkbox.setChecked(False)
                self.dist_edit.setText("100")
                self.parent().remove_pulse_lines()

            def apply_options(self):
                self.parent().remove_pulse_lines()
                if self.by_emitter_checkbox.isChecked():
                    try:
                        dist_ns = float(self.dist_edit.text())
                    except Exception:
                        QMessageBox.warning(self, "Valor inválido", "La distancia debe ser un número.")
                        return
                    self.parent().draw_pulse_lines_by_emitter(dist_ns)

        dlg = MergePulsesDialog(self)
        dlg.exec()

    def remove_pulse_lines(self):
        # Elimina las líneas de unión de pulsos en ambos gráficos
        if not hasattr(self, "_pulse_lines"):
            self._pulse_lines = []
        # 2D
        if hasattr(self, "plot_2d") and hasattr(self.plot_2d, "removeItem"):
            for line in getattr(self, "_pulse_lines", []):
                if hasattr(self.plot_2d, "removeItem"):
                    self.plot_2d.removeItem(line)
        # 3D
        if hasattr(self, "plot_3d") and hasattr(self.plot_3d, "items"):
            for line in getattr(self, "_pulse_lines", []):
                if hasattr(self.plot_3d, "removeItem"):
                    self.plot_3d.removeItem(line)
        self._pulse_lines = []

    def draw_pulse_lines_by_emitter(self, max_dist_ns=100):
        # Dibuja líneas conectando los pulsos de cada emisor por TOA ascendente y distancia máxima
        if self.filtered_df is None or self.emitter_col is None or self.emitter_col not in self.filtered_df.columns:
            return
        if not hasattr(self, "_pulse_lines"):
            self._pulse_lines = []
        self.remove_pulse_lines()
        df = self.filtered_df
        emitter_col = self.emitter_col

        # Buscar columna TOA
        toa_col = next((col for col in df.columns if 'TOA' in col.upper()), None)
        if not toa_col:
            QMessageBox.warning(self, "Sin columna TOA", "No se encontró columna TOA para ordenar los pulsos.")
            return

        # Determinar modo (2D o 3D)
        if self.is_3d_view:
            x_col = self.x_combo.currentText()
            y_col = self.y_combo.currentText()
            z_col = self.z_combo.currentText()
            if not (x_col and y_col and z_col):
                return
            for emitter in df[emitter_col].unique():
                group = df[df[emitter_col] == emitter].copy()
                group = group.sort_values(by=toa_col)
                x = pd.to_numeric(group[x_col], errors='coerce').values
                y = pd.to_numeric(group[y_col], errors='coerce').values
                z = pd.to_numeric(group[z_col], errors='coerce').values
                toas = pd.to_numeric(group[toa_col], errors='coerce').values
                               # Conectar solo si la diferencia entre TOAs es menor o igual a max_dist_ns
                seg_points = []
                for i in range(1, len(toas)):
                    if np.isnan(toas[i-1]) or np.isnan(toas[i]):

                        continue
                    if abs(toas[i] - toas[i-1]) <= max_dist_ns:
                        seg_points.append([[x[i-1], y[i-1], z[i-1]], [x[i], y[i], z[i]]])
                # Dibujar cada segmento
                color = self.get_emitter_color(emitter)
                if isinstance(color, str):
                    qcolor = QColor(color)
                   
                    rgba = (qcolor.redF(), qcolor.greenF(), qcolor.blueF(), 0.35)
                else:
                    rgba = tuple(list(color[:3]) + [0.35])
                for seg in seg_points:
                    arr = np.array(seg)
                    line = gl.GLLinePlotItem(pos=arr, color=rgba, width=2, antialias=True, mode='lines')
                    self.plot_3d.addItem(line)
                    self._pulse_lines.append(line)
        else:
            x_col = self.x_combo.currentText()
            y_col = self.y_combo.currentText()
            if not (x_col and y_col):
                return
            for emitter in df[emitter_col].unique():
                group = df[df[emitter_col] == emitter].copy()
                group = group.sort_values(by=toa_col)
                x = pd.to_numeric(group[x_col], errors='coerce').values
                y = pd.to_numeric(group[y_col], errors='coerce').values
                toas = pd.to_numeric(group[toa_col], errors='coerce').values
                color = self.get_emitter_color(emitter)
                if isinstance(color, str):
                    qcolor = QColor(color)
                    pen = pg.mkPen(qcolor.lighter(170), width=2, style=Qt.PenStyle.DotLine)
                    pen.setColor(QColor(qcolor.red(), qcolor.green(), qcolor.blue(), 120))
                else:
                    r, g, b = [int(255*c) for c in color[:3]]
                    pen = pg.mkPen(QColor(r, g, b, 120), width=2, style=Qt.PenStyle.DotLine)
                # Dibujar solo segmentos cuya diferencia de TOA sea menor o igual a max_dist_ns
                for i in range(1, len(toas)):
                    if np.isnan(toas[i-1]) or np.isnan(toas[i]):
                        continue
                    if abs(toas[i] - toas[i-1]) <= max_dist_ns:
                        line = pg.PlotCurveItem([x[i-1], x[i]], [y[i-1], y[i]], pen=pen)
                        self.plot_2d.addItem(line)
                        self._pulse_lines.append(line)

    def show_histogram_window(self):
        if self.filtered_df is None or self.filtered_df.empty:
            QMessageBox.warning(self, "Sin datos", "No hay datos para mostrar el histograma.")
            return
        if self.histogram_window is not None:
            self.histogram_window.close()
        columns = list(self.filtered_df.columns)
        self.histogram_window = HistogramWindow(self, columns, self.filtered_df)
        self.histogram_window.setWindowModality(Qt.WindowModality.NonModal)
        self.histogram_window.show()
        self.histogram_window.raise_()
        self.histogram_window.activateWindow()

from csv_load_options_dialog import CSVLoadOptionsDialog

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("umbrella.ico"))
    
    # Configurar estilo oscuro
    app.setStyle('Fusion')
    dark_palette = app.palette()
    dark_palette.setColor(dark_palette.ColorRole.Window, QColor(43, 43, 43))
    dark_palette.setColor(dark_palette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.Base, QColor(35, 35, 35))
    dark_palette.setColor(dark_palette.ColorRole.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(dark_palette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(dark_palette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(dark_palette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(dark_palette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(dark_palette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(dark_palette)
    
    try:
        window = CSVPlotterApp()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        QMessageBox.critical(None, "Error fatal", f"No se pudo iniciar la aplicación:\n{str(e)}")
        sys.exit(1)