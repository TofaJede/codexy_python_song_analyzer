import sys
import os
import math
from PyQt5 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
import numpy as np
from audio_analyzer import AudioAnalyzer

# Default colors
DEFAULT_ACCENT = '#bf00ff'
SECONDARY = '#8b0000'
BACKGROUND = '#000000'
# Radial gradient for a soft radiant background
GRADIENT = (
    'qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, '
    'stop:0 #8b0000, stop:1 #000000)'
)

_grad = QtGui.QRadialGradient(0.5, 0.5, 0.5)
_grad.setCoordinateMode(QtGui.QGradient.ObjectBoundingMode)
_grad.setColorAt(0, QtGui.QColor(SECONDARY))
_grad.setColorAt(1, QtGui.QColor('#000000'))
GRADIENT_BRUSH = QtGui.QBrush(_grad)


def neon_glow(widget: QtWidgets.QWidget, color: str) -> None:
    """Apply a soft neon glow to the given widget."""
    effect = QtWidgets.QGraphicsDropShadowEffect()
    effect.setBlurRadius(30)
    effect.setColor(QtGui.QColor(color))
    effect.setOffset(0)
    widget.setGraphicsEffect(effect)


class DropLabel(QtWidgets.QLabel):
    file_dropped = QtCore.pyqtSignal(str)

    def __init__(self, text='Drop audio file here'):
        super().__init__(text)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.setStyleSheet(
            f'border: 2px dashed {DEFAULT_ACCENT}; padding: 40px; background:{GRADIENT}; color:#fff;'
        )

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
        self.accent = DEFAULT_ACCENT
        self._accent_phase = 0.0
        self.setWindowTitle('Neon Song Analyzer – Key, BPM & EQ Visualizer')
        self.setStyleSheet(
            f'background: {GRADIENT}; color: #fff; font-family: "Comic Sans MS";'
        )
        self.analyzer = None
        self._loader = None
        self._thread = None

        self.drop_label = DropLabel()
        self.drop_label.setToolTip("Drag a song here or click Browse to analyze.")
        self.drop_label.setAccessibleName("File Drop Area")
        self.drop_label.setAccessibleDescription(
            "Drop an audio file here to analyze it."
        )
        self.drop_label.file_dropped.connect(self.load_file)

        self.browse_btn = QtWidgets.QPushButton('Browse')
        self.browse_btn.setToolTip("Select an audio file from disk.")
        self.browse_btn.setAccessibleName("Browse Button")
        self.browse_btn.setAccessibleDescription(
            "Open a file dialog to select an audio file for analysis."
        )
        self.browse_btn.setShortcut('Ctrl+O')
        self.browse_btn.clicked.connect(self.open_file_dialog)

        drop_container = QtWidgets.QWidget()
        drop_layout = QtWidgets.QVBoxLayout(drop_container)
        drop_layout.setContentsMargins(0, 0, 0, 0)
        drop_layout.addWidget(self.drop_label)
        drop_layout.addWidget(self.browse_btn)

        self.waveform_plot = pg.PlotWidget()
        self.waveform_plot.setToolTip("Waveform of the audio over time.")
        self.waveform_plot.setAccessibleName("Waveform Plot")
        self.waveform_plot.setAccessibleDescription(
            "Displays the waveform of the loaded audio file over time."
        )
        self.waveform_plot.setBackground(BACKGROUND)
        self.waveform_plot.setTitle("Waveform")
        self.waveform_plot.getPlotItem().setLabel('bottom', 'Time (s)')
        self.waveform_plot.getPlotItem().setLabel('left', 'Amplitude')

        self.key_plot = pg.BarGraphItem(x=range(12), height=np.zeros(12), width=0.6, brush=GRADIENT_BRUSH)
        self.key_widget = pg.PlotWidget()
        self.key_widget.setToolTip("Distribution of detected musical keys.")
        self.key_widget.setAccessibleName("Key Distribution Plot")
        self.key_widget.setAccessibleDescription(
            "Shows the distribution of detected musical keys in the song."
        )
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
        self.note_list.setAccessibleName("Top Notes List")
        self.note_list.setAccessibleDescription(
            "Lists the most frequent melody notes detected in the song."
        )
        self.eq_plot = pg.PlotWidget()
        self.eq_plot.setToolTip("Energy in low, mid, and high frequency bands.")
        self.eq_plot.setAccessibleName("Frequency Spectrum Plot")
        self.eq_plot.setAccessibleDescription(
            "Shows the energy levels for low, mid, and high frequency bands."
        )
        self.eq_plot.setBackground(BACKGROUND)
        self.eq_plot.setTitle("Frequency Spectrum")
        self.eq_bar = pg.BarGraphItem(x=[0,1,2], height=[0,0,0], width=0.6, brush=GRADIENT_BRUSH)
        self.eq_plot.addItem(self.eq_bar)
        self.eq_plot.getPlotItem().getAxis('bottom').setTicks([
            [(0,'Low'),(1,'Mid'),(2,'High')]
        ])
        self.eq_plot.getPlotItem().setLabel('bottom', 'Band')
        self.eq_plot.getPlotItem().setLabel('left', 'Energy')

        self.dynamic_label = QtWidgets.QLabel("Dynamic Range: - dB")
        self.dynamic_label.setAlignment(QtCore.Qt.AlignCenter)
        self.dynamic_label.setToolTip("Overall dynamic range in decibels.")
        self.dynamic_label.setAccessibleName("Dynamic Range Label")
        self.dynamic_label.setAccessibleDescription(
            "Shows the song's dynamic range in decibels."
        )

        self.dynamic_plot = pg.PlotWidget()
        self.dynamic_plot.setToolTip("Loudness envelope over time in dB.")
        self.dynamic_plot.setAccessibleName("Dynamic Range Plot")
        self.dynamic_plot.setAccessibleDescription(
            "Displays the loudness envelope (RMS) of the song in decibels over time."
        )
        self.dynamic_plot.setBackground(BACKGROUND)
        self.dynamic_plot.setTitle("Dynamic Range")
        self.dynamic_plot.getPlotItem().setLabel('bottom', 'Time (s)')
        self.dynamic_plot.getPlotItem().setLabel('left', 'dB')

        self.reset_btn = QtWidgets.QPushButton('Reset')
        self.reset_btn.setToolTip("Clear analysis results.")
        self.reset_btn.setAccessibleName("Reset Button")
        self.reset_btn.setAccessibleDescription(
            "Clears analysis results and resets the interface."
        )
        self.reset_btn.setShortcut('Ctrl+R')
        self.reset_btn.clicked.connect(self.reset)

        self.about_btn = QtWidgets.QPushButton('About')
        self.about_btn.setToolTip("About this application.")
        self.about_btn.setAccessibleName("About Button")
        self.about_btn.setAccessibleDescription(
            "Shows information about the application."
        )
        self.about_btn.clicked.connect(self.show_about_dialog)

        self.exit_btn = QtWidgets.QPushButton('Exit')
        self.exit_btn.setToolTip("Exit the application.")
        self.exit_btn.setAccessibleName("Exit Button")
        self.exit_btn.setAccessibleDescription(
            "Closes the application.",
        )
        self.exit_btn.setShortcut('Ctrl+Q')
        self.exit_btn.clicked.connect(QtWidgets.QApplication.instance().quit)

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

        dynamic_container = QtWidgets.QWidget()
        dynamic_layout = QtWidgets.QVBoxLayout(dynamic_container)
        dynamic_layout.setContentsMargins(0, 0, 0, 0)
        dynamic_layout.addWidget(self.dynamic_label)
        dynamic_layout.addWidget(self.dynamic_plot)

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(drop_container, 0, 0, 1, 2)
        layout.addWidget(waveform_container, 1, 0, 1, 2)
        layout.addWidget(key_container, 2, 0)
        layout.addWidget(self.note_list, 2, 1)
        layout.addWidget(eq_container, 3, 0)
        layout.addWidget(dynamic_container, 3, 1)
        layout.addWidget(self.bpm_label, 4, 0)
        layout.addWidget(self.duration_label, 4, 1)

        button_container = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addWidget(self.reset_btn)
        button_layout.addWidget(self.about_btn)
        button_layout.addWidget(self.exit_btn)
        layout.addWidget(button_container, 5, 0, 1, 2)

        self.apply_accent()
        self.accent_timer = QtCore.QTimer(self)
        self.accent_timer.timeout.connect(self.cycle_accent)
        self.accent_timer.start(50)

    def apply_accent(self) -> None:
        c = self.accent
        self.drop_label.setStyleSheet(
            f'border: 2px dashed {c}; padding: 40px; background:{GRADIENT}; color:#fff;'
        )
        self.browse_btn.setStyleSheet(
            f'background:{GRADIENT}; color:#fff; border:1px solid {c};'
        )
        self.reset_btn.setStyleSheet(
            f'background:{GRADIENT}; color:#fff; border:1px solid {c};'
        )
        self.about_btn.setStyleSheet(
            f'background:{GRADIENT}; color:#fff; border:1px solid {c};'
        )
        self.exit_btn.setStyleSheet(
            f'background:{GRADIENT}; color:#fff; border:1px solid {c};'
        )
        self.note_list.setStyleSheet(f'background:{BACKGROUND}; color:{c};')
        for lbl in (
            self.bpm_label,
            self.duration_label,
            self.waveform_label,
            self.key_label,
            self.eq_label,
            self.dynamic_label,
        ):
            lbl.setStyleSheet(f'color:{c};')
        for w in (
            self.drop_label,
            self.browse_btn,
            self.reset_btn,
            self.about_btn,
            self.exit_btn,
            self.dynamic_plot,
        ):
            neon_glow(w, c)

    def cycle_accent(self) -> None:
        base = QtGui.QColor(DEFAULT_ACCENT)
        h, s, v, a = base.getHsv()
        v = 150 + int(80 * math.sin(self._accent_phase))
        v = max(0, min(255, v))
        pulse = QtGui.QColor.fromHsv(h, s, v, a)
        self.accent = pulse.name()
        self.apply_accent()
        if hasattr(self, 'waveform_data'):
            self.waveform_plot.plot(*self.waveform_data, pen=pg.mkPen(self.accent), clear=True)
        if hasattr(self, 'dynamic_data'):
            self.dynamic_plot.plot(*self.dynamic_data, pen=pg.mkPen(self.accent), clear=True)
        self._accent_phase += 0.1

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

    def show_about_dialog(self):
        QtWidgets.QMessageBox.about(
            self,
            'About Neon Song Analyzer',
            'Neon Song Analyzer – Key, BPM & EQ Visualizer\n'
            'Version 1.0.0\n\n'
            'Analyzes songs to display key, tempo, and frequency spectrum.\n'
            'Credits: OpenAI Codexy'
        )

    def update_ui(self, res):
        x = np.linspace(0, res.duration, num=len(self.analyzer.y))
        self.waveform_data = (x, self.analyzer.y)
        self.waveform_plot.plot(x, self.analyzer.y, pen=pg.mkPen(self.accent), clear=True)

        heights = [res.key_distribution[note] for note in ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']]
        self.key_plot.setOpts(height=heights)

        self.bpm_label.setText(f'BPM: {res.tempo:.1f}')
        mins, secs = divmod(int(res.duration), 60)
        self.duration_label.setText(f'Duration: {mins:02d}:{secs:02d}')

        self.note_list.clear()
        for note, count in res.top_notes:
            self.note_list.addItem(f'{note}: {count}')

        self.eq_bar.setOpts(height=[res.band_energy['low'], res.band_energy['mid'], res.band_energy['high']])

        x_rms = np.linspace(0, res.duration, num=len(res.loudness_envelope))
        self.dynamic_data = (x_rms, res.loudness_envelope)
        self.dynamic_plot.plot(x_rms, res.loudness_envelope, pen=pg.mkPen(self.accent), clear=True)
        self.dynamic_label.setText(f'Dynamic Range: {res.dynamic_range:.2f} dB')

    def reset(self):
        self.waveform_plot.clear()
        self.key_plot.setOpts(height=np.zeros(12))
        self.bpm_label.setText('BPM: -')
        self.duration_label.setText('Duration: -')
        self.note_list.clear()
        self.eq_bar.setOpts(height=[0,0,0])
        self.dynamic_plot.clear()
        self.dynamic_label.setText('Dynamic Range: - dB')
        if hasattr(self, 'waveform_data'):
            del self.waveform_data
        if hasattr(self, 'dynamic_data'):
            del self.dynamic_data
        self.analyzer = None


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.resize(800, 600)
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
