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
import os
import psutil # Still useful for process management if needed, but not directly for this bug.

# ─── Globals ─────────────────────────────────────────────────────────────────

frame_q        = queue.Queue()     # incoming video frames
ctrl_ws        = None              # control WebSocket
control_ready  = threading.Event() # set when control channel is open
network_loop   = None              # the asyncio loop in the network thread
# Use a flag to signal main thread to exit gracefully
should_exit_viewer = False

# ─── Asyncio Coroutines ──────────────────────────────────────────────────────

async def video_loop(uri):
    global should_exit_viewer
    # Revert to original ssl context creation
    ssl_ctx = ssl._create_unverified_context()
    try:
        async with websockets.connect(uri + "/video", ssl=ssl_ctx) as vws:
            print(f"[{datetime.now()}] VIDEO connected to {uri}/video")
            while True:
                if should_exit_viewer: # Check if main thread wants to exit
                    break
                data = await vws.recv()
                img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    frame_q.put(img)
    except websockets.ConnectionClosed as e:
        print(f"[{datetime.now()}] VIDEO connection closed: {e}")
    except Exception as e:
        print(f"[{datetime.now()}] VIDEO loop error: {e}")
    finally:
        print(f"[{datetime.now()}] VIDEO loop terminated.")
        should_exit_viewer = True # Signal main thread to exit on disconnect

async def control_loop(uri):
    global ctrl_ws, should_exit_viewer
    # Revert to original ssl context creation
    ssl_ctx = ssl._create_unverified_context()
    try:
        print(f"[{datetime.now()}] Connecting CONTROL to {uri}/control …")
        ctrl_ws = await websockets.connect(uri + "/control", ssl=ssl_ctx)
        print(f"[{datetime.now()}] CONTROL connected")
        control_ready.set() # Signal that control is ready

        # Keep the control connection alive
        await ctrl_ws.wait_closed()

    except websockets.ConnectionClosed as e:
        print(f"[{datetime.now()}] CONTROL connection closed: {e}")
    except Exception as e:
        print(f"[{datetime.now()}] CONTROL loop error: {e}")
    finally:
        print(f"[{datetime.now()}] CONTROL loop terminated.")
        ctrl_ws = None # Reset ctrl_ws to None
        control_ready.clear() # Clear the event
        should_exit_viewer = True # Signal main thread to exit on disconnect

# ─── Network Thread Setup ────────────────────────────────────────────────────

def start_network(ip, port):
    global network_loop
    uri = f"wss://{ip}:{port}"
    network_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(network_loop)
    try:
        network_loop.run_until_complete(
            asyncio.gather(
                video_loop(uri),
                control_loop(uri),
                return_exceptions=True # Keep this, it's good practice
            )
        )
    except asyncio.CancelledError:
        print(f"[{datetime.now()}] Network loop cancelled.")
    except Exception as e:
        print(f"[{datetime.now()}] Unhandled exception in network thread: {e}")
    finally:
        print(f"[{datetime.now()}] Network loop shutdown complete.")
        network_loop.close()

# ─── Control Sender ─────────────────────────────────────────────────────────

def send_event(evt: dict):
    # Ensure control_ready is set AND ctrl_ws is not None and is not closed
    # Also check if the network_loop is running before trying to schedule
    if control_ready.is_set() and ctrl_ws and not ctrl_ws.closed and network_loop and network_loop.is_running():
        try:
            asyncio.run_coroutine_threadsafe(
                ctrl_ws.send(json.dumps(evt)),
                network_loop
            )
        except Exception as e:
            # This catch is important for debugging why messages aren't sent
            print(f"[{datetime.now()}] Error sending event via run_coroutine_threadsafe: {e}")
    # else:
    #     print(f"[{datetime.now()}] Control not ready or connection closed. Event not sent: {evt}")


# ─── Mouse Callback (window‑local) ───────────────────────────────────────────

