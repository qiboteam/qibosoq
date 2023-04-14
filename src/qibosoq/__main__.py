"""Main qibosoq program, starts the server"""

from qibosoq.rfsoc_server import serve

HOST = "192.168.0.81"  # Server address
PORT = 6000  # Port to listen on

serve(HOST, PORT)
