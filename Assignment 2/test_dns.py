"""
Automated test script for DNS Simulator - verifies all features work.
"""
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(__file__))

from dns_simulator import (
    DNSMessage, DNSCache, LocalDNSServer,
    real_dns_lookup_full, print_dns_records
)

PASS = 0
FAIL = 0

def test(name, condition):
    global PASS, FAIL
    if condition:
        print(f"  [PASS] {name}")
        PASS += 1
    else:
        print(f"  [FAIL] {name}")
        FAIL += 1

print("=" * 60)
print("  DNS SIMULATOR - AUTOMATED TESTS")
print("=" * 60)

# --- Test 1: DNS Message Format ---
print("\n--- Test 1: DNS Message Format ---")
msg = DNSMessage("google.com", "A")
test("Message ID is 16-bit", 0 <= msg.identification <= 0xFFFF)
test("Flags is 16-bit", 0 <= msg.flags <= 0xFFFF)
test("Header packs to 12 bytes", len(msg.pack_header()) == 12)
test("Query name stored", msg.query_name == "google.com")
msg.display("Test Query Message")

resp = msg.make_response()
test("Response has same ID", resp.identification == msg.identification)
test("Response QR bit set", resp.flags & DNSMessage.QR_RESPONSE)
resp.set_authoritative()
test("AA flag set", resp.flags & DNSMessage.AA_FLAG)
resp.display("Test Response Message")

# --- Test 2: DNS Cache ---
print("\n--- Test 2: DNS Cache with Auto-Flush ---")
cache = DNSCache(max_size=3)
test("Cache starts empty", len(cache.cache) == 0)

cache.put("a.com", {"A": ["1.1.1.1"], "NS": [], "MX": [], "CNAME": []})
cache.put("b.com", {"A": ["2.2.2.2"], "NS": [], "MX": [], "CNAME": []})
cache.put("c.com", {"A": ["3.3.3.3"], "NS": [], "MX": [], "CNAME": []})
test("Cache holds 3 items", len(cache.cache) == 3)

# This should trigger auto-flush (evict oldest = a.com)
cache.put("d.com", {"A": ["4.4.4.4"], "NS": [], "MX": [], "CNAME": []})
test("Auto-flush: size still 3", len(cache.cache) == 3)
result, _ = cache.get("a.com")
test("Auto-flush: oldest evicted", result is None)
result, _ = cache.get("d.com")
test("Auto-flush: newest exists", result is not None)

# Cache hit/miss
test("Cache hits counted", cache.hits > 0)
test("Cache misses counted", cache.misses > 0)

cache.display()

# --- Test 3: Real DNS Lookup ---
print("\n--- Test 3: Real DNS Record Lookup ---")
records = real_dns_lookup_full("google.com")
test("google.com has A records", len(records["A"]) > 0)
test("google.com has NS records", len(records.get("NS", [])) > 0)
print_dns_records("google.com", records)

records2 = real_dns_lookup_full("github.com")
test("github.com has A records", len(records2["A"]) > 0)
print_dns_records("github.com", records2)

# --- Test 4: Iterative Resolution ---
print("\n--- Test 4: Iterative DNS Resolution ---")
local_dns = LocalDNSServer(cache_size=5)
records, from_cache = local_dns.resolve_iterative("google.com")
test("Iterative: got records", len(records["A"]) > 0)
test("Iterative: not from cache (first)", from_cache == False)

# Second lookup should be cached
records, from_cache = local_dns.resolve_iterative("google.com")
test("Iterative: cached second time", from_cache == True)

# --- Test 5: Recursive Resolution ---
print("\n--- Test 5: Recursive DNS Resolution ---")
local_dns2 = LocalDNSServer(cache_size=5)
records, from_cache = local_dns2.resolve_recursive("facebook.com")
test("Recursive: got records", len(records["A"]) > 0)
test("Recursive: not from cache (first)", from_cache == False)

# Cached
records, from_cache = local_dns2.resolve_recursive("facebook.com")
test("Recursive: cached second time", from_cache == True)

# --- Test 6: Multiple domain lookups ---
print("\n--- Test 6: Multiple Domain Lookups ---")
test_domains = ["microsoft.com", "amazon.com", "youtube.com"]
for d in test_domains:
    r = real_dns_lookup_full(d)
    test(f"{d} resolves", len(r["A"]) > 0)
    print_dns_records(d, r)

# --- Summary ---
print(f"\n{'=' * 60}")
print(f"  TEST RESULTS: {PASS} passed, {FAIL} failed out of {PASS + FAIL}")
print(f"{'=' * 60}")

if FAIL > 0:
    sys.exit(1)
else:
    print("  ALL TESTS PASSED!")
    sys.exit(0)
