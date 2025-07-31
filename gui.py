import sys
import os
from PyQt5 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
import numpy as np
from audio_analyzer import AudioAnalyzer

ACCENT = '#ff0000'
BACKGROUND = '#1a001f'
GRADIENT = 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a001f, stop:1 #3e0066)'
_grad = QtGui.QLinearGradient(0, 0, 0, 1)
_grad.setCoordinateMode(QtGui.QGradient.ObjectBoundingMode)
_grad.setColorAt(0, QtGui.QColor('#1a001f'))
_grad.setColorAt(1, QtGui.QColor('#3e0066'))
GRADIENT_BRUSH = QtGui.QBrush(_grad)


class DropLabel(QtWidgets.QLabel):
    file_dropped = QtCore.pyqtSignal(str)

    def __init__(self, text='Drop audio file here'):
        super().__init__(text)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.setStyleSheet(f'border: 2px dashed {ACCENT}; padding: 40px; background:{GRADIENT}; color:#fff;')

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            self.file_dropped.emit(url.toLocalFile())
            break


class AnalyzerWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(object, object)
    error = QtCore.pyqtSignal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    @QtCore.pyqtSlot()
    def run(self):
        try:
            analyzer = AudioAnalyzer(self.path)
            results = analyzer.analyze()
            self.finished.emit(analyzer, results)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Neon Song Analyzer')
        self.setStyleSheet(f'background: {GRADIENT}; color: #fff;')
        self.analyzer = None
        self._loader = None
        self._thread = None

        self.drop_label = DropLabel()
        self.drop_label.setToolTip("Drag a song here or click Browse to analyze.")
        self.drop_label.file_dropped.connect(self.load_file)

        self.browse_btn = QtWidgets.QPushButton('Browse')
        self.browse_btn.setToolTip("Select an audio file from disk.")
        self.browse_btn.clicked.connect(self.open_file_dialog)
        self.browse_btn.setStyleSheet(
            f'background:{GRADIENT}; color:#fff; border:1px solid {ACCENT};'
        )

        drop_container = QtWidgets.QWidget()
        drop_layout = QtWidgets.QVBoxLayout(drop_container)
        drop_layout.setContentsMargins(0, 0, 0, 0)
        drop_layout.addWidget(self.drop_label)
        drop_layout.addWidget(self.browse_btn)

        self.waveform_plot = pg.PlotWidget()
        self.waveform_plot.setToolTip("Waveform of the audio over time.")
        self.waveform_plot.setBackground(BACKGROUND)
        self.waveform_plot.setTitle("Waveform")
        self.waveform_plot.getPlotItem().setLabel('bottom', 'Time (s)')
        self.waveform_plot.getPlotItem().setLabel('left', 'Amplitude')

        self.key_plot = pg.BarGraphItem(x=range(12), height=np.zeros(12), width=0.6, brush=GRADIENT_BRUSH)
        self.key_widget = pg.PlotWidget()
        self.key_widget.setToolTip("Distribution of detected musical keys.")
        self.key_widget.setBackground(BACKGROUND)
        self.key_widget.setTitle("Key Distribution")
        self.key_widget.addItem(self.key_plot)
        self.key_widget.getPlotItem().getAxis('bottom').setTicks([
            [(i, note) for i, note in enumerate(['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'])]
        ])
        self.key_widget.getPlotItem().setLabel('bottom', 'Key')
        self.key_widget.getPlotItem().setLabel('left', 'Count')

        self.bpm_label = QtWidgets.QLabel('BPM: -')
        self.bpm_label.setAlignment(QtCore.Qt.AlignCenter)
        self.duration_label = QtWidgets.QLabel('Duration: -')
        self.duration_label.setAlignment(QtCore.Qt.AlignCenter)

        self.note_list = QtWidgets.QListWidget()
        self.note_list.setToolTip("Most frequent melody notes.")
        self.note_list.setStyleSheet(f'background:{BACKGROUND}; color:#fff;')
        self.eq_plot = pg.PlotWidget()
        self.eq_plot.setToolTip("Energy in low, mid, and high frequency bands.")
        self.eq_plot.setBackground(BACKGROUND)
        self.eq_plot.setTitle("Frequency Spectrum")
        self.eq_bar = pg.BarGraphItem(x=[0,1,2], height=[0,0,0], width=0.6, brush=GRADIENT_BRUSH)
        self.eq_plot.addItem(self.eq_bar)
        self.eq_plot.getPlotItem().getAxis('bottom').setTicks([
            [(0,'Low'),(1,'Mid'),(2,'High')]
        ])
        self.eq_plot.getPlotItem().setLabel('bottom', 'Band')
        self.eq_plot.getPlotItem().setLabel('left', 'Energy')

        self.dynamic_meter = QtWidgets.QProgressBar()
        self.dynamic_meter.setToolTip("Dynamic range (0–1000 scale).")
        self.dynamic_meter.setRange(0, 1000)
        self.dynamic_meter.setStyleSheet(
            f"QProgressBar {{background-color: {BACKGROUND}; color: #fff; border: 1px solid {ACCENT};}}"
            f" QProgressBar::chunk {{background-color: {ACCENT};}}"
        )

        self.reset_btn = QtWidgets.QPushButton('Reset')
        self.reset_btn.setToolTip("Clear analysis results.")
        self.reset_btn.clicked.connect(self.reset)
        self.reset_btn.setStyleSheet(
            f'background:{GRADIENT}; color:#fff; border:1px solid {ACCENT};'
        )

        self.waveform_label = QtWidgets.QLabel("Waveform")
        self.waveform_label.setAlignment(QtCore.Qt.AlignCenter)
        self.key_label = QtWidgets.QLabel("Key Distribution")
        self.key_label.setAlignment(QtCore.Qt.AlignCenter)
        self.eq_label = QtWidgets.QLabel("Frequency Spectrum")
        self.eq_label.setAlignment(QtCore.Qt.AlignCenter)

        waveform_container = QtWidgets.QWidget()
        waveform_layout = QtWidgets.QVBoxLayout(waveform_container)
        waveform_layout.setContentsMargins(0, 0, 0, 0)
        waveform_layout.addWidget(self.waveform_label)
        waveform_layout.addWidget(self.waveform_plot)

        key_container = QtWidgets.QWidget()
        key_layout = QtWidgets.QVBoxLayout(key_container)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.addWidget(self.key_label)
        key_layout.addWidget(self.key_widget)

        eq_container = QtWidgets.QWidget()
        eq_layout = QtWidgets.QVBoxLayout(eq_container)
        eq_layout.setContentsMargins(0, 0, 0, 0)
        eq_layout.addWidget(self.eq_label)
        eq_layout.addWidget(self.eq_plot)

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(drop_container, 0, 0, 1, 2)
        layout.addWidget(waveform_container, 1, 0, 1, 2)
        layout.addWidget(key_container, 2, 0)
        layout.addWidget(self.note_list, 2, 1)
        layout.addWidget(eq_container, 3, 0)
        layout.addWidget(self.dynamic_meter, 3, 1)
        layout.addWidget(self.bpm_label, 4, 0)
        layout.addWidget(self.duration_label, 4, 1)
        layout.addWidget(self.reset_btn, 5, 0, 1, 2)

    def load_file(self, path):
        if self._thread is not None:
            return

        self._loader = QtWidgets.QProgressDialog("Analyzing...", None, 0, 0, self)
        self._loader.setWindowModality(QtCore.Qt.ApplicationModal)
        self._loader.setCancelButton(None)
        self._loader.show()

        self._thread = QtCore.QThread(self)
        self._worker = AnalyzerWorker(path)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self.on_analysis_finished)
        self._worker.error.connect(self.on_analysis_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        self._thread.finished.connect(self.thread_cleanup)
        self._thread.start()

    def thread_cleanup(self):
        self._thread.deleteLater()
        self._thread = None
        self._worker = None

    def on_analysis_finished(self, analyzer, results):
        self.analyzer = analyzer
        self.drop_label.setText(os.path.basename(analyzer.file_path))
        self.update_ui(results)
        if self._loader:
            self._loader.close()
            self._loader = None

    def on_analysis_error(self, message):
        if self._loader:
            self._loader.close()
            self._loader = None
        QtWidgets.QMessageBox.critical(self, 'Analysis Error', message)

    def open_file_dialog(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open Audio File', '', 'Audio Files (*.mp3 *.wav *.flac)')
        if path:
            self.load_file(path)

    def update_ui(self, res):
        x = np.linspace(0, res.duration, num=len(self.analyzer.y))
        self.waveform_plot.plot(x, self.analyzer.y, pen=ACCENT, clear=True)

        heights = [res.key_distribution[note] for note in ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']]
        self.key_plot.setOpts(height=heights)

        self.bpm_label.setText(f'BPM: {res.tempo:.1f}')
        self.duration_label.setText(f'Duration: {res.duration:.2f}s')

        self.note_list.clear()
        for note, count in res.top_notes:
            self.note_list.addItem(f'{note}: {count}')

        self.eq_bar.setOpts(height=[res.band_energy['low'], res.band_energy['mid'], res.band_energy['high']])

        self.dynamic_meter.setValue(int(res.dynamic_range * 1000))

    def reset(self):
        self.waveform_plot.clear()
        self.key_plot.setOpts(height=np.zeros(12))
        self.bpm_label.setText('BPM: -')
        self.duration_label.setText('Duration: -')
        self.note_list.clear()
        self.eq_bar.setOpts(height=[0,0,0])
        self.dynamic_meter.setValue(0)
        self.analyzer = None


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.resize(800, 600)
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
