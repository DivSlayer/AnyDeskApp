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
from pynput import keyboard
import time
import string # New import for string.printable

# ─── Globals ─────────────────────────────────────────────────────────────────

frame_q        = queue.Queue()     # incoming video frames
ctrl_ws        = None              # control WebSocket
control_ready  = threading.Event() # set when control channel is open
network_loop   = None              # the asyncio loop in the network thread

# For mouse mapping
remote_w, remote_h = None, None
pad_vert, pad_horiz, new_w, new_h = 0, 0, 0, 0

# Track currently pressed modifier keys to ensure proper down/up sequencing
currently_pressed_modifiers = set()

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
    x_img = x - pad_horiz
    y_img = y - pad_vert
    if 0 <= x_img < new_w and 0 <= y_img < new_h:
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

# ─── pynput Keyboard Listener Callbacks ──────────────────────────────────────

def get_pyautogui_key_name(key):
    # Handle regular character keys and symbols
    if hasattr(key, 'char') and key.char is not None:
        # pynput returns control characters for Ctrl+Key combinations
        # e.g., Ctrl+A -> '\x01', Ctrl+C -> '\x03'
        # We need to convert these back to their literal character for pyautogui
        try:
            char_code = ord(key.char)
            if 1 <= char_code <= 26: # This range covers Ctrl+A to Ctrl+Z
                # Convert control char to lowercase letter (e.g., '\x01' -> 'a')
                return chr(ord('a') + char_code - 1)
            elif key.char in string.printable and len(key.char) == 1:
                return key.char # Regular printable characters
            else:
                # For other non-standard chars that might have a .char
                return str(key.char)
        except TypeError: # key.char might not be convertible to int if it's not a single char
            return str(key.char) # Fallback to string representation

    # Handle special keys (e.g., Key.space, Key.ctrl_l)
    else:
        if key == keyboard.Key.space: return "space"
        elif key == keyboard.Key.enter: return "enter"
        elif key == keyboard.Key.backspace: return "backspace"
        elif key == keyboard.Key.tab: return "tab"
        elif key == keyboard.Key.esc: return "escape"
        elif key == keyboard.Key.up: return "up"
        elif key == keyboard.Key.down: return "down"
        elif key == keyboard.Key.left: return "left"
        elif key == keyboard.Key.right: return "right"
        elif key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r: return "control"
        elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r: return "alt"
        elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r: return "shift"
        elif key == keyboard.Key.cmd_l or key == keyboard.Key.cmd_r: return "win"
        elif key == keyboard.Key.delete: return "delete"
        elif key == keyboard.Key.home: return "home"
        elif key == keyboard.Key.end: return "end"
        elif key == keyboard.Key.page_up: return "pageup"
        elif key == keyboard.Key.page_down: return "pagedown"
        # For function keys like F1, F2, etc.
        elif str(key).startswith('Key.f'):
            return str(key).replace('Key.', '').lower()
        else:
            print(f"Unhandled special key detected by pynput: {key}")
            return None # Return None for truly unhandled keys

def on_press(key):
    if not control_ready.is_set():
        return
    
    pyautogui_key = get_pyautogui_key_name(key)
    
    if pyautogui_key:
        print(f"DEBUG VIEWER: Key pressed: {pyautogui_key} (down)")
        if pyautogui_key in ["control", "alt", "shift", "win"]:
            if pyautogui_key not in currently_pressed_modifiers:
                send_event({"type": "key", "key": pyautogui_key, "action": "down"})
                currently_pressed_modifiers.add(pyautogui_key)
        else:
            send_event({"type": "key", "key": pyautogui_key, "action": "down"})
        print(f"DEBUG VIEWER: Currently pressed modifiers: {currently_pressed_modifiers}")


def on_release(key):
    if not control_ready.is_set():
        return
    
    pyautogui_key = get_pyautogui_key_name(key)
    
    if pyautogui_key:
        print(f"DEBUG VIEWER: Key released: {pyautogui_key} (up)")
        if pyautogui_key in ["control", "alt", "shift", "win"]:
            send_event({"type": "key", "key": pyautogui_key, "action": "up"})
            currently_pressed_modifiers.discard(pyautogui_key)
            time.sleep(0.01) # Small delay (10 milliseconds)
        else:
            send_event({"type": "key", "key": pyautogui_key, "action": "up"})
        print(f"DEBUG VIEWER: Currently pressed modifiers: {currently_pressed_modifiers}")
            
    if key == keyboard.Key.esc:
        print("ESC pressed, stopping keyboard listener.")
        return False

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    ip   = sys.argv[1] if len(sys.argv)>1 else "127.0.0.1"
    port = sys.argv[2] if len(sys.argv)>2 else "8000"

    t = threading.Thread(target=start_network, args=(ip, port), daemon=True)
    t.start()

    cv2.namedWindow("Remote Desktop", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Remote Desktop", on_mouse)

    keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    keyboard_listener.start()

    desired_width = 1920
    desired_height = 1080
    global remote_w, remote_h, pad_vert, pad_horiz, new_w, new_h
    while True:
        try:
            frame = frame_q.get(timeout=0.05) 
        except queue.Empty:
            if not t.is_alive():
                print("Network thread died, exiting viewer.")
                break
            frame = None

        if frame is not None:
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

        key_press = cv2.waitKey(1) & 0xFF
        if key_press == 27:
            break
        
        if not keyboard_listener.is_alive():
            print("Keyboard listener stopped (possibly due to ESC key), exiting viewer.")
            break

    cv2.destroyAllWindows()
    if keyboard_listener.is_alive():
        keyboard_listener.stop()
        keyboard_listener.join()
    print("Viewer exiting…")

if __name__ == "__main__":
    main()