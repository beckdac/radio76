import asyncio
import math

import numpy as np
import sounddevice as sd

# Audio Settings
SAMPLERATE = 48000
CHANNELS = 1
DTYPE = 'int16'
BLOCKSIZE = 1024 # Size of buffer
UDP_PORT = 5005

# Queue to bridge UDP receiving and audio playback
audio_queue = asyncio.Queue(maxsize=10)

received_packets = 0
queue_full = 0

class AudioProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data, addr):
        # Put audio data into queue without blocking
        global received_packets
        global queue_full
        try:
            received_packets += 1
            audio_queue.put_nowait(data)
        except asyncio.QueueFull:
            queue_full += 1
            pass # Drop packet if queue is too full



chars = '.:-=+*#%@'
gradient = []
for char in chars:
    gradient.append(f"{char}")



async def audio_player():
    """Consumes data from queue and plays it."""
    high = 3000
    low = 50
    columns = 120
    samplerate = 48000
    gain = .1
    delta_f = (high - low) / (columns - 1)
    fftsize = math.ceil(samplerate / delta_f)
    low_bin = math.floor(low / delta_f)

    # Start sounddevice output stream
    with sd.RawOutputStream(samplerate=SAMPLERATE, channels=CHANNELS, 
                             dtype=DTYPE, blocksize=BLOCKSIZE) as stream:
        while True:
            #if received_packets % 100 == 0:
            #    print(f"received {received_packets} with {queue_full} queue overruns")
            # Wait for data from UDP server
            data = await audio_queue.get()
            audio_data = np.frombuffer(data, dtype=np.int16).reshape(-1, 1)

            magnitude = np.abs(np.fft.rfft(audio_data[:, 0], n=fftsize))
            magnitude *= gain / fftsize
            line = (gradient[int(np.clip(x, 0, 1) * (len(gradient) - 1))]
                    for x in magnitude[low_bin:low_bin + columns])
            print(*line, sep='', end='\n')

            # Write data to output stream
            stream.write(data)
            audio_queue.task_done()




async def main_loop():
    # Get the local event loop
    loop = asyncio.get_running_loop()

    # Create UDP endpoint
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: AudioProtocol(),
        local_addr=('0.0.0.0', UDP_PORT)
    )

    print(f"UDP Audio Remote listening on 0.0.0.0:{UDP_PORT}")
    
    # Run the player
    await audio_player()

def main():
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("Remote audio stopped")

if __name__ == '__main__':
    main()