def on_mouse(event, x, y, flags, param):
    if not control_ready.is_set(): return
    # Filter out redundant mouse move events to reduce load, if desired
    # if event == cv2.EVENT_MOUSEMOVE and (flags & cv2.EVENT_FLAG_LBUTTON or flags & cv2.EVENT_FLAG_RBUTTON):
    #     # Only send mouse move if a button is down (dragging)
    #     send_event({"type":"mouse_move",  "x":x, "y":y})
    # elif event == cv2.EVENT_MOUSEMOVE:
    #     # Or send all mouse moves
    #     send_event({"type":"mouse_move",  "x":x, "y":y})

    # For now, send all mouse move events as per original, or if you had issues with this previously, keep it.
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
    elif event == cv2.EVENT_MBUTTONDOWN: # Middle button
        send_event({"type":"mouse_click","button":"middle","action":"down"})
    elif event == cv2.EVENT_MBUTTONUP: # Middle button
        send_event({"type":"mouse_click","button":"middle","action":"up"})
    elif event == cv2.EVENT_MOUSEWHEEL:
        # flags contains the wheel delta (e.g., 120 for scroll up, -120 for scroll down)
        # We need to send a simple direction or delta for the remote_machine
        if flags > 0: # Scroll up
            send_event({"type":"mouse_scroll", "direction": "up", "delta": flags})
        else: # Scroll down
            send_event({"type":"mouse_scroll", "direction": "down", "delta": flags})


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    global should_exit_viewer
    ip   = sys.argv[1] if len(sys.argv)>1 else "192.168.100.10"
    port = sys.argv[2] if len(sys.argv)>2 else "8765"

    # 1) Start networking in background
    t = threading.Thread(target=start_network, args=(ip, port), daemon=True)
    t.start()

    # 2) Prepare OpenCV window and mouse callback
    cv2.namedWindow("Remote Desktop", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Remote Desktop", on_mouse)

    # 3) Display & keyboard loop
    while not should_exit_viewer: # Loop until signalled to exit
        try:
            # Use get_nowait() to prevent blocking if queue is empty
            frame = frame_q.get_nowait()
            cv2.imshow("Remote Desktop", frame)
        except queue.Empty:
            pass # No frame yet, continue to check key presses and status

        key = cv2.waitKey(1) & 0xFF
        # Check for 'q' or window closure
        if key == ord('q') or cv2.getWindowProperty("Remote Desktop", cv2.WND_PROP_VISIBLE) < 1:
            print(f"[{datetime.now()}] 'q' pressed or window closed. Signalling exit.")
            should_exit_viewer = True # Set flag to true to break loop
            break # Break out of display loop

        # Only send key events if control channel is ready and a valid key is pressed
        elif control_ready.is_set() and key != 255: # 255 usually means no key pressed
            try:
                k = chr(key) # Get character from key code
                # Basic check for common printable ASCII characters
                if 32 <= key <= 126: # ASCII printable range
                    send_event({"type":"key","key":k,"action":"down"})
                    send_event({"type":"key","key":k,"action":"up"})
                else:
                    # Handle special keys. This is a basic example and might need expansion.
                    # For example, arrow keys, function keys etc., have specific key codes.
                    # You'd need to map these to strings that remote_machine.py understands (e.g., 'left_arrow').
                    # For simplicity, we'll just print them for now.
                    # print(f"[{datetime.now()}] Special key pressed: {key}")
                    pass # Ignore unmapped special keys for now to prevent errors
            except ValueError:
                # chr() can raise ValueError for invalid ASCII values
                pass
            except Exception as e:
                print(f"[{datetime.now()}] Error processing key event: {e}")

    # Clean up after loop exits
    cv2.destroyAllWindows()
    print("Viewer exiting cleanly…")

    # Signal the network thread to stop its loops by cancelling its tasks
    if network_loop and network_loop.is_running():
        # Schedule a coroutine to stop the loop
        async def _stop_network_tasks():
            tasks = [t for t in asyncio.all_tasks(network_loop) if t is not asyncio.current_task(network_loop)]
            for task in tasks:
                task.cancel() # Request tasks to cancel
            await asyncio.gather(*tasks, return_exceptions=True) # Await their cancellation
            network_loop.stop() # Stop the event loop itself

        try:
            # Schedule the shutdown coroutine on the network loop
            asyncio.run_coroutine_threadsafe(_stop_network_tasks(), network_loop)
        except RuntimeError:
            # This can happen if the loop is already shutting down or closed
            pass
        finally:
            # Give the network thread a moment to terminate
            if t.is_alive():
                t.join(timeout=2) # Wait up to 2 seconds for the thread to finish

    os._exit(0) # Force exit to ensure all threads are terminated

if __name__ == "__main__":
    main()