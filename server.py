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

    gain = 0.001
    max_freq = 3000
    T_CYC = 15
    BPT = 2
    SYM_RATE = 6.25

    fft_len = int(BPT * SAMPLERATE // SYM_RATE)
    fft_out_len = fft_len // 2 + 1
    nFreqs = int(fft_out_len * 2 * max_freq / SAMPLERATE)
    audio_buffer = np.zeros(fft_len, dtype=np.float32)
    fft_in = np.zeros(fft_len, dtype=np.float32)
    fft_window = np.hanning(fft_len).astype(np.float32)

    while True:
        # Blocks until data is available
        data = audio_queue.get()

        samples = data.astype(np.float32).flatten()
        ns = len(samples)
        audio_buffer[:-ns] = audio_buffer[ns:]
        audio_buffer[-ns:] = samples

        # FFT Calculation
        np.multiply(audio_buffer, fft_window, out=fft_in)
        zfft = np.fft.rfft(fft_in)[:nFreqs]
        sp = np.clip(zfft.real*zfft.real + zfft.imag*zfft.imag, gain, None)

        # send data
        sio.emit('audio_fft', {'data': sp.tolist()})

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

