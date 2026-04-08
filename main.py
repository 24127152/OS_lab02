import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from fat32_reader import FAT32Reader
from scheduler import run_scheduler_for_selected_txt
from StartMenuScene import StartMenuScene
#MainScene chứa giao diện chính của ứng dụng, cho phép người dùng tải ảnh FAT32, xem thông tin boot sector, danh sách file .txt và chạy scheduler trên file đã chọn
class MainScene(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        self.image_path_var = tk.StringVar()
        self.reader = None
        self.txt_files = []

        self._build_ui()

    #Hàm xử lý sự kiện khi người dùng nhấn nút Export Results
    def on_export_result(self):
        content = self.result_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("No Output", "There is no scheduler output to export.")
            return

        txt_path = self._selected_txt_path() or "N/A"
        image_path = self.image_path_var.get().strip() or "N/A"

        save_path = filedialog.asksaveasfilename(
            title="Export Scheduler Result",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")]
        )
        if not save_path:
            return

        export_text = (
            "Lab02 Scheduler Export\n"
            "=====================\n"
            f"Image: {image_path}\n"
            f"Selected TXT: {txt_path}\n\n"
            "Scheduler Output\n"
            "----------------\n"
            f"{content}\n"
        )

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(export_text)
            messagebox.showinfo("Export Success", f"Saved to:\n{save_path}")
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc))

    #Hàm xây dựng UI chính
    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)

        ttk.Button(top, text="Back to Menu", command=lambda: self.app.show_scene("StartMenuScene")).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Label(top, text="Image Path:").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.image_path_var, width=78).pack(side=tk.LEFT, padx=8)
        ttk.Button(top, text="Browse", command=self.on_browse).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Load", command=self.on_load).pack(side=tk.LEFT, padx=4)

        mid = ttk.Frame(self, padding=(10, 0, 10, 0))
        mid.pack(fill=tk.BOTH, expand=True)

        boot_box = ttk.LabelFrame(mid, text="Boot Sector", padding=8)
        boot_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        self.boot_tree = ttk.Treeview(boot_box, columns=("field", "value"), show="headings", height=12)
        self.boot_tree.heading("field", text="Field")
        self.boot_tree.heading("value", text="Value")
        self.boot_tree.column("field", width=260, anchor=tk.W)
        self.boot_tree.column("value", width=160, anchor=tk.W)
        self.boot_tree.pack(fill=tk.BOTH, expand=True)

        txt_box = ttk.LabelFrame(mid, text="TXT Files", padding=8)
        txt_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        self.txt_tree = ttk.Treeview(
            txt_box,
            columns=("path", "name", "created_date", "created_time", "size"),
            show="headings",
            height=12,
        )
        self.txt_tree.heading("path", text="Path")
        self.txt_tree.heading("name", text="Name")
        self.txt_tree.heading("created_date", text="Date")
        self.txt_tree.heading("created_time", text="Time")
        self.txt_tree.heading("size", text="Size")
        self.txt_tree.column("path", width=320, anchor=tk.W)
        self.txt_tree.column("name", width=130, anchor=tk.W)
        self.txt_tree.column("created_date", width=90, anchor=tk.W)
        self.txt_tree.column("created_time", width=90, anchor=tk.W)
        self.txt_tree.column("size", width=80, anchor=tk.E)
        self.txt_tree.pack(fill=tk.BOTH, expand=True)

        buttons = ttk.Frame(self, padding=10)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="Show TXT Details", command=self.on_show_txt_details).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Run Scheduler", command=self.on_run_scheduler).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Export Results", command=self.on_export_result).pack(side=tk.LEFT, padx=8)

        detail_box = ttk.LabelFrame(self, text="Selected TXT Details", padding=8)
        detail_box.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.detail_var = tk.StringVar(value="No file selected.")
        ttk.Label(detail_box, textvariable=self.detail_var).pack(anchor=tk.W)

        result_box = ttk.LabelFrame(self, text="Scheduler Output", padding=8)
        result_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.result_text = tk.Text(result_box, height=16, wrap=tk.NONE)
        self.result_text.pack(fill=tk.BOTH, expand=True)

    #Hàm xóa nội dung Treeview cũ
    def _clear_tree(self, tree):
        for item in tree.get_children():
            tree.delete(item)

    def _selected_txt_path(self):
        selected_items = self.txt_tree.selection()
        selected = selected_items[0] if selected_items else self.txt_tree.focus()
        if not selected:
            return None
        values = self.txt_tree.item(selected, "values")
        return values[0] if values else None

    def on_browse(self):
        path = filedialog.askopenfilename(title="Select FAT32 image", filetypes=[("Image files", "*.img")])
        if path:
            self.image_path_var.set(path)

    def on_load(self):
        path = self.image_path_var.get().strip()
        if not path:
            messagebox.showwarning("Missing Path", "Please choose an image file first.")
            return

        self.reader = FAT32Reader(path)
        info = self.reader.read_boot_sector()
        if not isinstance(info, dict):
            messagebox.showerror("Load Error", str(info))
            return

        self._clear_tree(self.boot_tree)
        with open(path, "rb") as fsrc:
            root_chain = self.reader.read_cluster_chain(fsrc, info["root_cluster"])
        rdet_sectors = len(root_chain) * info["sectors_per_cluster"]

        boot_rows = [
            ("Bytes per sector", info["bytes_per_sector"]),
            ("Sectors per cluster", info["sectors_per_cluster"]),
            ("Number of sectors in Boot Sector region", info["reserved_sectors"]),
            ("Number of FAT tables", info["nums_of_fats"]),
            ("Number of sectors per FAT table", info["sectors_per_fat"]),
            ("Number of sectors for the RDET", rdet_sectors),
            ("Total number of sectors on the disk", info["total_sectors"]),
        ]
        for field, value in boot_rows:
            self.boot_tree.insert("", tk.END, values=(field, value))

        self.txt_files = self.reader.list_all_txt_files()
        self._clear_tree(self.txt_tree)
        for item in self.txt_files:
            self.txt_tree.insert(
                "",
                tk.END,
                values=(
                    item.get("path", ""),
                    item.get("name", ""),
                    item.get("created_date", "N/A"),
                    item.get("created_time", "N/A"),
                    item.get("size", 0),
                ),
            )

        if not self.txt_files:
            messagebox.showinfo("No TXT", "Loaded image, but no .txt files were found.")

        self.detail_var.set("No file selected.")
        self.result_text.delete("1.0", tk.END)

    def on_show_txt_details(self):
        if self.reader is None:
            messagebox.showwarning("Not Loaded", "Please load an image first.")
            return

        txt_path = self._selected_txt_path()
        if not txt_path:
            messagebox.showwarning("No Selection", "Please select one .txt file.")
            return

        details = self.reader.get_txt_file_details(txt_path)
        if not details:
            messagebox.showerror("Error", "Cannot load selected txt file details.")
            return

        self.detail_var.set(
            f"Name: {details['name']} | Date: {details['created_date']} | "
            f"Time: {details['created_time']} | Size: {details['size']} bytes"
        )

    def on_run_scheduler(self):
        if self.reader is None:
            messagebox.showwarning("Not Loaded", "Please load an image first.")
            return

        txt_path = self._selected_txt_path()
        if not txt_path:
            messagebox.showwarning("No Selection", "Please select one .txt file.")
            return

        logs = []

        def collector(msg):
            logs.append(str(msg))

        result = run_scheduler_for_selected_txt(self.reader, txt_path, print_fn=collector)
        if not result:
            messagebox.showerror("Error", "Failed to run scheduler for selected file.")
            return

        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, "\n".join(logs))


#Lớp app quản lý scene
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Lab02 FAT32 Scheduler")
        self.geometry("1200x780")
        self.container = tk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for Scene in (StartMenuScene, MainScene):
            frame = Scene(parent=self.container, app=self)
            self.frames[Scene.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_scene("StartMenuScene")

    def show_scene(self, scene_name):
        #Chuyển đổi giữa các scene
        frame = self.frames[scene_name]
        frame.tkraise()

def main():
    app = App()
    app.mainloop()



if __name__ == "__main__":
    main()
