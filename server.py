import socketio
import sounddevice as sd
import numpy as np
import threading
import queue
from werkzeug.serving import run_simple

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
    while True:
        # Blocks until data is available
        data = audio_queue.get()
        
        # FFT Calculation
        windowed = data[:, 0] * np.hanning(len(data))
        fft_data = np.abs(np.fft.rfft(windowed))

        # Log scaling often looks better for heatmaps
        # np.log1p(x) is log(1+x) to avoid log(0)
        log_fft = np.log1p(fft_data[0:150])

        sio.emit('audio_fft', {'data': log_fft.tolist()})

@sio.event
def connect(sid, environ):
    print(f"Client connected: {sid}")

if __name__ == '__main__':
    # Start the worker thread
    t = threading.Thread(target=emit_worker, daemon=True)
    t.start()

    # Start the audio stream
    stream = sd.InputStream(device=15,
                            callback=audio_callback,
                            channels=1,
                            samplerate=48000,
                            blocksize=2048)
    
    with stream:
        print("Server running on http://localhost:5000")
        # Run using a standard WSGI server
        run_simple('localhost', 5000, app)

