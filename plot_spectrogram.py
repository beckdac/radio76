from __future__ import annotations

import importlib.resources
import itertools
import math

import numpy as np
import sounddevice as sd
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid
from textual.widgets import Footer, Header, Label, TabbedContent, TabPane, Log

class Radio76App(App[None]):
    #AUTO_FOCUS = "SinePlot > PlotWidget"
    UPDATE_FREQUENCY = 2

    CSS = """
        PlotWidget {
            margin-right: 2;
            margin-bottom: 1;
        }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Log(max_lines=24, auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        self._timer = self.set_interval(
            1 / self.UPDATE_FREQUENCY, self.log_update, pause=False
        )

        self.theme = "tokyo-night"
    
    def log_update(self) -> None:
        log_widget = self.query_one(Log)
        log_width = log_widget.size.width
        global lines
        for line in lines:
            print(line)
            log_widget.write_line(line)
        lines = []



# Create a nice output gradient using ANSI escape sequences.
# Stolen from https://gist.github.com/maurisvh/df919538bcef391bc89f
colors = 30, 34, 35, 91, 93, 97
chars = ' :%#\t#%:'
gradient = []
for bg, fg in zip(colors, colors[1:]):
    for char in chars:
        if char == '\t':
            bg, fg = fg, bg
        else:
            #gradient.append(f'\x1b[{fg};{bg + 10}m{char}')
            gradient.append(f'{char}')

lines = []

def main() -> None:
    device = 14
    gain = 250
    block_duration_ms = 100
    columns = 100
    high = 3200
    low = 50
    samplerate = sd.query_devices(device, 'input')['default_samplerate']

    delta_f = (high - low) / (columns - 1)
    fftsize = math.ceil(samplerate / delta_f)
    low_bin = math.floor(low / delta_f)

    def callback(indata, frames, time, status):
        #print(frames)
        #print(len(indata[:,0]))
        if status:
            text = ' ' + str(status) + ' '
            print('\x1b[34;40m', text.center(columns, '#'),
                  '\x1b[0m', sep='')
        if any(indata):
            magnitude = np.abs(np.fft.rfft(indata[:, 0], n=fftsize))
            magnitude *= gain / fftsize
            line = (gradient[int(np.clip(x, 0, 1) * (len(gradient) - 1))]
                    for x in magnitude[low_bin:low_bin + columns])
            txt = "".join(line)
            #print(*line, sep='', end='\x1b[0m\n')
            #print(*line, sep='', end='\n')
            #print(f"pre {txt}")
            lines.append(f"{txt}\n")
            #lines.append(f"fii {len(list(line))}")
        else:
            print("no input")

    app = Radio76App()

    with sd.InputStream(device=device, channels=1, callback=callback,
                        blocksize=int(samplerate * block_duration_ms / 1000),
                        samplerate=samplerate):
        app.run()


if __name__ == "__main__":
    main()

