# viewer.py

import sys
import asyncio
import ssl
import json
import threading
import queue
import cv2
import numpy as np
import websockets
from datetime import datetime
from pynput import mouse, keyboard

# Thread-safe queue for incoming frames
frame_q = queue.Queue()

# WebSocket for control
ctrl_ws = None
# Event to mark control channel readiness
control_ready = threading.Event()

async def video_loop(uri):
    """Connect to /video, receive JPEG frames, decode & enqueue them."""
    ssl_ctx = ssl._create_unverified_context()
    async with websockets.connect(uri + "/video", ssl=ssl_ctx) as vws:
        print(f"[{datetime.now()}] VIDEO connected to {uri}/video")
        try:
            while True:
                data = await vws.recv()  # raw JPEG bytes
                img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    frame_q.put(img)
        except websockets.ConnectionClosed:
            print(f"[{datetime.now()}] VIDEO connection closed")

async def control_loop(uri):
    """Connect to /control and keep that socket open for sends."""
    global ctrl_ws
    ssl_ctx = ssl._create_unverified_context()
    print(f"[{datetime.now()}] Connecting CONTROL to {uri}/control …")
    ctrl_ws = await websockets.connect(uri + "/control", ssl=ssl_ctx)
    print(f"[{datetime.now()}] CONTROL connected")
    control_ready.set()
    try:
        await ctrl_ws.wait_closed()
    finally:
        print(f"[{datetime.now()}] CONTROL closed")

def start_network(ip, port):
    """Run both video and control loops in a single asyncio event loop."""
    uri = f"wss://{ip}:{port}"
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(asyncio.gather(
        video_loop(uri),
        control_loop(uri)
    ))

def send_event(evt):
    """Send a JSON-serializable event over the control channel."""
    if not control_ready.is_set():
        print(f"[{datetime.now()}] ❌ CONTROL not ready, dropping {evt}")
        return
    print(f"[{datetime.now()}] SENDING: {evt}")
    asyncio.run_coroutine_threadsafe(
        ctrl_ws.send(json.dumps(evt)),
        asyncio.get_event_loop()
    )

#  ─── pynput Listeners ──────────────────────────────────────────────────────

def on_move(x, y):
    send_event({"type": "mouse_move", "x": int(x), "y": int(y)})

def on_click(x, y, button, pressed):
    send_event({
        "type": "mouse_click",
        "button": button.name,        # 'left', 'right', etc.
        "action": "down" if pressed else "up"
    })

def on_scroll(x, y, dx, dy):
    # Optional: implement scroll if you like
    pass

def on_key_press(key):
    try:
        k = key.char
    except AttributeError:
        k = key.name
    send_event({"type": "key", "key": k, "action": "down"})

def on_key_release(key):
    try:
        k = key.char
    except AttributeError:
        k = key.name
    send_event({"type": "key", "key": k, "action": "up"})

#  ─── Main ─────────────────────────────────────────────────────────────────

def main():
    ip   = sys.argv[1] if len(sys.argv) > 1 else "192.168.100.10"
    port = sys.argv[2] if len(sys.argv) > 2 else "8765"

    # Start networking in background thread
    threading.Thread(target=start_network, args=(ip, port), daemon=True).start()

    # Start input listeners (captures global mouse & keyboard)
    mouse.Listener(on_move=on_move,
                   on_click=on_click,
                   on_scroll=on_scroll).start()
    keyboard.Listener(on_press=on_key_press,
                      on_release=on_key_release).start()

    # Display loop: pop frames and show them
    cv2.namedWindow("Remote Desktop", cv2.WINDOW_NORMAL)
    while True:
        frame = frame_q.get()
        cv2.imshow("Remote Desktop", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
    print("Viewer exiting…")

if __name__ == "__main__":
    main()
