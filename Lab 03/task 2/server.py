import socket
import threading
 
clients = []
 
def handle_client(conn, addr):
    name = conn.recv(1024).decode()
    print(f"{name} joined from {addr}")
    broadcast(f"{name} has joined the chat!", conn)
 
    while True:
        try:
            msg = conn.recv(1024).decode()
            if not msg:
                break
            print(f"{name}: {msg}")
            broadcast(f"{name}: {msg}", conn)
        except:
            break
 

    clients.remove(conn)
    broadcast(f"{name} has left the chat.", conn)
    conn.close()
 
def broadcast(msg, sender):
    """Send message to everyone except the sender."""
    for client in clients:
        if client != sender:
            client.send(msg.encode())
 

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('localhost', 5000))
server.listen(5)
print("Server started on port 5000. Waiting for clients...")
 
while True:
    conn, addr = server.accept()
    clients.append(conn)

    # Each client own thread
    thread = threading.Thread(target=handle_client, args=(conn, addr))
    thread.start()
    print(f"Active clients: {len(clients)}")
 