"""Two-size streaming experiment in a FRESH process per size: RSS sampled during upload only."""
import json, os, sys, threading, time, tracemalloc
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from auditor_candidate_binding import Adapter
src = Path(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir()
a = Adapter(out)
def rss(): return int(open('/proc/self/status').read().split('VmRSS:')[1].split()[0])
base = rss(); samples = []; stop = []
def sampler():
    while not stop: samples.append(rss()); time.sleep(.05)
t = threading.Thread(target=sampler, daemon=True); t.start()
r = a.upload_file_in_chunks(src, 65536); stop.append(1); t.join()
ident = a.registered_identity(r.capability) if r.accepted else None
print(json.dumps(dict(file_bytes=src.stat().st_size, accepted=r.accepted, identity_size=ident and ident['size_bytes'], rss_base_kb=base, rss_peak_kb=max(samples), rss_delta_kb=max(samples) - base,
                      peak_traced=a._stream['peak_traced'], asgi_reads=a._stream['reads_n'], max_read=a._stream['reads_max'], seconds=a._stream['seconds'])))
a.close()
