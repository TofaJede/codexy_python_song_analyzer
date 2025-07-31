import numpy as np
import librosa
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class AnalysisResults:
    duration: float
    tempo: float
    key_distribution: Dict[str, float]
    top_notes: List[Tuple[str, int]]
    band_energy: Dict[str, float]
    dynamic_range: float
    loudness_envelope: np.ndarray


class AudioAnalyzer:
    def __init__(self, file_path: str, sr: int = 22050):
        self.file_path = file_path
        self.sr = sr
        self.y = None
        self.duration = 0.0

    def load(self):
        self.y, _ = librosa.load(self.file_path, sr=self.sr)
        self.duration = librosa.get_duration(y=self.y, sr=self.sr)

    def analyze(self) -> AnalysisResults:
        if self.y is None:
            self.load()

        y = self.y
        sr = self.sr

        # Tempo
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

        # Chroma / key distribution
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean = chroma.mean(axis=1)
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        key_distribution = {
            note: float(val / chroma_mean.sum()) for note, val in zip(note_names, chroma_mean)
        }

        # Pitch tracking using pyin
        fmin = librosa.note_to_hz('C2')
        fmax = librosa.note_to_hz('C7')
        pitches, _ = librosa.pyin(y, fmin=fmin, fmax=fmax)
        valid_pitches = pitches[~np.isnan(pitches)]
        note_sequence = librosa.hz_to_note(valid_pitches)
        counts = Counter(note_sequence)
        top_notes = counts.most_common(10)

        # Frequency band energy
        S = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)

        def band_power(f_low, f_high):
            idx = (freqs >= f_low) & (freqs < f_high)
            return float(np.sum(S[idx, :] ** 2))

        band_energy = {
            'low': band_power(20, 250),
            'mid': band_power(250, 4000),
            'high': band_power(4000, sr / 2)
        }

        # Dynamic range
        rms = librosa.feature.rms(y=y)[0]
        dynamic_range = float(rms.max() - rms.min())

        # Loudness envelope
        loudness_envelope = rms

        return AnalysisResults(
            duration=self.duration,
            tempo=float(tempo),
            key_distribution=key_distribution,
            top_notes=top_notes,
            band_energy=band_energy,
            dynamic_range=dynamic_range,
            loudness_envelope=loudness_envelope,
        )
