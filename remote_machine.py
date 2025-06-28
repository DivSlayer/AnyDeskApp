# remote_machine.py

import sys
import asyncio
import ssl
import websockets
import mss
import cv2
import numpy as np
import pyautogui
import json
from datetime import datetime

async def stream_handler(ws):
    """Stream desktop frames over the WebSocket."""
    client = id(ws)
    print(f"[{datetime.now()}] Video client connected: {client}")
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            while True:
                frame = np.array(sct.grab(monitor))
                ret, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                if not ret:
                    continue
                await ws.send(buf.tobytes())
                await asyncio.sleep(1/15)
    except websockets.ConnectionClosed:
        pass
    finally:
        print(f"[{datetime.now()}] Video client disconnected: {client}")

async def control_handler(ws):
    """Receive JSON mouse/keyboard events and replay them locally."""
    client = id(ws)
    print(f"[{datetime.now()}] Control client connected: {client}")
    try:
        async for msg in ws:
            ev = json.loads(msg)
            etype = ev.get("type")
            if etype == "mouse_move":
                pyautogui.moveTo(ev["x"], ev["y"])
            elif etype == "mouse_click":
                btn, action = ev["button"], ev["action"]
                if action == "down":
                    pyautogui.mouseDown(button=btn)
                else:
                    pyautogui.mouseUp(button=btn)
            elif etype == "key":
                key, action = ev["key"], ev["action"]
                if action == "down":
                    pyautogui.keyDown(key)
                else:
                    pyautogui.keyUp(key)
    except websockets.ConnectionClosed:
        pass
    finally:
        print(f"[{datetime.now()}] Control client disconnected: {client}")

async def handler(ws, path):
    """Dispatch based on the request path (/video or /control)."""
    if path == "/video":
        await stream_handler(ws)
    elif path == "/control":
        await control_handler(ws)
    else:
        await ws.close()

async def run_server(bind_ip, port):
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.load_cert_chain('cert.pem', 'key.pem')

    print(f"[{datetime.now()}] Starting server on wss://{bind_ip}:{port}")
    server = await websockets.serve(handler, bind_ip, port, ssl=ssl_ctx)
    await server.wait_closed()

def main():
    ip   = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
    asyncio.run(run_server(ip, port))

if __name__ == "__main__":
    main()
