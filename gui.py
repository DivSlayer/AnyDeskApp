# gui.py

import tkinter as tk
from tkinter import messagebox
import socket
import subprocess
import sys

class LauncherGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AnyDesk Clone Launcher")

        # Role selection
        self.role_var = tk.StringVar(value="client")
        tk.Radiobutton(self, text="Connect to Remote", variable=self.role_var,
                       value="client", command=self.render_frame).pack(anchor="w", padx=10, pady=5)
        tk.Radiobutton(self, text="Be Remote Machine", variable=self.role_var,
                       value="server", command=self.render_frame).pack(anchor="w", padx=10)

        # Dynamic frame container
        self.frm = tk.Frame(self)
        self.frm.pack(padx=10, pady=10)

        self.render_frame()

    def render_frame(self):
        # Clean up
        for widget in self.frm.winfo_children():
            widget.destroy()

        role = self.role_var.get()
        if role == "client":
            tk.Label(self.frm, text="Server IP:").grid(row=0, column=0, sticky="e")
            self.ip_entry = tk.Entry(self.frm)
            self.ip_entry.insert(0, "127.0.0.1")
            self.ip_entry.grid(row=0, column=1)

            tk.Label(self.frm, text="Port:").grid(row=1, column=0, sticky="e")
            self.port_entry = tk.Entry(self.frm)
            self.port_entry.insert(0, "8000")
            self.port_entry.grid(row=1, column=1)

            tk.Button(self.frm, text="Connect",
                      command=self.start_client).grid(row=2, column=0, columnspan=2, pady=10)
        else:
            local_ip = self.get_local_ip()
            tk.Label(self.frm, text=f"Local IP: {local_ip}").pack()

            tk.Label(self.frm, text="Override IP (optional):").pack(pady=(5,0))
            self.override_entry = tk.Entry(self.frm)
            self.override_entry.insert(0, local_ip)
            self.override_entry.pack()

            tk.Label(self.frm, text="Port:").pack(pady=(5,0))
            self.port_entry = tk.Entry(self.frm)
            self.port_entry.insert(0, "8000")
            self.port_entry.pack()

            tk.Button(self.frm, text="Start Server",
                      command=self.start_server).pack(pady=10)

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except:
            ip = "127.0.0.1"
        return ip

    def start_client(self):
        ip = self.ip_entry.get().strip()
        port = self.port_entry.get().strip()
        cmd = [sys.executable, "viewer.py", ip, port]
        try:
            subprocess.Popen(cmd)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start viewer:\n{e}")
            return
        self.destroy()

    def start_server(self):
        ip = self.override_entry.get().strip()
        port = self.port_entry.get().strip()
        cmd = [sys.executable, "remote_machine.py", ip, port]
        try:
            subprocess.Popen(cmd)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start server:\n{e}")
            return
        self.destroy()

if __name__ == '__main__':
    app = LauncherGUI()
    app.mainloop()
