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

# Thread-safe queue for video frames
frame_q = queue.Queue()
# WebSocket for control
ctrl_ws = None
# Flag to indicate control channel status
control_ready = threading.Event()

async def video_loop(uri):
    ssl_ctx = ssl._create_unverified_context()
    async with websockets.connect(uri + "/video", ssl=ssl_ctx) as vws:
        print(f"[{datetime.now()}] Video connected")
        while True:
            data = await vws.recv()
            img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                frame_q.put(img)

async def control_loop(uri):
    global ctrl_ws
    ssl_ctx = ssl._create_unverified_context()
    ctrl_ws = await websockets.connect(uri + "/control", ssl=ssl_ctx)
    print(f"[{datetime.now()}] Control connected")
    control_ready.set()
    await ctrl_ws.wait_closed()
    print(f"[{datetime.now()}] Control closed")

def start_network(ip, port):
    uri = f"wss://{ip}:{port}"
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(asyncio.gather(
        video_loop(uri),
        control_loop(uri)
    ))

def send_event(evt):
    if control_ready.is_set() and ctrl_ws:
        asyncio.run_coroutine_threadsafe(
            ctrl_ws.send(json.dumps(evt)),
            asyncio.get_event_loop()
        )
    else:
        # not ready yet
        pass

def on_move(x, y):
    send_event({"type":"mouse_move","x":int(x),"y":int(y)})

def on_click(x, y, button, pressed):
    send_event({
        "type":"mouse_click",
        "button": button.name,      # 'left' or 'right'
        "action": "down" if pressed else "up"
    })

def on_scroll(x, y, dx, dy):
    # optional: implement scroll if you like
    pass

def on_key_press(key):
    try:
        k = key.char
    except AttributeError:
        k = key.name  # special keys
    send_event({"type":"key","key":k,"action":"down"})

def on_key_release(key):
    try:
        k = key.char
    except AttributeError:
        k = key.name
    send_event({"type":"key","key":k,"action":"up"})

def main():
    ip   = sys.argv[1] if len(sys.argv)>1 else "192.168.100.10"
    port = sys.argv[2] if len(sys.argv)>2 else "8765"

    # start websockets in background
    t = threading.Thread(target=start_network, args=(ip, port), daemon=True)
    t.start()

    # start input listeners
    mouse.Listener(on_move=on_move,
                   on_click=on_click,
                   on_scroll=on_scroll).start()
    keyboard.Listener(on_press=on_key_press,
                      on_release=on_key_release).start()

    # display loop
    cv2.namedWindow("Remote Desktop", cv2.WINDOW_NORMAL)
    while True:
        frame = frame_q.get()
        cv2.imshow("Remote Desktop", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()

if __name__=="__main__":
    main()
