import socket
import os

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(("localhost", 5555))
print("connected to the server")


while True:
    msg = input("Enter a command")

    if msg.startswith("send "):
        # send the file
        filename = msg.split(" ")[1]
        file_data = open(filename, "rb").read()
        header = f"FILE:{filename}:{len(file_data)}"
        client.send(header.encode())
        client.send(file_data)

        reply = client.recv(1024).decode()
        print("server reply: ", reply)

    else:
        # send the message
        client.send(msg.encode())
        reply = client.recv(1024).decode()
        print("server reply: ", reply)

client.close()
