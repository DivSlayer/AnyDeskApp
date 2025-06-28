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

# For mouse mapping
remote_w, remote_h = None, None
pad_vert, pad_horiz, new_w, new_h = 0, 0, 0, 0

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
    global remote_w, remote_h, pad_vert, pad_horiz, new_w, new_h
    # Map (x, y) from window to remote screen
    # Remove padding
    x_img = x - pad_horiz
    y_img = y - pad_vert
    if 0 <= x_img < new_w and 0 <= y_img < new_h:
        # Map to remote screen coordinates
        remote_x = int(x_img * remote_w / new_w)
        remote_y = int(y_img * remote_h / new_h)
        if not control_ready.is_set(): return
        if event == cv2.EVENT_MOUSEMOVE:
            send_event({"type":"mouse_move",  "x":remote_x, "y":remote_y})
        elif event == cv2.EVENT_LBUTTONDOWN:
            send_event({"type":"mouse_click","button":"left","action":"down"})
        elif event == cv2.EVENT_LBUTTONUP:
            send_event({"type":"mouse_click","button":"left","action":"up"})
        elif event == cv2.EVENT_RBUTTONDOWN:
            send_event({"type":"mouse_click","button":"right","action":"down"})
        elif event == cv2.EVENT_RBUTTONUP:
            send_event({"type":"mouse_click","button":"right","action":"up"})
        elif event == cv2.EVENT_LBUTTONDBLCLK:
            send_event({"type":"mouse_dblclick","button":"left","x":remote_x,"y":remote_y})
        elif event == cv2.EVENT_RBUTTONDBLCLK:
            send_event({"type":"mouse_dblclick","button":"right","x":remote_x,"y":remote_y})
    # else: mouse is in black bar area, ignore or clamp as needed

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    ip   = sys.argv[1] if len(sys.argv)>1 else "127.0.0.1"
    port = sys.argv[2] if len(sys.argv)>2 else "8000"

    # 1) Start networking in background
    t = threading.Thread(target=start_network, args=(ip, port), daemon=True)
    t.start()

    # 2) Prepare OpenCV window and mouse callback
    cv2.namedWindow("Remote Desktop", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Remote Desktop", on_mouse)

    # 3) Display & keyboard loop
    desired_width = 1920
    desired_height = 1080
    global remote_w, remote_h, pad_vert, pad_horiz, new_w, new_h
    while True:
        frame = frame_q.get()
        h, w = frame.shape[:2]
        if remote_w is None or remote_h is None:
            remote_w, remote_h = w, h
        aspect_original = w / h
        aspect_desired = desired_width / desired_height

        if aspect_original > aspect_desired:
            new_w = desired_width
            new_h = int(desired_width / aspect_original)
            resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            pad_vert = (desired_height - new_h) // 2
            pad_horiz = 0
            output = cv2.copyMakeBorder(resized, pad_vert, desired_height - new_h - pad_vert, 0, 0, cv2.BORDER_CONSTANT, value=[0,0,0])
        else:
            new_h = desired_height
            new_w = int(desired_height * aspect_original)
            resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            pad_horiz = (desired_width - new_w) // 2
            pad_vert = 0
            output = cv2.copyMakeBorder(resized, 0, 0, pad_horiz, desired_width - new_w - pad_horiz, cv2.BORDER_CONSTANT, value=[0,0,0])

        cv2.imshow("Remote Desktop", output)

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
