import tkinter as tk
from tkinter import messagebox
import socket
import subprocess
import sys
import os

class LauncherGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AnyDesk Clone Launcher")
        self.geometry("300x200")
        self.resizable(False, False)

        # Role selection
        self.role_var = tk.StringVar(value="client")
        tk.Radiobutton(self, text="Connect to Remote", variable=self.role_var,
                       value="client", command=self.render_frame).pack(anchor="w", padx=10, pady=5)
        tk.Radiobutton(self, text="Be Remote Machine", variable=self.role_var,
                       value="server", command=self.render_frame).pack(anchor="w", padx=10)

        # Dynamic frame container
        self.frm = tk.Frame(self)
        self.frm.pack(padx=10, pady=10)

        self.viewer_process = None
        self.render_frame()

    def render_frame(self):
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
            self.port_entry.insert(0, "8765")
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
        base = os.path.dirname(os.path.abspath(__file__))
        viewer_path = os.path.join(base, "viewer.py")
        cmd = [sys.executable, viewer_path, ip, port]
        try:
            # Pass a flag to viewer.py to indicate it was launched by the GUI
            self.viewer_process = subprocess.Popen(cmd, cwd=base)
            self.withdraw() # Hide the main GUI window
            self.monitor_viewer_process() # Start monitoring the viewer process
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start viewer:\n{e}")
            return

    def monitor_viewer_process(self):
        if self.viewer_process and self.viewer_process.poll() is None:
            # Viewer process is still running, check again after a delay
            self.after(1000, self.monitor_viewer_process)
        else:
            # Viewer process has terminated, show the GUI again
            self.show_initial_page()

    def show_initial_page(self):
        self.deiconify() # Show the main GUI window
        self.render_frame() # Render the initial role selection

    def disconnect(self):
        if self.viewer_process and self.viewer_process.poll() is None:
            self.viewer_process.terminate()
            self.viewer_process = None
        self.show_initial_page() # Show initial page after disconnect

    def start_server(self):
        ip = self.override_entry.get().strip()
        port = self.port_entry.get().strip()
        base = os.path.dirname(os.path.abspath(__file__))
        server_path = os.path.join(base, "remote_machine.py")
        cmd = [sys.executable, server_path, ip, port]
        try:
            subprocess.Popen(cmd, cwd=base, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start server:\n{e}")
            return
        messagebox.showinfo("Launched", f"Server started on {ip}:{port}")

if __name__ == '__main__':
    app = LauncherGUI()
    app.mainloop()