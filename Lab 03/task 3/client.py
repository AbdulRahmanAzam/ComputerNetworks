import socket
import threading
import os
 
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(('localhost', 5000))
 
name = input("Enter your name: ")
client.send(name.encode())
 
def receive():
    while True:
        try:
            msg = client.recv(4096).decode()
            print(msg)
        except:
            break
 
thread = threading.Thread(target=receive)
thread.daemon = True
thread.start()
 
print("Type a message or 'send <filename>' to send a file\n")
 
while True:
    msg = input()
 
    if msg.startswith("send "):
        filename = msg.split(" ", 1)[1]
 
        if not os.path.exists(filename):
            print("File not found")
            continue
 
        file_data = open(filename, "rb").read()
        client.send(f"FILE:{filename}:{len(file_data)}".encode())
        client.send(file_data)
 
    else:
        client.send(msg.encode())