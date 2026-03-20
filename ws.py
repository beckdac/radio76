"""
Monitors WSJTX UDP Multicast and shares the data via a websocket.

Includes a sample `index.html` that displays the data. Filters
canidate next calls and manages a state machine / model.
"""

import asyncio
from datetime import datetime
from enum import Enum
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

    loop = asyncio.get_event_loop()
    try:
        while True:
            # Receive data asynchronously
            data, addr = await loop.run_in_executor(None, sock.recvfrom, 4096)

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
    data = {}
    try:
        while True:
            await asyncio.sleep(2)  # Run every 2 seconds
            now = datetime.now()
            data["time"] = now.strftime("%Y-%m-%d %H:%M:%S")
            # TODO: purge the state update queue and apply the state to the
            # local state copy and send it in the heartbeat
            # count of initiatied calls in list
            # count of completed calls in list
            await sio.emit("gateway_heartbeat", data)
    except asyncio.CancelledError:
        print("Heartbeat task cancelled")


async def state_machine_task(state_machine_queue, state_update_queue):
    """
    Models / manages the state of the system by observing messages

    Can send a call request if setting is turned on.  Will filter
    messages and identify canidate best calls.
    """
    print("State machine task starting")
    state = {
        "busy": True,
        "dial_freq": None,
        "mode": None,
        "lc_or_oa_decodes": {},
        "decodes": {},
        "snr_threshold": -10,
        "delta_time_threshold": 1.0,
        "max_cq_decode_age": 20,
    }
    calls_tried = {}
    calls_73 = {}
    canidate = None
    # TODO: get current best canidate and add that
    # get current state (cts, rts, busy) and add that
    try:
        while True:
            data = await state_machine_queue.get()
            #print(f"message received: {data}")
            if data["type"] == StateMachineMessageType.STATUS:
                #print("looking at status message")
                reset = False
                if not data["tx_enabled"] and not data["transmitting"]:
                    state["busy"] = False
                else:
                    state["busy"] = True
                if state["dial_freq"] != data["dial_freq"]:
                    print("frequency change detected")
                    reset = True
                if state["mode"] != data["mode"]:
                    print("mode change detected")
                    reset = True
                if reset:
                    print("resetting for dial or mode change")
                    canidate = None
                    state["mode"] = data["mode"]
                    state["dial_freq"] = data["dial_freq"]
                # if we need new dictionaries of examined calls, set them up now
                dict_state = (state["dial_freq"], state["mode"])
                if calls_tried.get(dict_state, None) is None:
                    calls_tried[dict_state] = {}
                if calls_73.get(dict_state, None) is None:
                    calls_73[dict_state] = {}
                # if we are transmitting then there must be a dx call set so let's
                # add it to the list of tried calls
                if data["transmitting"]:
                    calls_tried[dict_state][data["dx_call"]] = True
            elif data["type"] == StateMachineMessageType.DECODE:
                #print(f"received decode message: {data}")
                # skip if replay
                if not data["new"]:
                    continue
                # increment counters for freq and mode based decodes
                dict_state = (state["dial_freq"], state["mode"])
                curr = state["decodes"].get(dict_state, 0)
                state["decodes"][dict_state] = curr + 1
                # skip low confidence or off air
                if data["low_conf"] or data["off_air"]:
                    curr = state["lc_or_oa_decodes"].get(dict_state, 0)
                    state["lc_or_oa_decodes"][dict_state] = curr + 1
                    continue
                # make sure the mode matches
                # if data['mode'] != state['mode']:
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
                else:
                    # malformed CQ message
                    print(f"{__file__}:{__name__} : malformed CQ message: {data}")
                    continue
                # apply snr threshold
                if data["snr"] < state["snr_threshold"]:
                    #print(f"culled for snr: {data['snr']}")
                    continue
                # apply delta time threshold
                if abs(float(data["delta_time"])) > abs(state["delta_time_threshold"]):
                    #print(f"culled for delta time: {data['delta_time']}")
                    continue
                # compare against current canidate
                if canidate is not None:
                    cdiff = datetime.now() - canidate["last"]
                    if (
                        cdiff.total_seconds() < state["max_cq_decode_age"]
                        and canidate["snr"] > data["snr"]
                    ):
                        #print("culled for being less than previous valid canidate")
                        continue
                data["last"] = datetime.now()
                canidate = data.copy()
                print(f"new canidate: {canidate}")
            elif data["type"] == StateMachineMessageType.QSO_LOGGED:
                # make sure the mode matches
                if data["mode"] != state["mode"]:
                    print(
                        f"{__file__}:{__name__} : mode mismatch between known current state and decode: {data}"
                    )
                    continue
                dict_state = (state["dial_freq"], state["mode"])
                calls_73[dict_state][data.call] = True
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
