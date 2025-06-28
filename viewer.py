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

# Thread-safe queue for incoming frames
global frame_queue, ctrl_ws, connection_lost, running
frame_queue = queue.Queue()
ctrl_ws = None
connection_lost = True
running = True

async def recv_video(uri):
    """Receive frames from server and enqueue them."""
    global running
    ssl_ctx = ssl._create_unverified_context()
    async with websockets.connect(uri + "/video", ssl=ssl_ctx) as vws:
        print(f"[{datetime.now()}] Video stream connected")
        while running:
            try:
                data = await vws.recv()
            except websockets.ConnectionClosed:
                break
            frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                frame_queue.put(frame)

async def recv_control(uri):
    """Open control channel for sending events."""
    global ctrl_ws, connection_lost
    ssl_ctx = ssl._create_unverified_context()
    ctrl_ws = await websockets.connect(uri + "/control", ssl=ssl_ctx)
    connection_lost = False
    print(f"[{datetime.now()}] Control channel connected")
    try:
        await ctrl_ws.wait_closed()
    finally:
        connection_lost = True
        print(f"[{datetime.now()}] Control channel closed")

async def start_network(ip, port):
    uri = f"wss://{ip}:{port}"
    await asyncio.gather(
        recv_video(uri),
        recv_control(uri)
    )

def network_thread(ip, port):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_network(ip, port))

def send_event(evt: dict):
    """Send control event if channel is open."""
    if ctrl_ws and not connection_lost:
        asyncio.run_coroutine_threadsafe(
            ctrl_ws.send(json.dumps(evt)),
            asyncio.get_event_loop()
        )
    else:
        print(f"[{datetime.now()}] Cannot send event, control channel lost")

# Mouse callback
def on_mouse(event, x, y, flags, param):
    if not running or connection_lost:
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

# Main viewer loop
def main():
    global running
    ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.100.10"
    port = sys.argv[2] if len(sys.argv) > 2 else "8765"

    # Start network thread
t = threading.Thread(target=network_thread, args=(ip, port), daemon=True)
    t.start()

    cv2.namedWindow('Remote Desktop', cv2.WINDOW_NORMAL)
    cv2.setMouseCallback('Remote Desktop', on_mouse)

    while running:
        # Show latest frame
        try:
            frame = frame_queue.get(timeout=0.05)
            cv2.imshow('Remote Desktop', frame)
        except queue.Empty:
            pass
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            running = False
            break
        elif key != 255 and not connection_lost:
            ch = chr(key)
            send_event({"type": "key", "key": ch, "action": "down"})
            send_event({"type": "key", "key": ch, "action": "up"})

    cv2.destroyAllWindows()
    print("Viewer exited")

if __name__ == '__main__':
    main()
