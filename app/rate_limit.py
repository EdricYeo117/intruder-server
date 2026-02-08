import os
import time
from collections import defaultdict, deque
from dotenv import load_dotenv

load_dotenv()

WINDOW_SECONDS = int(os.getenv("WINDOW_SECONDS", "10"))
MAX_EVENTS_PER_WINDOW = int(os.getenv("MAX_EVENTS_PER_WINDOW", "3"))

_hits = defaultdict(deque)  # device_id -> deque[timestamps]

def allow(device_id: str) -> bool:
    now = time.time()
    q = _hits[device_id]
    while q and (now - q[0]) > WINDOW_SECONDS:
        q.popleft()
    if len(q) >= MAX_EVENTS_PER_WINDOW:
        return False
    q.append(now)
    return True
