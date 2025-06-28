# viewer.py

import sys
import threading
import asyncio
import ssl
import json
import queue
from datetime import datetime

import numpy as np
import cv2
import websockets

frame_queue = queue.Queue()
ctrl_ws = None
running = True

async def recv_video(uri):
    """Receive frames from /video and enqueue them."""
    global running
    ssl_ctx = ssl._create_unverified_context()
    async with websockets.connect(uri + "/video", ssl=ssl_ctx) as vws:
        print(f"[{datetime.now()}] Connected to video stream")
        while running:
            data = await vws.recv()
            img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                frame_queue.put(img)

async def recv_control(uri):
    """Open the /control channel for sending events."""
    global ctrl_ws
    ssl_ctx = ssl._create_unverified_context()
    ctrl_ws = await websockets.connect(uri + "/control", ssl=ssl_ctx)
    print(f"[{datetime.now()}] Control channel open")
    await ctrl_ws.wait_closed()

def network_thread(ip, port):
    uri = f"wss://{ip}:{port}"
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tasks = [
        loop.create_task(recv_video(uri)),
        loop.create_task(recv_control(uri))
    ]
    loop.run_until_complete(asyncio.wait(tasks))

def send_event(evt: dict):
    """Send JSON event over control channel."""
    global ctrl_ws
    if ctrl_ws and not ctrl_ws.closed:
        asyncio.run_coroutine_threadsafe(ctrl_ws.send(json.dumps(evt)),
                                         asyncio.get_event_loop())

def on_mouse(event, x, y, flags, param):
    """Forward mouse moves and clicks."""
    if not running or ctrl_ws is None:
        return
    if event == cv2.EVENT_MOUSEMOVE:
        send_event({"type": "mouse_move", "x": x, "y": y})
    elif event == cv2.EVENT_LBUTTONDOWN:
        send_event({"type": "mouse_click", "button": "left", "action": "down"})
    elif event == cv2.EVENT_LBUTTONUP:
        send_event({"type": "mouse_click", "button": "left", "action": "up"})
    elif event == cv2.EVENT_RBUTTONDOWN:
        send_event({"type": "mouse_click", "button": "right", "action": "down"})
    elif event == cv2.EVENT_RBUTTONUP:
        send_event({"type": "mouse_click", "button": "right", "action": "up"})

def main():
    global running

    ip   = sys.argv[1] if len(sys.argv) > 1 else "192.168.100.10"
    port = sys.argv[2] if len(sys.argv) > 2 else "8765"

    # Start networking
    t = threading.Thread(target=network_thread, args=(ip, port), daemon=True)
    t.start()

    cv2.namedWindow('Remote Desktop')
    cv2.setMouseCallback('Remote Desktop', on_mouse)

    try:
        while running:
            # Display next frame if available
            try:
                frame = frame_queue.get(timeout=0.03)
                cv2.imshow('Remote Desktop', frame)
            except queue.Empty:
                pass

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                running = False
                break
            elif key != 255 and ctrl_ws and not ctrl_ws.closed:
                ch = chr(key)
                send_event({"type": "key", "key": ch, "action": "down"})
                send_event({"type": "key", "key": ch, "action": "up"})
    finally:
        running = False
        cv2.destroyAllWindows()
        print("Viewer shutdown")

if __name__ == "__main__":
    main()
