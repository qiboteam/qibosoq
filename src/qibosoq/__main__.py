from socketserver import TCPServer

from qick import QickSoc

from qibosoq.rfsoc_server import MyTCPHandler

HOST = "192.168.0.72"  # Server address
PORT = 6000  # Port to listen on

TCPServer.allow_reuse_address = True
with TCPServer((HOST, PORT), MyTCPHandler) as server:
    print("Server Listening")

    server.serve_forever()
