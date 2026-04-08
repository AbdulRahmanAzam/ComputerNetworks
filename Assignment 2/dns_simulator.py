"""
DNS Lookup Simulator - CN Assignment 2
=======================================
Simulates DNS name resolution with Root, TLD, and Authoritative servers.
Demonstrates iterative & recursive resolution, DNS message format,
caching with auto-flush, and real DNS record retrieval.

Student: [YOUR NAME]  |  ID: [YOUR ID]  |  Section: [YOUR SECTION]
"""

import struct
import socket
import random
import time
import os
from collections import OrderedDict
from datetime import datetime

# ─────────────────────────────────────────────────────────────
#  DNS Message Format (RFC 1035 simplified)
# ─────────────────────────────────────────────────────────────

class DNSMessage:
    """
    Represents a DNS protocol message with:
    - 16-bit identification field
    - 16-bit flags field (QR, Opcode, AA, TC, RD, RA, RCODE)
    """
    # Flag bit masks
    QR_RESPONSE = 0x8000     # 1 = response, 0 = query
    AA_FLAG     = 0x0400     # Authoritative Answer
    RD_FLAG     = 0x0100     # Recursion Desired
    RA_FLAG     = 0x0080     # Recursion Available

    def __init__(self, query_name, record_type="A", is_response=False, msg_id=None):
        self.identification = msg_id if msg_id is not None else random.randint(0, 0xFFFF)
        self.flags = 0
        if is_response:
            self.flags |= self.QR_RESPONSE
        self.flags |= self.RD_FLAG  # recursion desired by default
        self.query_name = query_name
        self.record_type = record_type
        self.answers = []
        self.authority = []
        self.additional = []

    def set_authoritative(self):
        self.flags |= self.AA_FLAG

    def set_recursion_available(self):
        self.flags |= self.RA_FLAG

    def make_response(self):
        resp = DNSMessage(self.query_name, self.record_type, is_response=True, msg_id=self.identification)
        resp.flags |= self.RA_FLAG
        return resp

    def pack_header(self):
        """Pack the 12-byte DNS header."""
        qdcount = 1
        ancount = len(self.answers)
        nscount = len(self.authority)
        arcount = len(self.additional)
        return struct.pack("!HHHHHH",
                           self.identification,
                           self.flags,
                           qdcount, ancount, nscount, arcount)

    def header_hex(self):
        hdr = self.pack_header()
        return " ".join(f"{b:02X}" for b in hdr)

    def display(self, label="DNS Message"):
        is_resp = "Response" if (self.flags & self.QR_RESPONSE) else "Query"
        aa = "Yes" if (self.flags & self.AA_FLAG) else "No"
        rd = "Yes" if (self.flags & self.RD_FLAG) else "No"
        ra = "Yes" if (self.flags & self.RA_FLAG) else "No"

        print(f"\n{'=' * 60}")
        print(f"  {label}")
        print(f"{'=' * 60}")
        print(f"  Identification : 0x{self.identification:04X} ({self.identification})")
        print(f"  Flags          : 0x{self.flags:04X}")
        print(f"    QR (type)    : {is_resp}")
        print(f"    AA (auth)    : {aa}")
        print(f"    RD (rec-des) : {rd}")
        print(f"    RA (rec-avl) : {ra}")
        print(f"  Question       : {self.query_name} (type {self.record_type})")
        print(f"  Answers        : {len(self.answers)}")
        print(f"  Authority      : {len(self.authority)}")
        print(f"  Additional     : {len(self.additional)}")
        print(f"  Raw Header Hex : {self.header_hex()}")
        print(f"{'=' * 60}")


# ─────────────────────────────────────────────────────────────
#  DNS Cache with Auto-Flush
# ─────────────────────────────────────────────────────────────

