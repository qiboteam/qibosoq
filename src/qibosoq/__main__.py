"""Main qibosoq program, starts the server"""

import os
import signal
from socketserver import TCPServer

from qick import QickSoc

from qibosoq.rfsoc_server import MyTCPHandler, signal_handler


def serve(host, port):
    # starts handler for system interruption (ex. Ctrl-C)
    signal.signal(signal.SIGINT, signal_handler)
    TCPServer.allow_reuse_address = True
    with TCPServer((host, port), MyTCPHandler) as server:
        print(f"Server Listening, PID {os.getpid()}")
        server.serve_forever()


HOST = "192.168.0.72"  # Server address
PORT = 6000  # Port to listen on

serve(HOST, PORT)
