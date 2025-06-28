import sys
import asyncio
import ssl
import json
import websockets
import mss
import cv2
import numpy as np
import pyautogui
from datetime import datetime

async def stream_handler(ws):
    """Streams the desktop at ~15 FPS as JPEG over /video."""
    client = id(ws)
    print(f"[{datetime.now()}] VIDEO client connected: {client}")
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            while True:
                img = np.array(sct.grab(monitor))
                ret, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY),50])
                if not ret:
                    continue
                await ws.send(buf.tobytes())
                await asyncio.sleep(1/15)
    except websockets.ConnectionClosed:
        pass
    finally:
        print(f"[{datetime.now()}] VIDEO client disconnected: {client}")

async def control_handler(ws):
    """Receives JSON mouse/keyboard events over /control and replays via pyautogui."""
    client = id(ws)
    print(f"[{datetime.now()}] CONTROL client connected: {client}")
    try:
        async for msg in ws:
            ev = json.loads(msg)
            t = ev.get("type")
            if t == "mouse_move":
                pyautogui.moveTo(ev["x"], ev["y"])
            elif t == "mouse_click":
                btn, action = ev["button"], ev["action"]
                if action == "down":
                    pyautogui.mouseDown(button=btn)
                else:
                    pyautogui.mouseUp(button=btn)
            elif t == "key":
                key, action = ev["key"], ev["action"]
                if action == "down":
                    pyautogui.keyDown(key)
                else:
                    pyautogui.keyUp(key)
    except websockets.ConnectionClosed:
        pass
    finally:
        print(f"[{datetime.now()}] CONTROL client disconnected: {client}")

async def handler(ws):
    path = ws.request.path
    if path == "/video":
        await stream_handler(ws)
    elif path == "/control":
        await control_handler(ws)
    else:
        await ws.close()

async def main():
    bind_ip = sys.argv[1] if len(sys.argv)>1 else "0.0.0.0"
    port    = int(sys.argv[2]) if len(sys.argv)>2 else 8765

    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.load_cert_chain('cert.pem','key.pem')

    print(f"[{datetime.now()}] Server listening on wss://{bind_ip}:{port}")
    await websockets.serve(handler, bind_ip, port, ssl=ssl_ctx)
    await asyncio.Future()  # run forever

if __name__=="__main__":
    asyncio.run(main())