class DNSCache:
    """LRU cache for DNS records with configurable max size and TTL-based auto-flush."""

    def __init__(self, max_size=5):
        self.max_size = max_size
        self.cache = OrderedDict()  # key -> (records_dict, timestamp, ttl)
        self.hits = 0
        self.misses = 0

    def get(self, domain):
        if domain in self.cache:
            records, ts, ttl = self.cache[domain]
            age = time.time() - ts
            if age < ttl:
                self.cache.move_to_end(domain)
                self.hits += 1
                return records, int(ttl - age)
            else:
                del self.cache[domain]
        self.misses += 1
        return None, 0

    def put(self, domain, records, ttl=300):
        if domain in self.cache:
            self.cache.move_to_end(domain)
        elif len(self.cache) >= self.max_size:
            evicted_key, _ = self.cache.popitem(last=False)
            print(f"  [CACHE] Auto-flush: evicted '{evicted_key}' (cache full, max={self.max_size})")
        self.cache[domain] = (records, time.time(), ttl)

    def display(self):
        print(f"\n{'-' * 60}")
        print(f"  LOCAL DNS CACHE  (size {len(self.cache)}/{self.max_size}  |  hits={self.hits}  misses={self.misses})")
        print(f"{'-' * 60}")
        if not self.cache:
            print("  (empty)")
        for domain, (records, ts, ttl) in self.cache.items():
            remaining = max(0, int(ttl - (time.time() - ts)))
            cached_at = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            print(f"  {domain:30s}  cached={cached_at}  TTL={remaining}s")
        print(f"{'-' * 60}")

    def flush_all(self):
        count = len(self.cache)
        self.cache.clear()
        print(f"  [CACHE] Flushed all {count} entries.")


# ─────────────────────────────────────────────────────────────
#  Actual DNS Record Lookup (using socket / low-level)
# ─────────────────────────────────────────────────────────────

def real_dns_lookup(domain):
    """Perform actual DNS lookups using socket for A records and
    build a comprehensive record dictionary."""
    records = {"A": [], "NS": [], "MX": [], "CNAME": []}

    # --- A records via socket ---
    try:
        results = socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM)
        seen = set()
        for res in results:
            ip = res[4][0]
            if ip not in seen:
                seen.add(ip)
                records["A"].append(ip)
    except socket.gaierror:
        pass

    return records


def real_dns_lookup_full(domain):
    """Full DNS lookup using dnspython if available, fallback to socket."""
    records = {"A": [], "NS": [], "MX": [], "CNAME": []}

    try:
        import dns.resolver

        # A records
        try:
            answers = dns.resolver.resolve(domain, "A")
            records["A"] = [r.to_text() for r in answers]
        except Exception:
            pass

        # NS records
        try:
            answers = dns.resolver.resolve(domain, "NS")
            records["NS"] = [r.to_text() for r in answers]
        except Exception:
            pass

        # MX records
        try:
            answers = dns.resolver.resolve(domain, "MX")
            records["MX"] = [r.to_text() for r in answers]
        except Exception:
            pass

        # CNAME records
        try:
            answers = dns.resolver.resolve(domain, "CNAME")
            records["CNAME"] = [r.to_text() for r in answers]
        except Exception:
            pass

    except ImportError:
        # Fallback: socket-only for A records
        records = real_dns_lookup(domain)

    return records


# ─────────────────────────────────────────────────────────────
#  DNS Server Hierarchy Simulation
# ─────────────────────────────────────────────────────────────

# Known TLD -> root hint mapping
ROOT_SERVER_DB = {
    "com": "TLD-COM-SERVER (a.gtld-servers.net)",
    "org": "TLD-ORG-SERVER (a0.org.afilias-nst.info)",
    "net": "TLD-NET-SERVER (a.gtld-servers.net)",
    "edu": "TLD-EDU-SERVER (a.edu-servers.net)",
    "io":  "TLD-IO-SERVER  (ns-a1.io)",
    "gov": "TLD-GOV-SERVER (a.gov-servers.net)",
    "pk":  "TLD-PK-SERVER  (ns.pknic.net.pk)",
    "uk":  "TLD-UK-SERVER  (nsa.nic.uk)",
}

