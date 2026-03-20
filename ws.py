"""
Monitors WSJTX UDP Multicast and shares the data via a websocket.

Includes a sample `index.html` that displays the data. Filters
canidate next calls and manages a state machine / model.
"""

import asyncio
import copy
from datetime import datetime
from enum import Enum
import json
import socket
import struct
import traceback

from aiohttp import web
import socketio
import pywsjtx


class StateMachineMessageType(Enum):
    STATUS = 1
    DECODE = 2
    QSO_LOGGED = 3
    SOCKET_INFO = 4


# Create an Async Socket.IO server
sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")
app = web.Application()
sio.attach(app)

# setup for multicast
MULTICAST_GRP = "224.0.0.1"
MULTICAST_PORT = 2237

MY_MAX_SCHEMA = 3


async def listen_WSJTX_multicast(state_machine_queue):
    """Background task to listen to multicast udp from wsjtx, parse it and forward it"""
    print("WSJTX UDP multicast listener task started")

    # Create the socket
    # print("setting socket opt")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # print("binding")
    # Bind to the wildcard address and port
    sock.bind(("", MULTICAST_PORT))

    # Join the multicast group
    # print("joining multicast")
    mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GRP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    print(f"Listening to WSJTX multicast {MULTICAST_GRP}:{MULTICAST_PORT}")
    socket_info_sent = False

    loop = asyncio.get_event_loop()
    try:
        while True:
            # Receive data asynchronously
            data, addr = await loop.run_in_executor(None, sock.recvfrom, 4096)

            # TODO: this uses the first sender as the address for all future comms
            # from outside of this loop
            if not socket_info_sent:
                await state_machine_queue.put({'type':StateMachineMessageType.SOCKET_INFO, 
                                               'sock':sock, 'addr':addr})
                socket_info_sent = True

            out = {}

            if data != None:
                the_packet = pywsjtx.WSJTXPacketClassFactory.from_udp_packet(addr, data)

            if type(the_packet) == pywsjtx.HeartBeatPacket:
                # print("heartbeat")
                max_schema = max(the_packet.max_schema, MY_MAX_SCHEMA)
                reply_beat_packet = pywsjtx.HeartBeatPacket.Builder(
                    the_packet.wsjtx_id, max_schema
                )
                await loop.run_in_executor(None, sock.sendto, reply_beat_packet, addr)
                now = datetime.now()
                out["time"] = now.strftime("%Y-%m-%d %H:%M:%S")
                await sio.emit("heartbeat", out)
            elif type(the_packet) == pywsjtx.DecodePacket:
                # print("decode")
                out["id"] = the_packet.wsjtx_id
                out["new"] = the_packet.new_decode
                out["time"] = the_packet.time.strftime("%H:%M:%S")
                out["snr"] = the_packet.snr
                out["delta_time"] = f"{the_packet.delta_t:.4g}"
                out["delta_hz"] = the_packet.delta_f
                out["mode"] = the_packet.mode
                out["message"] = the_packet.message
                out["low_conf"] = the_packet.low_confidence
                out["off_air"] = the_packet.off_air
                await sio.emit("decode", {"rows": [out]})
                sm_out = out
                sm_out["type"] = StateMachineMessageType.DECODE
                sm_out["pkt"] = the_packet
                await state_machine_queue.put(sm_out)
            elif type(the_packet) == pywsjtx.StatusPacket:
                # print("status")
                out["id"] = the_packet.wsjtx_id
                out["dial_freq"] = the_packet.dial_frequency
                out["mode"] = the_packet.mode
                out["dx_call"] = the_packet.dx_call
                out["report"] = the_packet.report
                out["tx_mode"] = the_packet.tx_mode
                out["tx_enabled"] = the_packet.tx_enabled
                out["transmitting"] = the_packet.transmitting
                out["decoding"] = the_packet.decoding
                out["rx_df"] = the_packet.rx_df
                out["tx_df"] = the_packet.tx_df
                out["de_call"] = the_packet.de_call
                out["de_grid"] = the_packet.de_grid
                out["dx_grid"] = the_packet.dx_grid
                out["tx_watchdog"] = the_packet.tx_watchdog
                out["sub_mode"] = the_packet.sub_mode
                out["fast_mode"] = the_packet.fast_mode
                out["special_op_mode"] = the_packet.special_op_mode
                await sio.emit("status", out)
                sm_out = {}
                sm_out["type"] = StateMachineMessageType.STATUS
                sm_out["dial_freq"] = the_packet.dial_frequency
                sm_out["mode"] = the_packet.mode
                sm_out["tx_enabled"] = the_packet.tx_enabled
                sm_out["transmitting"] = the_packet.transmitting
                sm_out["dx_call"] = the_packet.dx_call
                await state_machine_queue.put(sm_out)
            elif type(the_packet) == pywsjtx.QSOLoggedPacket:
                print("QSO Logged")
                out["id"] = the_packet.wsjtx_id
                out["datetime_off"] = the_packet.datetime_off.time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                out["call"] = the_packet.call
                out["grid"] = the_packet.grid
                out["frequency"] = the_packet.frequency
                out["mode"] = the_packet.mode
                out["report_sent"] = the_packet.report_sent
                out["report_recv"] = the_packet.report_recv
                out["tx_power"] = the_packet.tx_power
                out["comments"] = the_packet.comments
                out["name"] = the_packet.name
                out["datetime_on"] = the_packet.datetime_on.time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                out["op_call"] = the_packet.op_call
                out["my_call"] = the_packet.my_call
                out["my_grid"] = the_packet.my_grid
                out["exchange_sent"] = the_packet.exchange_sent
                out["exchange_recv"] = the_packet.exchange_recv
                print(f"{out}")
                await sio.emit("qso_logged", out)
                sm_out = {}
                sm_out["type"] = StateMachineMessageType.QSO_LOGGED
                sm_out["call"] = the_packet.call
                sm_out["mode"] = the_packet.mode
                await state_machine_queue.put(sm_out)
            elif type(the_packet) == pywsjtx.ClosePacket:
                print("WSJTX closing packet, raising asyncio.CancelledError")
                await sio.emit("wsjtx_closing", out)
                raise asyncio.CancelledError
            elif type(the_packet) == pywsjtx.ReplayPacket:
                print("replay packet ignored")
            elif type(the_packet) == pywsjtx.HaltTxPacket:
                print("halt tx packet ignored")
            elif type(the_packet) == pywsjtx.FreeTextPacket:
                print("free text packet ignored")
            elif type(the_packet) == pywsjtx.WSPRDecodePacket:
                print("wspr decode packet ignored")
            elif type(the_packet) == pywsjtx.LocationChangePacket:
                print("location change packet ignored")
            elif type(the_packet) == pywsjtx.LoggedADIFPacket:
                print("logged adif packet ignored")
            elif type(the_packet) == pywsjtx.HighlightCallsignPacket:
                print("highlight callsign packet ignored")
            else:
                print(f"unknown packet type encountered:")
                print(f"{the_packet}")
    except asyncio.CancelledError:
        print("WSJTX UDP multicast listener task cancelled")
    except Exception as e:
        print(f"EXCEPTION: {e}")


