import asyncio
import os
import sys
import pywsjtx.extra.simple_server

import re
import random

TEST_MULTICAST = True

if TEST_MULTICAST:
    IP_ADDRESS = '224.0.0.1'
    PORT = 2237
else:
    IP_ADDRESS = '127.0.0.1'
    PORT = 2237

MY_MAX_SCHEMA = 3


class WSJTXServerProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport
        print("Server started, listening for UDP packets...")

    def datagram_received(self, data, addr):
        pkt = data
        addr_port = addr
        #message = data.decode()
        #print(f"Received {message} from {addr}")

        if (pkt != None):
            the_packet = pywsjtx.WSJTXPacketClassFactory.from_udp_packet(addr_port, pkt)

        if type(the_packet) == pywsjtx.HeartBeatPacket:
            max_schema = max(the_packet.max_schema, MY_MAX_SCHEMA)
            reply_beat_packet = pywsjtx.HeartBeatPacket.Builder(the_packet.wsjtx_id,max_schema)
            self.transport.sendto(reply_beat_packet, addr_port)
        if type(the_packet) == pywsjtx.DecodePacket:
            m = re.match(r"^CQ\s+(\S+)\s+", the_packet.message)
            if m:
                print("Callsign {}".format(m.group(1)))
                callsign = m.group(1)

                color_pkt = pywsjtx.HighlightCallsignPacket.Builder(the_packet.wsjtx_id, callsign,

                                                                    pywsjtx.QCOLOR.White(),
                                                                    pywsjtx.QCOLOR.Red(),
                                                                    True)

                normal_pkt = pywsjtx.HighlightCallsignPacket.Builder(the_packet.wsjtx_id, callsign,
                                                                    pywsjtx.QCOLOR.Uncolor(),
                                                                    pywsjtx.QCOLOR.Uncolor(),
                                                                    True)
                self.transport.sendto(color_pkt, addr_port)
                #print(pywsjtx.PacketUtil.hexdump(color_pkt))
        print(the_packet)


async def main():
    loop = asyncio.get_running_loop()

    # create the UDP endpoint
    transport, protocol = await loop.create_datagram_endpoint(
            lambda: WSJTXServerProtocol(),
            local_addr=(IP_ADDRESS, PORT)
    )

    try:
        await asyncio.sleep(3600) # run for 1 hour
    finally:
        transport.close()


if __name__ == '__main__':
    asyncio.run(main())