# Well-known authoritative NS for popular domains (used for display)
KNOWN_AUTH_SERVERS = {
    "google.com":    "ns1.google.com",
    "facebook.com":  "a.ns.facebook.com",
    "youtube.com":   "ns1.google.com",
    "amazon.com":    "pdns1.ultradns.net",
    "twitter.com":   "ns1.p34.dynect.net",
    "github.com":    "dns1.p08.nsone.net",
    "wikipedia.org": "ns0.wikimedia.org",
    "reddit.com":    "ns-1029.awsdns-00.org",
    "microsoft.com": "ns1-39.azure-dns.com",
    "apple.com":     "a.ns.apple.com",
}


def get_tld(domain):
    parts = domain.rstrip(".").split(".")
    return parts[-1] if parts else ""


def get_auth_server_name(domain):
    if domain in KNOWN_AUTH_SERVERS:
        return KNOWN_AUTH_SERVERS[domain]
    # For unknown domains, derive from NS records or generate plausible name
    return f"ns1.{domain}"


class RootDNSServer:
    """Simulates a Root DNS Server (e.g., a.root-servers.net)."""
    name = "ROOT DNS SERVER (a.root-servers.net)"

    def query(self, dns_msg):
        tld = get_tld(dns_msg.query_name)
        tld_server = ROOT_SERVER_DB.get(tld, f"TLD-{tld.upper()}-SERVER")
        print(f"  [{self.name}]")
        print(f"    Received query for: {dns_msg.query_name}")
        print(f"    I don't know the answer, but I know the TLD '.{tld}' server.")
        print(f"    Referral -> {tld_server}")
        resp = dns_msg.make_response()
        resp.authority = [f"Referral to {tld_server}"]
        return resp, tld_server


class TLDDNSServer:
    """Simulates a TLD DNS Server (e.g., a.gtld-servers.net for .com)."""
    def __init__(self, tld):
        self.tld = tld
        self.name = ROOT_SERVER_DB.get(tld, f"TLD-{tld.upper()}-SERVER")

    def query(self, dns_msg):
        domain = dns_msg.query_name.rstrip(".")
        auth_ns = get_auth_server_name(domain)
        print(f"  [{self.name}]")
        print(f"    Received query for: {dns_msg.query_name}")
        print(f"    I manage the '.{self.tld}' zone. The authoritative server is:")
        print(f"    Referral -> AUTHORITATIVE SERVER ({auth_ns})")
        resp = dns_msg.make_response()
        resp.authority = [f"Referral to {auth_ns}"]
        return resp, auth_ns


class AuthoritativeDNSServer:
    """Simulates an Authoritative DNS Server (e.g., ns1.google.com)."""
    def __init__(self, auth_ns, domain):
        self.name = f"AUTHORITATIVE SERVER ({auth_ns})"
        self.domain = domain

    def query(self, dns_msg):
        print(f"  [{self.name}]")
        print(f"    Received query for: {dns_msg.query_name}")
        print(f"    I am authoritative for {self.domain}. Looking up records...")

        records = real_dns_lookup_full(dns_msg.query_name)

        resp = dns_msg.make_response()
        resp.set_authoritative()

        if records["A"]:
            resp.answers = records["A"]
            print(f"    Found {len(records['A'])} A record(s)")
        else:
            print(f"    No A records found.")

        return resp, records


