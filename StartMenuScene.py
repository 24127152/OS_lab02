import tkinter as tk




class StartMenuScene(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg="#1e1e1e")
        self.app = app

        self.content_frame = tk.Frame(self, bg="#1e1e1e")
        self.content_frame.pack(expand=True)

        title = tk.Label(
            self.content_frame,
            text="FAT32 Scheduler Simulator",
            font=("Segoe UI", 36, "bold"),
            fg="white",
            bg="#1e1e1e",
        )
        title.pack(pady=(0, 12))

        subtitle = tk.Label(
            self.content_frame,
            text="Lab02 Project",
            font=("Segoe UI", 14, "bold"),
            fg="#cfcfcf",
            bg="#1e1e1e",
        )
        subtitle.pack(pady=(0, 32))

        btn_start = tk.Button(
            self.content_frame,
            text="Start",
            font=("Segoe UI", 12, "bold"),
            width=18,
            fg="white",
            bg="#2a2a2a",
            activeforeground="white",
            activebackground="#3b3b3b",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: self.app.show_scene("MainScene"),
        )
        btn_start.pack(pady=8)

        btn_exit = tk.Button(
            self.content_frame,
            text="Exit",
            font=("Segoe UI", 12, "bold"),
            width=18,
            fg="white",
            bg="#2a2a2a",
            activeforeground="white",
            activebackground="#3b3b3b",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.app.destroy,
        )
        btn_exit.pack(pady=8)

        self._bind_hover(btn_start)
        self._bind_hover(btn_exit)

    def _bind_hover(self, button):
        normal_bg = "#2a2a2a"
        hover_bg = "#4a4a4a"
        button.bind("<Enter>", lambda _e: button.config(bg=hover_bg))
        button.bind("<Leave>", lambda _e: button.config(bg=normal_bg))