# --- Routes ---
async def index(request):
    """Serves the index.html file."""
    return web.FileResponse("index.html")


app.router.add_get("/", index)


@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")


@sio.event
async def update_control(sid, data):
    """
    Receives updates and broadcasts them asynchronously.
    """
    print(f"Update from {sid}: {data}")
    # Broadcast to all OTHER clients
    await sio.emit("control_update", data, skip_sid=sid)


@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")


async def heartbeat_task(state_update_queue):
    print("Heartbeat task starting")
    state = None
    sock = None
    addr = None
    loop = asyncio.get_event_loop()
    try:
        while True:
            await asyncio.sleep(1)  # Run every 1 second
            new_state = None
            # TODO: 
            # count of initiatied calls in list
            # count of completed calls in list

            # empty queue and update state information
            new_canidate = None
            while True:
                try:
                    (new_state, canidate) = state_update_queue.get_nowait()
                    # flatten dicts for json conversion
                    new_state.decodes = {str(k): v for k, v in new_state.decodes.items()}
                    new_state.lc_or_oa_decodes = {str(k): v for k, v in new_state.lc_or_oa_decodes.items()}
                    if new_state.sock:
                        sock = new_state.sock
                        new_state.sock = None
                    if new_state.addr:
                        addr = new_state.addr
                        new_state.addr = None
                    if canidate:
                        new_canidate = canidate
                except asyncio.QueueEmpty:
                    break
            if new_state != None:
                # update the state
                state = new_state
            if state != None:
                now = datetime.now()
                state.time = now.strftime("%Y-%m-%d %H:%M:%S")
                state.sock = None
                state.addr = None
                #print(f"{state}")
                await sio.emit("gateway_heartbeat", state.__dict__)
            if not state.busy and new_canidate:
                print(f"initiating reply to {new_canidate['message']}")
                reply_pkt = pywsjtx.ReplyPacket.Builder(new_canidate["pkt"])
                await loop.run_in_executor(None, sock.sendto, reply_pkt, addr)
    except asyncio.CancelledError:
        print("Heartbeat task cancelled")
    except Exception as e:
        print(f"state machine task exception occurred:\n{type(e)} : {e}")
        traceback.print_exc()


