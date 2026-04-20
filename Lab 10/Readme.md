Solution of Tasks are in Task1.md and Task3.md

Task 2 is mentioned below in this readme.md only

# Task 2:

200.16.100.0/24
Development : 32 hosts
Finance: 27 hosts
HR: 10 hosts

for the largest network, we must atleast have 32 hosts

#### assignable hosts according to bits:
5 bits => 2^5 - 2 = 30 hosts (this is less)
6 bits => 2^6 - 2 = 62 hosts (this is perfect)

#### bits to borrow: 
2^2 > 3. => 4 subnets,  meaning 2 bits will be borrowed

#### new subnet mask
/24 + 2 = /26

#### Development: 
Network: 200.16.100.0
Range: 1-62
Broadcast: 63

#### Finance:
Network: 200.16.100.64
Range: 65-126
Broadcast: 127

#### HR:
Network: 200.16.100.128
Range: 129-190
Broadcast: 191


<img width="658" height="743" alt="image" src="https://github.com/user-attachments/assets/770ddcb2-c518-4f4a-a096-cab4640316f9" />
