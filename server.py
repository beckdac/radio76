import math
import threading
import queue

import socketio
import sounddevice as sd
import numpy as np
from werkzeug.serving import run_simple

CHANNELS=1
SAMPLERATE=48000
BLOCKSIZE=8192
DEVICE=15

# Use a standard thread-safe Queue
audio_queue = queue.Queue(maxsize=10)

sio = socketio.Server(cors_allowed_origins='*', async_mode='threading')
app = socketio.WSGIApp(sio)

def audio_callback(indata, frames, time, status):
    """Producer: Runs in the sounddevice real thread."""
    try:
        audio_queue.put_nowait(indata.copy())
    except queue.Full:
        pass

def emit_worker():
    """Consumer: Runs in a standard Python thread."""
    print("Emission worker started.")

    high = 3000
    low = 50
    columns = 200 
    gain = 100
    delta_f = (high - low) / (columns - 1)
    fftsize = math.ceil(SAMPLERATE / delta_f)
    low_bin = math.floor(low / delta_f)

    while True:
        # Blocks until data is available
        data = audio_queue.get()

        # FFT Calculation
        magnitude = np.abs(np.fft.rfft(data[:, 0], n=fftsize))[0:columns]
        magnitude *= gain / fftsize

        # Log scaling often looks better for heatmaps
        # np.log1p(x) is log(1+x) to avoid log(0)
        log_fft = np.log1p(magnitude)

        sio.emit('audio_fft', {'data': log_fft.tolist()})

@sio.event
def connect(sid, environ):
    print(f"Client connected: {sid}")

if __name__ == '__main__':
    # Start the worker thread
    t = threading.Thread(target=emit_worker, daemon=True)
    t.start()

    # Start the audio stream
    stream = sd.InputStream(device=DEVICE,
                            callback=audio_callback,
                            channels=CHANNELS,
                            samplerate=SAMPLERATE,
                            blocksize=BLOCKSIZE)
    
    with stream:
        print("Server running on http://localhost:5000")
        # Run using a standard WSGI server
        run_simple('localhost', 5000, app)

