import socket
import threading
 
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(('localhost', 5000))
 
name = input("Enter your name: ")
client.send(name.encode())
 
def receive():
    while True:
        try:
            msg = client.recv(1024).decode()
            print(msg)
        except:
            break
 

thread = threading.Thread(target=receive)
thread.daemon = True
thread.start()
 

while True:
    msg = input()
    client.send(msg.encode())
 