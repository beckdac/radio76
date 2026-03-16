import asyncio
import sounddevice as sd
import numpy as np

# Audio Settings
SAMPLERATE = 48000
CHANNELS = 1
DTYPE = 'int16'
BLOCKSIZE = 1024 # Size of buffer
UDP_PORT = 5005

# Queue to bridge UDP receiving and audio playback
audio_queue = asyncio.Queue(maxsize=10)

class AudioProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data, addr):
        # Put audio data into queue without blocking
        print(".", end="")
        try:
            audio_queue.put_nowait(data)
        except asyncio.QueueFull:
            print("dropped packet because of full queue")
            pass # Drop packet if queue is too full

async def audio_player():
    """Consumes data from queue and plays it."""
    # Start sounddevice output stream
    with sd.RawOutputStream(samplerate=SAMPLERATE, channels=CHANNELS, 
                             dtype=DTYPE, blocksize=BLOCKSIZE) as stream:
        while True:
            # Wait for data from UDP server
            data = await audio_queue.get()
            
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
