import sys
import threading
import asyncio
import ssl
import json
import queue
import cv2
import numpy as np
import websockets
from datetime import datetime

# ─── Globals ─────────────────────────────────────────────────────────────────

frame_q        = queue.Queue()     # incoming video frames
ctrl_ws        = None              # control WebSocket
control_ready  = threading.Event() # set when control channel is open
network_loop   = None              # the asyncio loop in the network thread

# ─── Asyncio Coroutines ──────────────────────────────────────────────────────

async def video_loop(uri):
    ssl_ctx = ssl._create_unverified_context()
    async with websockets.connect(uri + "/video", ssl=ssl_ctx) as vws:
        print(f"[{datetime.now()}] VIDEO connected to {uri}/video")
        try:
            while True:
                data = await vws.recv()
                img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    frame_q.put(img)
        except websockets.ConnectionClosed:
            print(f"[{datetime.now()}] VIDEO connection closed")

async def control_loop(uri):
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

# ─── Network Thread Setup ────────────────────────────────────────────────────

def start_network(ip, port):
    global network_loop
    uri = f"wss://{ip}:{port}"
    network_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(network_loop)
    network_loop.run_until_complete(asyncio.gather(
        video_loop(uri),
        control_loop(uri)
    ))

# ─── Control Sender ─────────────────────────────────────────────────────────

def send_event(evt: dict):
    if not control_ready.is_set():
        return
    asyncio.run_coroutine_threadsafe(
        ctrl_ws.send(json.dumps(evt)),
        network_loop
    )

# ─── Mouse Callback (window‑local) ───────────────────────────────────────────

def on_mouse(event, x, y, flags, param):
    # cv2 passes events only when mouse is over the window
    if not control_ready.is_set(): return
    if event == cv2.EVENT_MOUSEMOVE:
        send_event({"type":"mouse_move",  "x":x, "y":y})
    elif event == cv2.EVENT_LBUTTONDOWN:
        send_event({"type":"mouse_click","button":"left","action":"down"})
    elif event == cv2.EVENT_LBUTTONUP:
        send_event({"type":"mouse_click","button":"left","action":"up"})
    elif event == cv2.EVENT_RBUTTONDOWN:
        send_event({"type":"mouse_click","button":"right","action":"down"})
    elif event == cv2.EVENT_RBUTTONUP:
        send_event({"type":"mouse_click","button":"right","action":"up"})

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    ip   = sys.argv[1] if len(sys.argv)>1 else "192.168.100.10"
    port = sys.argv[2] if len(sys.argv)>2 else "8765"

    # 1) Start networking in background
    t = threading.Thread(target=start_network, args=(ip, port), daemon=True)
    t.start()

    # 2) Prepare OpenCV window and mouse callback
    cv2.namedWindow("Remote Desktop", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Remote Desktop", on_mouse)

    # 3) Display & keyboard loop
    while True:
        frame = frame_q.get()
        cv2.imshow("Remote Desktop", frame)

        key = cv2.waitKey(1) & 0xFF
        # only capture key when window is focused
        # if key == ord('27'):
        if key == 27:
            break
        elif control_ready.is_set() and key != 255:
            k = chr(key)
            send_event({"type":"key","key":k,"action":"down"})
            send_event({"type":"key","key":k,"action":"up"})

    cv2.destroyAllWindows()
    print("Viewer exiting…")

if __name__ == "__main__":
    main()
