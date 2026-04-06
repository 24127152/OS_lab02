import tkinter as tk
class StartMenuScene(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg="#1e1e1e")
        self.app = app

        title = tk.Label(
            self, text="FAT32 Scheduler Simulator",
            font=("Segoe UI", 36, "bold"),
            fg="white", bg="#1e1e1e"
        )
        title.pack(pady=(120, 12))

        subtitle = tk.Label(
            self, text="Lab02 Project",
            font=("Segoe UI", 14, "bold"),
            fg="#cfcfcf", bg="#1e1e1e"
        )
        subtitle.pack(pady=(0, 40))

        #Nút start
        btn_start = tk.Button(
            self, text="Start",
            font=("Segoe UI", 12, "bold"),
            width=18,
            command=lambda: self.app.show_scene("MainScene")
        )
        btn_start.pack(pady=10)

        btn_exit = tk.Button(
            self, text="Exit",
            font=("Segoe UI", 12, "bold"),
            width=18,
            command=self.app.destroy
        )
        btn_exit.pack(pady=10)