import socket

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('localhost', 5555))
server.listen()

conn, addr = server.accept()

while True:
    data = conn.recv(1024).decode()

    if data.startswith("FILE: "):
        # recieve the file
        _, filename, size = data.split(":")
        file_data = conn.recv(int(size))

        with open("received_" + filename, "wb") as f:
            f.write(file_data)

        conn.send("File received successfully".encode())

    else:
        print("Client: ", data)
        reply = input("Your reply: ")
        conn.send(reply.encode())

conn.close()