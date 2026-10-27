"""Narrow unprivileged client for the local Wi-Fi manager."""
import json
import socket

SOCKET='/run/machinista-network/control.sock'

def request(action, **values):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(18)
        connection.connect(SOCKET)
        connection.sendall(json.dumps(dict(action=action,**values)).encode()+b'\n')
        data=b''
        while b'\n' not in data:
            part=connection.recv(65536)
            if not part or len(data)>262144:raise OSError('Wi-Fi service unreachable.')
            data+=part
    result=json.loads(data.split(b'\n')[0])
    if 'error' in result:raise ValueError(result['error'])
    return result