class LocalDNSServer:
    """
    Simulates the Local DNS Server (dns.poly.edu in the figure).
    Acts as a recursive resolver with caching.
    """
    def __init__(self, cache_size=5):
        self.name = "LOCAL DNS SERVER (dns.poly.edu)"
        self.cache = DNSCache(max_size=cache_size)
        self.root = RootDNSServer()

    def resolve_iterative(self, domain):
        """Iterative DNS resolution - local server does all the work."""
        print(f"\n{'#' * 60}")
        print(f"  ITERATIVE DNS RESOLUTION")
        print(f"  Domain: {domain}")
        print(f"{'#' * 60}")

        # Step 1: Check cache
        cached, ttl_remaining = self.cache.get(domain)
        if cached:
            print(f"\n  [CACHE HIT] '{domain}' found in cache (TTL remaining: {ttl_remaining}s)")
            print(f"  => Skipping DNS hierarchy traversal!")
            return cached, True  # True = from cache

        print(f"\n  [CACHE MISS] '{domain}' not in cache. Starting resolution...\n")

        # Create DNS query message
        query_msg = DNSMessage(domain, "A")
        query_msg.display(f"Step 1: Client -> Local DNS (Query)")

        # Step 2: Local DNS -> Root DNS
        print(f"\n  >>> Step 2: Local DNS -> Root DNS Server")
        root_query = DNSMessage(domain, "A", msg_id=query_msg.identification)
        root_resp, tld_server = self.root.query(root_query)

        # Step 3: Root DNS -> Local DNS (referral)
        print(f"\n  <<< Step 3: Root DNS -> Local DNS (Referral to TLD)")

        # Step 4: Local DNS -> TLD DNS
        tld = get_tld(domain)
        tld_dns = TLDDNSServer(tld)
        print(f"\n  >>> Step 4: Local DNS -> TLD DNS Server (.{tld})")
        tld_query = DNSMessage(domain, "A", msg_id=query_msg.identification)
        tld_resp, auth_ns = tld_dns.query(tld_query)

        # Step 5: TLD DNS -> Local DNS (referral)
        print(f"\n  <<< Step 5: TLD DNS -> Local DNS (Referral to Authoritative)")

        # Step 6: Local DNS -> Authoritative DNS
        auth_dns = AuthoritativeDNSServer(auth_ns, domain)
        print(f"\n  >>> Step 6: Local DNS -> Authoritative DNS Server")
        auth_query = DNSMessage(domain, "A", msg_id=query_msg.identification)
        auth_resp, records = auth_dns.query(auth_query)

        # Step 7: Authoritative DNS -> Local DNS (answer)
        print(f"\n  <<< Step 7: Authoritative DNS -> Local DNS (Answer)")
        auth_resp.display(f"Step 7: Authoritative Answer")

        # Step 8: Local DNS -> Client (answer)
        print(f"\n  <<< Step 8: Local DNS -> Client (Final Answer)")

        # Cache the result
        self.cache.put(domain, records)
        print(f"  [CACHE] Stored '{domain}' in local cache")

        return records, False

    def resolve_recursive(self, domain):
        """Recursive DNS resolution - each server queries the next."""
        print(f"\n{'#' * 60}")
        print(f"  RECURSIVE DNS RESOLUTION")
        print(f"  Domain: {domain}")
        print(f"{'#' * 60}")

        # Step 1: Check cache
        cached, ttl_remaining = self.cache.get(domain)
        if cached:
            print(f"\n  [CACHE HIT] '{domain}' found in cache (TTL remaining: {ttl_remaining}s)")
            print(f"  => Skipping entire DNS hierarchy traversal!")
            print(f"  => This demonstrates how caching speeds up recursive lookups.")
            return cached, True

        print(f"\n  [CACHE MISS] '{domain}' not in cache. Starting resolution...\n")

        query_msg = DNSMessage(domain, "A")
        query_msg.display(f"Step 1: Client -> Local DNS (Query)")

        # Step 2: Local DNS -> Root DNS
        print(f"\n  >>> Step 2: Local DNS -> Root DNS")
        print(f"    Root receives query and must resolve it completely (recursive).")
        root_query = DNSMessage(domain, "A", msg_id=query_msg.identification)
        _, tld_server = self.root.query(root_query)

        # Step 3: Root DNS -> TLD DNS  (Root forwards to TLD)
        tld = get_tld(domain)
        tld_dns = TLDDNSServer(tld)
        print(f"\n  >>> Step 3: Root DNS -> TLD DNS  (Root forwards query)")
        tld_query = DNSMessage(domain, "A", msg_id=query_msg.identification)
        _, auth_ns = tld_dns.query(tld_query)

        # Step 4: TLD DNS -> Authoritative DNS  (TLD forwards to Auth)
        auth_dns = AuthoritativeDNSServer(auth_ns, domain)
        print(f"\n  >>> Step 4: TLD DNS -> Authoritative DNS (TLD forwards query)")
        auth_query = DNSMessage(domain, "A", msg_id=query_msg.identification)
        auth_resp, records = auth_dns.query(auth_query)

        # Step 5: Authoritative -> TLD (answer bubbles back)
        print(f"\n  <<< Step 5: Authoritative -> TLD DNS (Answer)")

        # Step 6: TLD -> Root (answer bubbles back)
        print(f"\n  <<< Step 6: TLD DNS -> Root DNS (Answer)")

        # Step 7: Root -> Local DNS (answer bubbles back)
        print(f"\n  <<< Step 7: Root DNS -> Local DNS (Answer)")
        auth_resp.display(f"Step 7: Final Answer (via recursive chain)")

        # Step 8: Local DNS -> Client
        print(f"\n  <<< Step 8: Local DNS -> Client (Final Answer)")

        # Cache
        self.cache.put(domain, records)
        print(f"  [CACHE] Stored '{domain}' in local cache")

        return records, False


