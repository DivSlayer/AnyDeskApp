import tkinter as tk
from tkinter import messagebox
import socket
import subprocess
import sys
import os
import cv2

from get_local_ip import get_private_ip_and_subnet

class LauncherGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AnyDesk Clone Launcher")
        self.geometry("300x250")
        self.resizable(False, False)
        self.local_ip, subnet = get_private_ip_and_subnet()
        # Role selection
        self.role_var = tk.StringVar(value="client")
        self.client_radio = tk.Radiobutton(self, text="Connect to Remote", variable=self.role_var,
                       value="client", command=self.render_frame)
        self.client_radio.pack(anchor="w", padx=10, pady=5)
        self.server_radio = tk.Radiobutton(self, text="Be Remote Machine", variable=self.role_var,
                       value="server", command=self.render_frame)
        self.server_radio.pack(anchor="w", padx=10)

        # Dynamic frame container
        self.frm = tk.Frame(self)
        self.frm.pack(padx=10, pady=10)

        self.viewer_process = None
        self.server_process = None
        self.render_frame()

    def render_frame(self):
        for widget in self.frm.winfo_children():
            widget.destroy()

        role = self.role_var.get()
        if role == "client":
            tk.Label(self.frm, text="Server IP:").grid(row=0, column=0, sticky="e")
            self.ip_entry = tk.Entry(self.frm)
            self.ip_entry.insert(0, self.local_ip)
            self.ip_entry.grid(row=0, column=1)

            tk.Label(self.frm, text="Port:").grid(row=1, column=0, sticky="e")
            self.port_entry = tk.Entry(self.frm)
            self.port_entry.insert(0, "8000")
            self.port_entry.grid(row=1, column=1)

            self.connect_btn = tk.Button(self.frm, text="Connect",
                      command=self.start_client)
            self.connect_btn.grid(row=2, column=0, columnspan=2, pady=10)
        else:
            local_ip = self.get_local_ip()
            tk.Label(self.frm, text=f"Local IP: {local_ip}").pack()

            tk.Label(self.frm, text="Override IP (optional):").pack(pady=(5,0))
            self.override_entry = tk.Entry(self.frm)
            self.override_entry.insert(0, local_ip)
            self.override_entry.pack()

            tk.Label(self.frm, text="Port:").pack(pady=(5,0))
            self.port_entry = tk.Entry(self.frm)
            self.port_entry.insert(0, "8765")
            self.port_entry.pack()

            self.server_btn = tk.Button(self.frm, text="Start Server",
                      command=self.start_server)
            self.server_btn.pack(pady=10)

    def disable_role_selection(self):
        self.client_radio.config(state="disabled")
        self.server_radio.config(state="disabled")

    def enable_role_selection(self):
        self.client_radio.config(state="normal")
        self.server_radio.config(state="normal")

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except:
            ip = self.local_ip
        return ip

    def start_client(self):
        ip = self.ip_entry.get().strip()
        port = self.port_entry.get().strip()
        base = os.path.dirname(os.path.abspath(__file__))
        viewer_path = os.path.join(base, "viewer.py")
        cmd = [sys.executable, viewer_path, ip, port]
        try:
            self.viewer_process = subprocess.Popen(cmd, cwd=base)
            self.show_client_connected(ip, port)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start viewer:\n{e}")
            return

    def show_client_connected(self, ip, port):
        for widget in self.frm.winfo_children():
            widget.destroy()
        
        tk.Label(self.frm, text=f"Connected to {ip}:{port}", font=("Arial", 12, "bold")).pack(pady=20)
        tk.Button(self.frm, text="Disconnect", command=self.disconnect_client, 
                 bg="red", fg="white", font=("Arial", 10, "bold")).pack(pady=10)
        
        # Disable role selection
        self.disable_role_selection()
        
        # Monitor the viewer process
        self.monitor_viewer_process()

    def disconnect_client(self):
        if self.viewer_process and self.viewer_process.poll() is None:
            self.viewer_process.terminate()
            self.viewer_process = None
        self.show_initial_page()

    def monitor_viewer_process(self):
        if self.viewer_process and self.viewer_process.poll() is None:
            # Viewer process is still running, check again after a delay
            self.after(1000, self.monitor_viewer_process)
        else:
            # Viewer process has terminated, show the GUI again
            self.show_initial_page()

    def show_initial_page(self):
        # Re-enable role selection
        self.enable_role_selection()
        self.render_frame()

    def start_server(self):
        ip = self.override_entry.get().strip()
        port = self.port_entry.get().strip()
        base = os.path.dirname(os.path.abspath(__file__))
        server_path = os.path.join(base, "remote_machine.py")
        cmd = [sys.executable, server_path, ip, port]
        try:
            self.server_process = subprocess.Popen(cmd, cwd=base, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.show_server_running(ip, port)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start server:\n{e}")
            return

    def show_server_running(self, ip, port):
        for widget in self.frm.winfo_children():
            widget.destroy()
        
        tk.Label(self.frm, text=f"Server Running", font=("Arial", 14, "bold")).pack(pady=(20,5))
        tk.Label(self.frm, text=f"Address: {ip}:{port}", font=("Arial", 10)).pack(pady=5)
        tk.Label(self.frm, text="Waiting for connections...", font=("Arial", 9)).pack(pady=5)
        tk.Button(self.frm, text="Stop Server", command=self.stop_server).pack(pady=15)

        # Disable role selection
        self.disable_role_selection()

    def stop_server(self):
        if self.server_process and self.server_process.poll() is None:
            self.server_process.terminate()
            self.server_process = None
        self.show_initial_page()

if __name__ == '__main__':
    app = LauncherGUI()
    app.mainloop()