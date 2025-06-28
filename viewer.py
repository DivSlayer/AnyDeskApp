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

# Thread‐safe queue for frames
frame_queue = queue.Queue()
ctrl_ws = None
running = True

async def recv_video(uri):
    """Fetch frames from server and enqueue them."""
    global running
    ssl_ctx = ssl._create_unverified_context()
    async with websockets.connect(uri + "/video", ssl=ssl_ctx) as vws:
        print(f"[{datetime.now()}] Video stream connected")
        while running:
            data = await vws.recv()
            arr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is not None:
                frame_queue.put(frame)

async def recv_control(uri):
    """Open control channel to send mouse/keyboard events."""
    global ctrl_ws
    ssl_ctx = ssl._create_unverified_context()
    ctrl_ws = await websockets.connect(uri + "/control", ssl=ssl_ctx)
    print(f"[{datetime.now()}] Control channel connected")
    await ctrl_ws.wait_closed()

def start_network_loops(server_ip, port):
    """Run both recv coroutines in a dedicated asyncio loop."""
    uri = f"wss://{server_ip}:{port}"
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tasks = [
        loop.create_task(recv_video(uri)),
        loop.create_task(recv_control(uri))
    ]
    loop.run_until_complete(asyncio.wait(tasks))

def send_event(evt: dict):
    """Thread-safe send on the control WebSocket."""
    global ctrl_ws
    if ctrl_ws and not ctrl_ws.connection_lost:
        asyncio.run_coroutine_threadsafe(
            ctrl_ws.send(json.dumps(evt)),
            asyncio.get_event_loop()
        )

def on_mouse(event, x, y, flags, param):
    """Mouse callback: forward moves and clicks."""
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

    # Read server IP/port from args or defaults
    server_ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.100.10"
    port      = sys.argv[2] if len(sys.argv) > 2 else "8765"

    # Start networking thread
    net_thread = threading.Thread(
        target=start_network_loops,
        args=(server_ip, port),
        daemon=True
    )
    net_thread.start()

    # Setup OpenCV window and mouse callback
    cv2.namedWindow('Remote Desktop')
    cv2.setMouseCallback('Remote Desktop', on_mouse)

    try:
        while running:
            # Display latest frame, if any
            try:
                frame = frame_queue.get(timeout=0.03)
                cv2.imshow('Remote Desktop', frame)
            except queue.Empty:
                pass

            # Handle keypresses
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                running = False
                break
            elif key != 255 and ctrl_ws and not ctrl_ws.connection_lost:
                # Send key down/up
                ch = chr(key)
                send_event({"type": "key", "key": ch, "action": "down"})
                send_event({"type": "key", "key": ch, "action": "up"})

    finally:
        running = False
        cv2.destroyAllWindows()
        print("Shutting down...")

if __name__ == '__main__':
    main()