# ─────────────────────────────────────────────────────────────
#  Display helpers
# ─────────────────────────────────────────────────────────────

def print_dns_records(domain, records, from_cache=False):
    """Pretty-print DNS records similar to assignment sample output."""
    primary_ip = records["A"][0] if records["A"] else "N/A"
    source = " (FROM CACHE)" if from_cache else ""

    print(f"\n{'*' * 60}")
    print(f"  {domain}/{primary_ip}{source}")
    print(f"  -- DNS INFORMATION --")
    if records["A"]:
        print(f"  A   : {', '.join(records['A'])}")
    else:
        print(f"  A   : (no records found)")
    if records.get("NS"):
        print(f"  NS  : {', '.join(records['NS'])}")
    if records.get("MX"):
        print(f"  MX  : {', '.join(records['MX'])}")
    if records.get("CNAME"):
        print(f"  CNAME: {', '.join(records['CNAME'])}")
    print(f"{'*' * 60}")


def print_banner():
    os.system("cls" if os.name == "nt" else "clear")
    print(r"""
 +==============================================================+
 |           DNS LOOKUP SIMULATOR - CN Assignment 2            |
 |                                                             |
 |  Simulates Root, TLD & Authoritative DNS Servers            |
 |  with DNS Message Format, Caching & Auto-Flush              |
 +==============================================================+
    """)


def print_menu():
    print("\n +-------- MENU (Enter choice) --------+")
    print(" | 1. Iterative DNS Lookup             |")
    print(" | 2. Recursive DNS Lookup             |")
    print(" | 3. Show Cache Contents              |")
    print(" | 4. Flush DNS Cache                  |")
    print(" | 5. Demo: Caching Benefit (Recursive)|")
    print(" | 6. Demo: Auto-Flush when Cache Full |")
    print(" | 7. Batch Lookup (multiple domains)  |")
    print(" | 0. Exit                             |")
    print(" +-------------------------------------+")


# ─────────────────────────────────────────────────────────────
#  Demo routines
# ─────────────────────────────────────────────────────────────

