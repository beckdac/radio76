import asyncio
import sounddevice as sd
import numpy as np
import socket

# Configuration
UDP_IP = "192.168.1.16"
UDP_PORT = 5005
CHANNELS = 1
DEVICE = 15
DTYPE = 'int16'
BLOCK_SIZE = 1024 # Frames per buffer

# Create UDP Socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Async queue for bridging callback with asyncio loop
audio_queue = asyncio.Queue(10)

def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status)
    # Put audio data into the queue for the async loop
    try:
        audio_queue.put_nowait(indata.copy())
    except asyncio.QueueFull:
        print("dropped frames because of full queue")
        pass # Drop audio frame if queue is too full

async def send_audio():
    """Reads from queue and sends audio over UDP."""
    print("Starting audio transmission...")
    while True:
        # Await data from the queue
        print(">")
        audio_data = await audio_queue.get()
        
        # Send raw bytes
        print("<")
        sock.sendto(audio_data.tobytes(), (UDP_IP, UDP_PORT))
        audio_queue.task_done()

async def main_loop():
    # Start sounddevice recording
    device = sd.query_devices(DEVICE, 'input')
    samplerate = device['default_samplerate']
    device_name = device['name']
    print(f"using {samplerate} as the sample rate for device {DEVICE} identified as {device_name}")
    print(f"sending to {UDP_IP} on port {UDP_PORT}")
    with sd.InputStream(device=DEVICE,
                        samplerate=samplerate,
                        channels=CHANNELS, 
                        callback=callback,
                        dtype=DTYPE,
                        blocksize=BLOCK_SIZE):
        # Run sender task concurrently
        await send_audio()

def main():
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\nAudio capture stopped by user.")

if __name__ == "__main__":
    main()
