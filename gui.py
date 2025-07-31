import sys
import os
from PyQt5 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
import numpy as np
from audio_analyzer import AudioAnalyzer

ACCENT = '#6433a2'


class DropLabel(QtWidgets.QLabel):
    file_dropped = QtCore.pyqtSignal(str)

    def __init__(self, text='Drop audio file here'):
        super().__init__(text)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.setStyleSheet(f'border: 2px dashed {ACCENT}; padding: 40px;')

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
        self.setStyleSheet(f'background-color: #111; color: {ACCENT};')
        self.analyzer = None
        self._loader = None
        self._thread = None

        self.drop_label = DropLabel()
        self.drop_label.file_dropped.connect(self.load_file)

        self.browse_btn = QtWidgets.QPushButton('Browse')
        self.browse_btn.clicked.connect(self.open_file_dialog)
        self.browse_btn.setStyleSheet(f'background-color:{ACCENT}; color:#fff;')

        drop_container = QtWidgets.QWidget()
        drop_layout = QtWidgets.QVBoxLayout(drop_container)
        drop_layout.setContentsMargins(0, 0, 0, 0)
        drop_layout.addWidget(self.drop_label)
        drop_layout.addWidget(self.browse_btn)

        self.waveform_plot = pg.PlotWidget()
        self.waveform_plot.setBackground('#111')
        self.waveform_plot.getPlotItem().hideAxis('bottom')
        self.waveform_plot.getPlotItem().hideAxis('left')

        self.key_plot = pg.BarGraphItem(x=range(12), height=np.zeros(12), width=0.6, brush=ACCENT)
        self.key_widget = pg.PlotWidget()
        self.key_widget.setBackground('#111')
        self.key_widget.addItem(self.key_plot)
        self.key_widget.getPlotItem().getAxis('bottom').setTicks([
            [(i, note) for i, note in enumerate(['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'])]
        ])

        self.bpm_label = QtWidgets.QLabel('BPM: -')
        self.bpm_label.setAlignment(QtCore.Qt.AlignCenter)
        self.duration_label = QtWidgets.QLabel('Duration: -')
        self.duration_label.setAlignment(QtCore.Qt.AlignCenter)

        self.note_list = QtWidgets.QListWidget()
        self.eq_plot = pg.PlotWidget()
        self.eq_bar = pg.BarGraphItem(x=[0,1,2], height=[0,0,0], width=0.6, brush=ACCENT)
        self.eq_plot.addItem(self.eq_bar)
        self.eq_plot.getPlotItem().getAxis('bottom').setTicks([
            [(0,'Low'),(1,'Mid'),(2,'High')]
        ])

        self.dynamic_meter = QtWidgets.QProgressBar()
        self.dynamic_meter.setRange(0, 1000)

        self.reset_btn = QtWidgets.QPushButton('Reset')
        self.reset_btn.clicked.connect(self.reset)
        self.reset_btn.setStyleSheet(f'background-color:{ACCENT}; color:#fff;')

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(drop_container, 0, 0, 1, 2)
        layout.addWidget(self.waveform_plot, 1, 0, 1, 2)
        layout.addWidget(self.key_widget, 2, 0)
        layout.addWidget(self.note_list, 2, 1)
        layout.addWidget(self.eq_plot, 3, 0)
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
