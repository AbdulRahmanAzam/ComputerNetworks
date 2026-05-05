import socket
import threading
 
ALLOWED_EXTENSIONS = ['.txt', '.jpg', '.pdf', '.png']
BANNED_WORDS = ['spam', 'hate', 'abuse', 'badword']
 
clients = {}
 
def is_file_allowed(filename):
    for ext in ALLOWED_EXTENSIONS:
        if filename.endswith(ext):
            return True
    return False
 
def has_banned_word(message):
    for word in BANNED_WORDS:
        if word in message.lower():
            return True
    return False
 
def broadcast(msg, sender):
    for client in clients:
        if client != sender:
            client.send(msg.encode())
 
def handle_client(conn, addr):
    name = conn.recv(1024).decode()
    clients[conn] = name
    print(f"{name} joined")
    broadcast(f"{name} joined the chat", conn)
 
    while True:
        try:
            msg = conn.recv(4096).decode()
            if not msg:
                break
 
            if msg.startswith("FILE:"):
                parts = msg.split(":", 2)
                filename = parts[1]
                size = int(parts[2])
 
                file_data = b""
                while len(file_data) < size:
                    file_data += conn.recv(4096)
 
                if is_file_allowed(filename):
                    with open("server_" + filename, "wb") as f:
                        f.write(file_data)
                    print(f"{name} sent {filename}")
                    broadcast(f"{name} shared a file: {filename}", conn)
                    conn.send("File sent!".encode())
                else:
                    print(f"{name} tried to send {filename} - blocked")
                    conn.send(f"File rejected. Allowed types: {ALLOWED_EXTENSIONS}".encode())
 
            else:
                if has_banned_word(msg):
                    print(f"{name} used a banned word")
                    conn.send("Message blocked: inappropriate content.".encode())
                else:
                    print(f"{name}: {msg}")
                    broadcast(f"{name}: {msg}", conn)
 
        except:
            break
 
    del clients[conn]
    broadcast(f"{name} left the chat", conn)
    conn.close()
    print(f"{name} disconnected")
 
 
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('localhost', 5000))
server.listen(5)
print("Server running on port 5000")
 
while True:
    conn, addr = server.accept()
    thread = threading.Thread(target=handle_client, args=(conn, addr))
    thread.start()