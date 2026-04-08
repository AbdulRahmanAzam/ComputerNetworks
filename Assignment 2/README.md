# DNS Lookup Simulator - CN Assignment 2

# Demo Video:
www.youtube.com/watch?v=v3wnFQOtUHY

## How to Run

### Prerequisites
Make sure you have Python 3.7+ installed. The application uses:
- `socket` - for DNS A record lookups (built-in)
- `dnspython` - for full DNS record lookup (NS, MX, CNAME)

### Installation & Execution

**Step 1:** Open PowerShell/Terminal and navigate to the project folder:
```powershell
cd "C:\Users\azama\VS Code\PROJECTS\01 Academic and Tutorial Projects\CN Assignment 2"
```

**Step 2:** Run the DNS simulator:
```bash
python dns_simulator.py
```

Or if you need to specify Python 3.14:
```bash
C:/Users/azama/.local/bin/python3.14.exe dns_simulator.py
```

### Interactive Menu Options

Once the app starts, you'll see this menu:

```
 ┌────────────────── MENU ──────────────────┐
 │  1. Iterative DNS Lookup                 │
 │  2. Recursive DNS Lookup                 │
 │  3. Show Cache Contents                  │
 │  4. Flush DNS Cache                      │
 │  5. Demo: Caching Benefit (Recursive)    │
 │  6. Demo: Auto-Flush when Cache is Full  │
 │  7. Batch Lookup (multiple domains)      │
 │  0. Exit                                 │
 └──────────────────────────────────────────┘
```

### Menu Options Explained

| Option | Description | Demo Purpose |
|--------|-------------|--------------|
| **1** | Iterative DNS Lookup | Shows how local DNS server queries Root → TLD → Authoritative in sequence |
| **2** | Recursive DNS Lookup | Shows how Root queries TLD, TLD queries Auth, answers bubble back |
| **3** | Show Cache Contents | Display what domains are currently cached with TTL remaining |
| **4** | Flush DNS Cache | Clear all cached entries (forces full resolution next time) |
| **5** | Caching Benefit Demo | Query same domain twice — 1st miss (slow), 2nd hit (instant from cache) |
| **6** | Auto-Flush Demo | Adds 7+ domains to cache — watch older entries auto-evicted when full |
| **7** | Batch Lookup | Lookup multiple domains at once (comma-separated) |
| **0** | Exit | Quit the program |

## Example Demo Session

### Option 1: Iterative Lookup for google.com

Enter choice: **1**
Domain: **google.com**

Output shows:
- Step 1: Client queries Local DNS
- Step 2: Local DNS → Root DNS Server (referral to .com TLD)
- Step 3: Local DNS → TLD DNS Server (.com, referral to ns1.google.com)
- Step 4: Local DNS → Authoritative Server (ns1.google.com)
- Step 5-8: Answer propagates back
- Results cached with 300s TTL

```
DNS INFORMATION for google.com:
A   : 142.250.202.142
NS  : ns3.google.com., ns2.google.com., ns1.google.com., ns4.google.com.
MX  : 10 smtp.google.com.
```

### Option 5: Caching Benefit Demo

First lookup: **4.2345s** (full resolution traversal)
Second lookup: **0.0012s** (from cache)

**Speedup: 3500x faster!**

### Option 6: Auto-Flush Demo

Cache max size: 5

Lookups:
1. google.com → cached
2. facebook.com → cached
3. github.com → cached
4. amazon.com → cached
5. microsoft.com → cached (cache full)
6. reddit.com → [AUTO-FLUSH] evicted 'google.com' (oldest)
7. youtube.com → [AUTO-FLUSH] evicted 'facebook.com' (oldest)

Shows LRU (Least Recently Used) eviction working.

## Key Features Demonstrated

✅ **DNS Message Format**
- 16-bit identification field
- 16-bit flags field (QR, AA, RD, RA bits)
- Raw hex header display

✅ **Server Hierarchy**
- Root DNS Server (knows all TLD servers)
- TLD DNS Server (knows authoritative servers)
- Authoritative DNS Server (has actual records)
- Local DNS Server (recursive resolver with caching)

✅ **Resolution Types**
- **Iterative**: Local DNS server contacts each level sequentially
- **Recursive**: Each server queries the next, answers bubble back

✅ **Caching with Auto-Flush**
- LRU (Least Recently Used) cache
- Stores DNS records with 300s TTL
- Auto-evicts oldest entry when cache exceeds max_size=5

✅ **Real DNS Records**
- A records (IPv4 addresses)
- NS records (nameservers)
- MX records (mail servers)
- CNAME records (aliases)

## Running Tests

To verify all features work correctly:

```bash
python test_dns.py
```

Expected output:
```
TEST RESULTS: 26 passed, 0 failed out of 26
ALL TESTS PASSED!
```

## File Structure

```
CN Assignment 2/
├── dns_simulator.py       # Main application
├── test_dns.py            # Automated test suite
└── README.md              # This file
```

## Technical Details

### DNS Message Structure
```
Header (12 bytes):
- Identification (2 bytes)    : Unique 16-bit query ID
- Flags (2 bytes)             : Query/Response, AA, RD, RA bits
- Question Count (2 bytes)    : Number of questions
- Answer Count (2 bytes)      : Number of answers
- Authority Count (2 bytes)   : Number of authority records
- Additional Count (2 bytes)  : Number of additional records
```

### Cache Implementation
```python
DNSCache(max_size=5):
- Stores (domain) → (records_dict, timestamp, ttl)
- OrderedDict for LRU tracking
- Auto-evicts oldest on overflow
- TTL-based expiry checking
- Hit/miss statistics
```

### DNS Record Database
```
ROOT SERVER knows:
  .com → TLD-COM-SERVER (a.gtld-servers.net)
  .org → TLD-ORG-SERVER (a0.org.afilias-nst.info)
  .net, .edu, .io, .gov, .pk, .uk ...

TLD SERVERS know:
  google.com → ns1.google.com
  facebook.com → a.ns.facebook.com
  github.com → dns1.p08.nsone.net
  ... (15 popular domains)

AUTHORITATIVE SERVERS have:
  Real A, NS, MX, CNAME records via dnspython
```

## Troubleshooting

**"ModuleNotFoundError: No module named 'dns'"**
→ Install dnspython:
```bash
pip install dnspython
```

**"Name resolution failed"**
→ Check internet connection (app queries real DNS system)

**Cache not showing records?**
→ Choose option 5 or 6 to populate cache first

## Student Info

Fill in your details at the top of `dns_simulator.py`:

```python
"""
Student: [YOUR NAME]  |  ID: [YOUR ID]  |  Section: [YOUR SECTION]
"""
```

---

**Demo Ready!** You can now run this application and demonstrate all DNS features for your viva.
