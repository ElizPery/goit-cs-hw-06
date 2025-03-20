from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
from time import sleep
import datetime

import pathlib
import mimetypes

from multiprocessing import Process
import socket
import threading

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

uri = "mongodb://mongodb:27017"

HTTPServer_Port = 3000
UDP_IP = '127.0.0.1'
UDP_PORT = 5000

def send_data_to_socket(data):
    with socket.socket() as s:
        while True:
            try:
                s.connect((UDP_IP, UDP_PORT))
                s.sendall(data)
                break
            except ConnectionRefusedError:
                sleep(0.5)

class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        pr_url = urllib.parse.urlparse(self.path)
        if pr_url.path == '/':
            self.send_html_file('index.html')
        elif pr_url.path == '/message':
            self.send_html_file('message.html')
        else:
            if pathlib.Path().joinpath(pr_url.path[1:]).exists():
                self.send_static()
            else:
                self.send_html_file('error.html', 404)

    def do_POST(self):
        data = self.rfile.read(int(self.headers['Content-Length']))
        send_data_to_socket(data)
        self.send_response(302)
        self.send_header('Location', '/')
        self.end_headers()


    def send_html_file(self, filename, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        with open(filename, 'rb') as fd:
            self.wfile.write(fd.read())

    def send_static(self):
        self.send_response(200)
        mt = mimetypes.guess_type(self.path)
        if mt:
            self.send_header("Content-type", mt[0])
        else:
            self.send_header("Content-type", 'text/plain')
        self.end_headers()
        with open(f'.{self.path}', 'rb') as file:
            self.wfile.write(file.read())

def run_http_server(server_class=HTTPServer, handler_class=HttpHandler):
    server_address = ('', HTTPServer_Port)
    http = server_class(server_address, handler_class)
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        http.server_close()

def save_data(data):
    client = MongoClient(uri, server_api=ServerApi("1"))
    db = client.book
    modified_data = data.copy()
    modified_data["date"] = datetime.now()

    db.messages.insert_one(modified_data)

def run_socket_server(ip, port):
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((ip, port))
        s.listen(1)
        conn, addr = s.accept()
        print(f"Connected by {addr}")
        with conn:
            while True:
                data = conn.recv(1024)
                data_parse = urllib.parse.unquote_plus(data.decode())
                data_dict = {key: value for key, value in [el.split('=') for el in data_parse.split('&')]}
                print(f'From client: {data_dict}')
                save_data(data_dict)
                if not data:
                    break

if __name__ == '__main__':
    http_server_process = Process(target=run_http_server)
    http_server_process.start()
    http_server_process.join()

    socket_server_process = Process(target=run_socket_server, args=(UDP_IP, UDP_PORT))
    socket_server_process.start()
    socket_server_process.join()

    client = threading.Thread(target=send_data_to_socket)
    client.start()
    client.join()