def demo_caching_benefit(local_dns):
    """Demonstrate how caching helps recursive lookups."""
    domain = "google.com"
    print(f"\n{'=' * 60}")
    print(f"  DEMO: CACHING BENEFIT FOR RECURSIVE RESOLUTION")
    print(f"{'=' * 60}")

    print(f"\n  --- First Lookup (cache miss, full traversal) ---")
    start = time.time()
    records, from_cache = local_dns.resolve_recursive(domain)
    t1 = time.time() - start
    print_dns_records(domain, records, from_cache)
    print(f"  Time taken: {t1:.4f}s")

    print(f"\n  --- Second Lookup (should hit cache) ---")
    start = time.time()
    records, from_cache = local_dns.resolve_recursive(domain)
    t2 = time.time() - start
    print_dns_records(domain, records, from_cache)
    print(f"  Time taken: {t2:.4f}s")

    print(f"\n  ┌─────────────────────────────────────────┐")
    print(f"  │ CACHING RESULT SUMMARY                  │")
    print(f"  │ First lookup  : {t1:.4f}s (full resolution) │")
    print(f"  │ Second lookup : {t2:.4f}s (from cache)      │")
    if t1 > 0:
        speedup = t1 / max(t2, 0.0001)
        print(f"  │ Speedup       : {speedup:.1f}x faster           │")
    print(f"  └─────────────────────────────────────────┘")


def demo_auto_flush(local_dns):
    """Demonstrate auto-flush when cache exceeds max size."""
    print(f"\n{'=' * 60}")
    print(f"  DEMO: AUTO-FLUSH WHEN CACHE IS FULL")
    print(f"  Cache max size: {local_dns.cache.max_size}")
    print(f"{'=' * 60}")

    local_dns.cache.flush_all()
    domains = ["google.com", "facebook.com", "github.com", "amazon.com",
               "microsoft.com", "reddit.com", "youtube.com"]

    for i, domain in enumerate(domains, 1):
        print(f"\n  --- Lookup #{i}: {domain} ---")
        records = real_dns_lookup_full(domain)
        local_dns.cache.put(domain, records)
        if records["A"]:
            print(f"  Resolved: {', '.join(records['A'][:3])}")
        local_dns.cache.display()

    print(f"\n  Notice how older entries were automatically evicted")
    print(f"  when the cache reached its max size of {local_dns.cache.max_size}!")


# ─────────────────────────────────────────────────────────────
#  Main interactive loop
# ─────────────────────────────────────────────────────────────

def main():
    print_banner()

    # Local DNS server with cache size of 5
    local_dns = LocalDNSServer(cache_size=5)

    while True:
        print_menu()
        try:
            choice = input("\n  Enter choice: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye!")
            break

        if choice == "1":
            domain = input("  Enter domain name (e.g., google.com): ").strip().lower()
            if not domain:
                print("  Invalid domain.")
                continue
            records, from_cache = local_dns.resolve_iterative(domain)
            print_dns_records(domain, records, from_cache)

        elif choice == "2":
            domain = input("  Enter domain name (e.g., google.com): ").strip().lower()
            if not domain:
                print("  Invalid domain.")
                continue
            records, from_cache = local_dns.resolve_recursive(domain)
            print_dns_records(domain, records, from_cache)

        elif choice == "3":
            local_dns.cache.display()

        elif choice == "4":
            local_dns.cache.flush_all()

        elif choice == "5":
            demo_caching_benefit(local_dns)

        elif choice == "6":
            demo_auto_flush(local_dns)

        elif choice == "7":
            domains_str = input("  Enter domains (comma-separated): ").strip()
            domains = [d.strip().lower() for d in domains_str.split(",") if d.strip()]
            for domain in domains:
                print(f"\n  {'─' * 40}")
                records, from_cache = local_dns.resolve_iterative(domain)
                print_dns_records(domain, records, from_cache)

        elif choice == "0":
            print("\n  Exiting DNS Simulator. Goodbye!")
            break
        else:
            print("  Invalid choice. Try again.")


if __name__ == "__main__":
    main()
