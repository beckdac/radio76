import asyncio
import socket
import time

import numpy as np
import sounddevice as sd


# Configuration
UDP_IP = "192.168.1.16"
UDP_PORT = 5005
CHANNELS = 1
DEVICE = 15
DTYPE = 'int16'
BLOCK_SIZE = 1024 # Frames per buffer
PACKET_UPDATE = 1000

# Create UDP Socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

async def inputstream_generator(channels=1, **kwargs):
    """Generator that yields blocks of arrays"""
    q_in = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def callback(indata, frame_count, time_info, status):
        loop.call_soon_threadsafe(q_in.put_nowait, (indata, status))

    stream = sd.RawInputStream(callback=callback, channels=channels, **kwargs)
    sent_packets = 0
    with stream:
        while True:
            audio_data, status = await q_in.get()
        
            # Send raw bytes
            sent_packets += 1
            sock.sendto(audio_data, (UDP_IP, UDP_PORT))
            if sent_packets % PACKET_UPDATE == 0:
                print(f"sent {sent_packets} packets")
            q_in.task_done()
            #yield indata, status

def oldcallback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status)
    #print(f"{len(indata)} : {frames}")
    # Put audio data into the queue for the async loop
    try:
        loop.call_soon_threadsafe(audio_queue.put_nowait, (indata.copy(), status))
    except asyncio.QueueFull:
        queue_full += 1
        pass # Drop audio frame if queue is too full


#sent_packets = 0

async def send_audio():
    """Reads from queue and sends audio over UDP."""
    print("Starting audio transmission...")
    global sent_packets
    while True:
        # Await data from the queue
        print(">")
        audio_data, status = await audio_queue.get()
        print("<")
        
        # Send raw bytes
        sent_packets += 1
        sock.sendto(audio_data.tobytes(), (UDP_IP, UDP_PORT))
        audio_queue.task_done()

        # print something occassionally
        if sent_packets % 10 == 0:
            print(f"sent {sent_packets} and had {queue_full} errors")

async def main_loop():
    # Start sounddevice recording
    device = sd.query_devices(DEVICE, 'input')
    samplerate = device['default_samplerate']
    device_name = device['name']
    print(f"using {samplerate} as the sample rate for device {DEVICE} identified as {device_name}")
    print(f"sending to {UDP_IP} on port {UDP_PORT}")
    await inputstream_generator(device=DEVICE, samplerate=samplerate, channels=CHANNELS, 
                        dtype=DTYPE, blocksize=BLOCK_SIZE)

def main():
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\nAudio capture stopped by user.")

if __name__ == "__main__":
    main()
