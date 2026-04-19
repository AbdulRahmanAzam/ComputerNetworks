# TCP Congestion control simulator - NewReno variant
import math

class TCPNewReno:
    def __init__(self):
        self.cwnd = 1  # congestion window in MSS units
        self.ssthresh = 32  # slow start threshold
        self.state = "slow_start"  # slow_start or congestion_avoidance
        self.ack_count = 0

    def on_ack(self):
        # increase cwnd
        if self.state == "slow_start":
            self.cwnd += 1
            if self.cwnd >= self.ssthresh:
                self.state = "congestion_avoidance"
        else:
            self.ack_count += 1
            if self.ack_count >= self.cwnd:
                self.cwnd += 1
                self.ack_count = 0

    def on_loss(self):
        # congestion detected
        self.ssthresh = max(self.cwnd // 2, 2)
        self.cwnd = 1
        self.state = "slow_start"
        self.ack_count = 0

    def get_cwnd_bytes(self):
        # MSS = 1448 bytes (typical)
        return self.cwnd * 1448

# simulate TCP for 20 seconds
tcp = TCPNewReno()
time_step = 0.1  # 100ms intervals
output = []

for t in [i * time_step for i in range(1, 201)]:
    # simulate loss event at t=10s and t=15s
    if math.isclose(t, 10.0, abs_tol=0.05) or math.isclose(t, 15.0, abs_tol=0.05):
        tcp.on_loss()
    else:
        # normal ACK received
        tcp.on_ack()
    
    cwnd_bytes = tcp.get_cwnd_bytes()
    output.append(f"{t:.1f}\t{cwnd_bytes}")

# write to file
with open("cwnd.txt", "w") as f:
    f.write("\n".join(output))

print("Simulation complete. Output saved to cwnd.txt")
print(f"Data points: {len(output)}")