class StateMachineState():
    def __init__(self, snr_threshold=-10, delta_time_threshold=.5, max_cq_decode_age=20):
        self.busy = True
        self.dial_freq = None
        self.mode = None
        self.lc_or_oa_decodes = {}
        self.decodes = {}
        self.snr_threshold = snr_threshold
        self.delta_time_threshold = delta_time_threshold
        self.max_cq_decode_age = max_cq_decode_age
        self.time = None
        self.sock = None
        self.addr = None

    def __repr__(self):
        return f"{{ 'busy' : {self.busy}, 'dial_freq' : {self.dial_freq}, 'mode' : {self.mode},\n\
                'lc_or_oa_decodes' : {self.lc_or_oa_decodes},\n\
                'decodes' : {self.decodes},\n\
                'snr_threshold' : {self.snr_threshold},\n\
                'delta_time_threshold' : {self.delta_time_threshold},\n\
                'max_cq_decode_age' : {self.max_cq_decode_age},\n\
                'time' : {self.time},\n\
                'sock' : {self.sock},\n\
                'addr' : {self.addr}}}\n"


    def to_json(self):
        return json.dumps(self.__dict__)

async def state_machine_task(state_machine_queue, state_update_queue):
    """
    Models / manages the state of the system by observing messages

    Can send a call request if setting is turned on.  Will filter
    messages and identify canidate best calls.
    """
    print("State machine task starting")
    state = StateMachineState()
    calls_tried = {}
    calls_73 = {}
    canidate = None
    try:
        while True:
            data = await state_machine_queue.get()
            #print(f"message received: {data}")
            if data["type"] == StateMachineMessageType.STATUS:
                #print("looking at status message")
                reset = False
                if not data["tx_enabled"] and not data["transmitting"]:
                    state.busy = False
                else:
                    state.busy = True
                if state.dial_freq != data["dial_freq"]:
                    print("frequency change detected")
                    reset = True
                if state.mode != data["mode"]:
                    print("mode change detected")
                    reset = True
                if reset:
                    print("resetting for dial or mode change")
                    canidate = None
                    state.mode = data["mode"]
                    state.dial_freq = data["dial_freq"]
                # if we need new dictionaries of examined calls, set them up now
                dict_state = (state.dial_freq, state.mode)
                if calls_tried.get(dict_state, None) is None:
                    print(f"init calls tried dictionary for {dict_state}")
                    calls_tried[dict_state] = {}
                if calls_73.get(dict_state, None) is None:
                    print(f"init calls 73 dictionary for {dict_state}")
                    calls_73[dict_state] = {}
                # if we are transmitting then there must be a dx call set so let's
                # add it to the list of tried calls
                if data["transmitting"]:
                    calls_tried[dict_state][data["dx_call"]] = True
                await state_update_queue.put((copy.copy(state), None))
            elif data["type"] == StateMachineMessageType.DECODE:
                #print(f"received decode message: {data}")
                # skip if replay
                if not data["new"]:
                    continue
                # increment counters for freq and mode based decodes
                dict_state = (state.dial_freq, state.mode)
                curr = state.decodes.get(dict_state, 0)
                state.decodes[dict_state] = curr + 1
                # skip low confidence or off air
                if data["low_conf"] or data["off_air"]:
                    curr = state.lc_or_oa_decodes.get(dict_state, 0)
                    state.lc_or_oa_decodes[dict_state] = curr + 1
                    continue
                # if the system is still getting state skip
                if state.mode is None or state.dial_freq is None:
                    continue
                # make sure the mode matches
                # if data['mode'] != state.mode:
                #    print(f"{__file__}:{__name__} : mode mismatch between known current state and decode: {data}")
                #    continue
                # mode is frequently ~
                # make sure it is a cq
                if not data["message"].startswith("CQ") or data["message"].startswith(
                    "CQ DX"
                ):
                    #print(f"culled for message: {data['message']}")
                    continue
                # make sure it isn't someone we have worked before
                # extract call
                tokens = data["message"].split()
                if len(tokens) >= 3:
                    if len(tokens) == 4 and \
                            ( tokens[1].casefold() == "POTA".casefold() or len(tokens[1]) < 4 ):
                        call = tokens[2]
                    else:
                        call = tokens[1]
                    if calls_tried[dict_state].get(call, False) or \
                            calls_73[dict_state].get(call, False):
                        #print("culled for previous message")
                        continue
                elif len(tokens) == 2:
                    # skip missing grid
                    continue
                else:
                    # malformed CQ message
                    print(f"{__file__}:{__name__} : malformed CQ message: {data}")
                    continue
                # apply snr threshold
                if data["snr"] < state.snr_threshold:
                    #print(f"culled for snr: {data['snr']}")
                    continue
                # apply delta time threshold
                if abs(float(data["delta_time"])) > abs(state.delta_time_threshold):
                    #print(f"culled for delta time: {data['delta_time']}")
                    continue
                # compare against current canidate
                if canidate is not None:
                    cdiff = datetime.now() - canidate["last"]
                    if (
                        cdiff.total_seconds() < state.max_cq_decode_age
                        and canidate["snr"] > data["snr"]
                    ):
                        #print("culled for being less than previous valid canidate")
                        continue
                data["last"] = datetime.now()
                canidate = data.copy()
                await state_update_queue.put((copy.copy(state), canidate))
            elif data["type"] == StateMachineMessageType.QSO_LOGGED:
                # make sure the mode matches
                if data["mode"] != state.mode:
                    print(
                        f"{__file__}:{__name__} : mode mismatch between known current state and decode: {data}"
                    )
                    continue
                dict_state = (state.dial_freq, state.mode)
                # remove from old dict, if there
                calls_tried[dict_state][data["call"]] = False
                # add to new dict
                calls_73[dict_state][data["call"]] = True
            elif data["type"] == StateMachineMessageType.SOCKET_INFO:
                state.sock = data["sock"]
                state.addr = data["addr"]
            else:
                print(
                    f"{__file__}:{__name__} : unexpected state machine message: {data}"
                )
        print(f"{__file__}:{__name__} : processed message {data}")
    except asyncio.CancelledError:
        print("state machine task cancelled")
    except Exception as e:
        print(f"state machine task exception occurred:\n{type(e)} : {e}")
        traceback.print_exc()


async def start_background_tasks(app):
    state_machine_queue = asyncio.Queue()
    state_update_queue = asyncio.Queue()
    app["udp_listener"] = asyncio.create_task(
        listen_WSJTX_multicast(state_machine_queue)
    )
    app["state_machine"] = asyncio.create_task(
        state_machine_task(state_machine_queue, state_update_queue)
    )
    app["heartbeat"] = asyncio.create_task(heartbeat_task(state_update_queue))


async def cleanup_background_tasks(app):
    app["heartbeat"].cancel()
    await app["heartbeat"]
    app["udp_listener"].cancel()
    await app["udp_listener"]
    app["state_machine"].cancel()
    await app["state_machine"]


# Register the startup and cleanup signals
app.on_startup.append(start_background_tasks)
app.on_cleanup.append(cleanup_background_tasks)

if __name__ == "__main__":
    web.run_app(app, port=5000)
