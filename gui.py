# gui_launcher.py

import tkinter as tk
from tkinter import messagebox
import socket
import threading
import subprocess
import sys

class LauncherGUI:
    def __init__(self, master):
        self.master = master
        master.title("Remote Desktop Launcher")

        # Role selection
        self.role_var = tk.StringVar(value="client")
        tk.Radiobutton(master, text="Connect to Remote", variable=self.role_var,
                       value="client", command=self._render_frame).pack(anchor="w")
        tk.Radiobutton(master, text="Be Remote Machine", variable=self.role_var,
                       value="server", command=self._render_frame).pack(anchor="w")

        # Container for dynamic frame
        self.frame = tk.Frame(master)
        self.frame.pack(fill="both", expand=True, pady=10)

        # Other controls
        self._render_frame()

    def _render_frame(self):
        # Clear old widgets
        for w in self.frame.winfo_children():
            w.destroy()

        role = self.role_var.get()
        if role == "client":
            tk.Label(self.frame, text="Server IP:").grid(row=0, column=0, sticky="e")
            self.ip_entry = tk.Entry(self.frame)
            self.ip_entry.insert(0, "192.168.100.10")
            self.ip_entry.grid(row=0, column=1)

            tk.Label(self.frame, text="Port:").grid(row=1, column=0, sticky="e")
            self.port_entry = tk.Entry(self.frame)
            self.port_entry.insert(0, "8765")
            self.port_entry.grid(row=1, column=1)

            tk.Button(self.frame, text="Connect",
                      command=self.start_client).grid(row=2, columnspan=2, pady=5)
        else:
            local_ip = self._get_local_ip()
            tk.Label(self.frame, text=f"Local IP: {local_ip}").pack()

            tk.Label(self.frame, text="Override IP (optional):").pack()
            self.override_entry = tk.Entry(self.frame)
            self.override_entry.pack()
            self.override_entry.insert(0, local_ip)

            tk.Label(self.frame, text="Port:").pack()
            self.port_entry = tk.Entry(self.frame)
            self.port_entry.insert(0, "8765")
            self.port_entry.pack()

            tk.Button(self.frame, text="Start Server",
                      command=self.start_server).pack(pady=5)

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = "127.0.0.1"
        return ip

    def start_client(self):
        ip = self.ip_entry.get().strip()
        port = self.port_entry.get().strip()
        # Launch viewer.py with arguments
        cmd = [sys.executable, "viewer.py", ip, port]
        subprocess.Popen(cmd)
        self.master.destroy()

    def start_server(self):
        ip = self.override_entry.get().strip()
        port = self.port_entry.get().strip()
        # Launch remote_machine.py with arguments
        cmd = [sys.executable, "remote_machine.py", ip, port]
        subprocess.Popen(cmd)
        self.master.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    app = LauncherGUI(root)
    root.mainloop()
