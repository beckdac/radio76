import asyncio
from datetime import datetime
import struct

from aiohttp import web
import socketio
import socket
import pywsjtx

# Create an Async Socket.IO server
sio = socketio.AsyncServer(async_mode='aiohttp', cors_allowed_origins='*')
app = web.Application()
sio.attach(app)

# setup for multicast
MULTICAST_GRP = '224.0.0.1'
MULTICAST_PORT = 2237

MY_MAX_SCHEMA = 3

async def listen_WSJTX_multicast():
    """Background task to listen to multicast udp from wsjtx, parse it and forward it"""
    print("WSJTX UDP multicast listener task started")

    # Create the socket
    #print("setting socket opt")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    #print("binding")
    # Bind to the wildcard address and port
    sock.bind(('', MULTICAST_PORT))

    # Join the multicast group
    #print("joining multicast")
    mreq = struct.pack('4sl', socket.inet_aton(MULTICAST_GRP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    print(f"Listening to WSJTX multicast {MULTICAST_GRP}:{MULTICAST_PORT}")

    loop = asyncio.get_event_loop()
    try:
        while True:
            # Receive data asynchronously
            data, addr = await loop.run_in_executor(None, sock.recvfrom, 4096)

            out = {}

            if (data != None):
                the_packet = pywsjtx.WSJTXPacketClassFactory.from_udp_packet(addr, data)

            if type(the_packet) == pywsjtx.HeartBeatPacket:
                #print("heartbeat")
                max_schema = max(the_packet.max_schema, MY_MAX_SCHEMA)
                reply_beat_packet = pywsjtx.HeartBeatPacket.Builder(the_packet.wsjtx_id, max_schema)
                await loop.run_in_executor(None, sock.sendto, reply_beat_packet, addr)
                now = datetime.now()
                out['time'] = now.strftime("%Y-%m-%d %H:%M:%S")
                await sio.emit('heartbeat', out)
            elif type(the_packet) == pywsjtx.DecodePacket:
                #print("decode")
                out['id'] = the_packet.wsjtx_id
                out['new'] = the_packet.new_decode
                out['time'] = the_packet.time.strftime("%H:%M:%S")
                out['snr'] = the_packet.snr
                out['delta_time'] = f"{the_packet.delta_t:.4g}"
                out['delta_hz'] = the_packet.delta_f
                out['mode'] = the_packet.mode
                out['message'] = the_packet.message
                out['low_conf'] = the_packet.low_confidence
                out['off_air'] = the_packet.off_air
                await sio.emit('decode', {"rows": [out]})
            elif type(the_packet) == pywsjtx.StatusPacket:
                #print("status")
                out['id'] = the_packet.wsjtx_id
                out['dial_freq'] = the_packet.dial_frequency
                out['mode'] = the_packet.mode
                out['dx_call'] = the_packet.dx_call
                out['report'] = the_packet.report
                out['tx_mode'] = the_packet.tx_mode
                out['tx_enabled'] = the_packet.tx_enabled
                out['transmitting'] = the_packet.transmitting
                out['decoding'] = the_packet.decoding
                out['rx_df'] = the_packet.rx_df
                out['tx_df'] = the_packet.tx_df
                out['de_call'] = the_packet.de_call
                out['de_grid'] = the_packet.de_grid
                out['dx_grid'] = the_packet.dx_grid
                out['tx_watchdog'] = the_packet.tx_watchdog
                out['sub_mode'] = the_packet.sub_mode
                out['fast_mode'] = the_packet.fast_mode
                out['special_op_mode'] = the_packet.special_op_mode
                await sio.emit('status', out)
            elif type(the_packet) == pywsjtx.QSOLoggedPacket:
                print("QSO Logged")
                out['id'] = the_packet.wsjtx_id
                out['datetime_off'] = the_packet.datetime_off
                out['call'] = the_packet.call
                out['grid'] = the_packet.grid
                out['frequency'] = the_packet.frequency
                out['mode'] = the_packet.mode
                out['report_sent'] = the_packet.report_sent
                out['report_recv'] = the_packet.report_recv
                out['tx_power'] = the_packet.tx_power
                out['comments'] = the_packet.comments
                out['name'] = the_packet.name
                out['datetime_on'] = the_packet.datetime_on
                out['op_call'] = the_packet.op_call
                out['my_call'] = the_packet.my_call
                out['my_grid'] = the_packet.my_grid
                out['exchange_sent'] = the_packet.exchange_sent
                out['exchange_recv'] = the_packet.exchange_recv
                await sio.emit('qso_logged', out)
            elif type(the_packet) == pywsjtx.Packet:
                print("")
                await sio.emit('', out)
            elif type(the_packet) == pywsjtx.Packet:
                print("")
                await sio.emit('', out)
            elif type(the_packet) == pywsjtx.Packet:
                print("")
                await sio.emit('', out)
            elif type(the_packet) == pywsjtx.Packet:
                print("")
                await sio.emit('', out)
            elif type(the_packet) == pywsjtx.Packet:
                print("")
                await sio.emit('', out)
            elif type(the_packet) == pywsjtx.Packet:
                print("")
                await sio.emit('', out)
            elif type(the_packet) == pywsjtx.Packet:
                print("")
                await sio.emit('', out)
            elif type(the_packet) == pywsjtx.Packet:
                print("")
                await sio.emit('', out)
    except asyncio.CancelledError:
        print("WSJTX UDP multicast listener task cancelled")
    except Exception as e:
        print(f"EXCEPTION: {e}")


# --- Routes ---
async def index(request):
    """Serves the index.html file."""
    return web.FileResponse('index.html')

app.router.add_get('/', index)

@sio.event
async def connect(sid, environ):
    print(f'Client connected: {sid}')

@sio.event
async def update_control(sid, data):
    """
    Receives updates and broadcasts them asynchronously.
    """
    print(f"Update from {sid}: {data}")
    # Broadcast to all OTHER clients
    await sio.emit('control_update', data, skip_sid=sid)

@sio.event
async def disconnect(sid):
    print(f'Client disconnected: {sid}')


async def heartbeat_task():
    print("Heartbeat task starting")
    data = { }
    try:
        while True:
            await asyncio.sleep(2)  # Run every 2 seconds
            now = datetime.now()
            data['time'] = now.strftime("%Y-%m-%d %H:%M:%S")
            await sio.emit('gateway_heartbeat', data)
    except asyncio.CancelledError:
        print("Heartbeat task cancelled")

async def start_background_tasks(app):
    app['udp_listener'] = asyncio.create_task(listen_WSJTX_multicast())
    app['heartbeat'] = asyncio.create_task(heartbeat_task())

async def cleanup_background_tasks(app):
    app['heartbeat'].cancel()
    await app['heartbeat']
    app['udp_listener'].cancel()
    await app['udp_listener']

# Register the startup and cleanup signals
app.on_startup.append(start_background_tasks)
app.on_cleanup.append(cleanup_background_tasks)


if __name__ == '__main__':
    web.run_app(app, port=5000)
