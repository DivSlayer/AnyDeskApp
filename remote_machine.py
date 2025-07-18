import sys
import asyncio
import ssl
import json
import websockets
import mss, cv2, numpy as np
import pyautogui
from datetime import datetime

async def stream_handler(ws):
    client = id(ws)
    print(f"[{datetime.now()}] VIDEO client connected: {client}")
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            while True:
                img = np.array(sct.grab(monitor))
                ret, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY),100])
                if not ret:
                    continue
                await ws.send(buf.tobytes())
                await asyncio.sleep(1/30)
    except websockets.ConnectionClosed:
        pass
    finally:
        print(f"[{datetime.now()}] VIDEO client disconnected: {client}")

async def control_handler(ws):
    client = id(ws)
    print(f"[{datetime.now()}] CONTROL client connected: {client}")
    try:
        async for msg in ws:
            try:
                ev = json.loads(msg)
            except json.JSONDecodeError:
                print(f"[{datetime.now()}] ❌ JSON parse error for: {msg!r}")
                continue

            et = ev.get("type")
            if et == "mouse_move":
                x, y = ev["x"], ev["y"]
                pyautogui.moveTo(x, y)
            elif et == "mouse_click":
                btn, action = ev["button"], ev["action"]
                if action == "down":
                    pyautogui.mouseDown(button=btn)
                else:
                    pyautogui.mouseUp(button=btn)
            elif et == "key":
                key, action = ev["key"], ev["action"]
                print(f"DEBUG REMOTE: Received key event: {{'key': '{key}', 'action': '{action}'}}") # DEBUG PRINT
                if action == "down":
                    pyautogui.keyDown(key)
                else:
                    pyautogui.keyUp(key)
            elif et == "mouse_scroll":
                direction = ev["direction"]
                if direction == "up":
                    pyautogui.scroll(1)
                elif direction == "down":
                    pyautogui.scroll(-1)
            elif et == "mouse_dblclick":
                btn = ev["button"]
                x = ev.get("x")
                y = ev.get("y")
                if x is not None and y is not None:
                    pyautogui.click(x=x, y=y, button=btn, clicks=2)
                else:
                    pyautogui.click(button=btn, clicks=2)
            else:
                print(f"[{datetime.now()}] ❓ Unknown event type: {et!r}")
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
        print(f"[{datetime.now()}] Invalid path: {path}, closing")
        await ws.close()

async def main():
    bind_ip = sys.argv[1] if len(sys.argv)>1 else "0.0.0.0"
    port    = int(sys.argv[2]) if len(sys.argv)>2 else 8765

    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    try:
        ssl_ctx.load_cert_chain("cert.pem", "key.pem")
    except FileNotFoundError:
        print("Error: SSL certificate (cert.pem) or key (key.pem) not found.")
        print("Please ensure 'cert.pem' and 'key.pem' are in the same directory as remote_machine.py.")
        print("You can generate self-signed certificates using OpenSSL (e.g., openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365)")
        sys.exit(1)

    print(f"[{datetime.now()}] Starting server on {bind_ip}:{port}")
    async with websockets.serve(handler, bind_ip, port, ssl=ssl_ctx):
        await asyncio.Future()

if __name__ == "__main__":
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.001

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped by user (Ctrl+C)")
    except Exception as e:
        print(f"An error occurred: {e}")