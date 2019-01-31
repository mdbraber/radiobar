#!/usr/bin/env python3
import socket
import sys
import time
import subprocess
import errno
from socket import error as socket_error

HOST = '127.0.0.1'  # The server's hostname or IP address
PORT = 65432        # The port used by the server

def connect(): 
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((HOST, PORT))
        return s
    except socket_error as serr:
        if serr.errno != errno.ECONNREFUSED: 
            raise serr
        subprocess.Popen(["open","/Applications/RadioBar.app"])
        time.sleep(5)
        return connect()
    
try:
    s = connect()
    s.sendall(bytes(sys.argv[1],'utf-8'))
    data = s.recv(1024)
    print(data.decode('utf-8'))
except socket_error as serr:
    print(serr)
    sys.exit(1)
