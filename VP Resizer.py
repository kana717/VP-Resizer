import os
import cv2
import threading
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog
from PIL import Image, ImageSequence
import subprocess
import imageio_ffmpeg
import time

PHOTO_RESOLUTIONS = {
    "Original": None,
    "1440p": (2560, 1440),
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "480p": (854, 480),
    "360p": (640, 360),
    "240p": (426, 240),
    "144p": (256, 144),
}

VIDEO_RESOLUTIONS = PHOTO_RESOLUTIONS.copy()

PHOTO_EXTENSIONS = (
    "jpg", "jpeg", "png", "bmp", "tiff", "tif", "webp", "gif", "heic", "ico"
)

VIDEO_EXTENSIONS = (
    "mp4", "avi", "mov", "mkv", "wmv", "flv", "mpg", "mpeg", "3gp", "webm"
)

def clamp_even_dimension(value, min_val=64):
    value = max(value, min_val)
    if value % 2 != 0:
        value -= 1
    return value

def parse_custom_resolution(text):
    text = text.strip().lower()
    if "x" in text:
        try:
            w, h = map(int, text.split("x"))
        except:
            return None
    else:
        if "p" in text:
            text = text.replace("p", "")
        try:
            h = int(text)
            ratio = 16 / 9
            w = int(h * ratio)
        except:
            return None
    w = clamp_even_dimension(w)
    h = clamp_even_dimension(h)
    return (w, h)

def resize_gif(file_path, target_size):
    try:
        original_size = os.path.getsize(file_path)
        base, ext = os.path.splitext(file_path)
        temp_file = base + ".tmp" + ext  # e.g. "file.tmp.gif"

        # Remove old temp file if exists
        if os.path.exists(temp_file):
            os.remove(temp_file)

        with Image.open(file_path) as img:
            frames = []

            orig_w, orig_h = img.size
            if target_size:
                target_w, target_h = target_size
                ratio = min(target_w / orig_w, target_h / orig_h)
                new_w = int(orig_w * ratio)
                new_h = int(orig_h * ratio)
                new_w = clamp_even_dimension(new_w)
                new_h = clamp_even_dimension(new_h)
            else:
                new_w, new_h = orig_w, orig_h

            for frame in ImageSequence.Iterator(img):
                frame = frame.convert("RGBA")
                resized_frame = frame.resize((new_w, new_h), Image.Resampling.LANCZOS)
                frames.append(resized_frame)

            frames[0].save(
                temp_file,
                save_all=True,
                append_images=frames[1:],
                loop=img.info.get("loop", 0),
                duration=img.info.get("duration", 100),
                disposal=2,
            )

        # Small delay to ensure file handles are released
        time.sleep(0.1)

        new_size = os.path.getsize(temp_file)
        if new_size <= original_size:
            # Delete original before renaming new one
            try:
                os.remove(file_path)
            except Exception:
                pass

            # Small delay before rename
            time.sleep(0.1)

            try:
                os.replace(temp_file, file_path)
            except Exception:
                pass
            return "Finished", original_size / (1024 * 1024), new_size / (1024 * 1024)
        else:
            try:
                os.remove(temp_file)
            except Exception:
                pass
            return "Skipped (resized larger)", original_size / (1024 * 1024), original_size / (1024 * 1024)
    except Exception as e:
        return f"Finished (error ignored for GIF)", 0, 0

def resize_image(file_path, target_size):
    try:
        original_size = os.path.getsize(file_path)
        base, ext = os.path.splitext(file_path)
        ext = ext.lower()

        if ext == ".gif":
            return resize_gif(file_path, target_size)
        else:
            with Image.open(file_path) as img:
                if target_size:
                    orig_w, orig_h = img.size
                    target_w, target_h = target_size

                    ratio = min(target_w / orig_w, target_h / orig_h)
                    new_w = int(orig_w * ratio)
                    new_h = int(orig_h * ratio)

                    new_w = clamp_even_dimension(new_w)
                    new_h = clamp_even_dimension(new_h)

                    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                temp_file = base + ".tmp" + ext
                img.save(temp_file)

            time.sleep(0.1)

            new_size = os.path.getsize(temp_file)
            if new_size <= original_size:
                os.replace(temp_file, file_path)
                return "Finished", original_size / (1024 * 1024), new_size / (1024 * 1024)
            else:
                os.remove(temp_file)
                return "Skipped (resized larger)", original_size / (1024 * 1024), original_size / (1024 * 1024)

    except Exception as e:
        return f"Skipped (error: {e})", 0, 0

def resize_video(file_path, target_size):
    try:
        original_size = os.path.getsize(file_path) / (1024 * 1024)
        if not target_size:
            return "Skipped (invalid resolution)", 0, 0

        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return "Skipped (can't open video)", 0, 0
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        target_w, target_h = target_size
        ratio = min(target_w / orig_w, target_h / orig_h)
        new_w = int(orig_w * ratio)
        new_h = int(orig_h * ratio)

        new_w = clamp_even_dimension(new_w)
        new_h = clamp_even_dimension(new_h)

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        base, ext = os.path.splitext(file_path)
        ext = ext.lower()
        temp_file = base + ".tmp" + ext

        command = [
            ffmpeg_exe,
            "-i", file_path,
            "-vf", f"scale={new_w}:{new_h}",
            "-c:a", "copy",
            "-y", temp_file
        ]

        subprocess.run(command, check=True)

        # Small delay
        time.sleep(0.1)

        new_size = os.path.getsize(temp_file) / (1024 * 1024)
        if new_size <= original_size:
            os.replace(temp_file, file_path)
            return "Finished", original_size, new_size
        else:
            os.remove(temp_file)
            return "Skipped (resized larger)", original_size, original_size
    except subprocess.CalledProcessError as e:
        return f"Skipped (ffmpeg error: {e})", 0, 0
    except Exception as e:
        return f"Skipped (error: {e})", 0, 0

def process_folder(folder_path, photo_text, video_text):
    total_original_size = 0
    total_new_size = 0
    photo_target_size = parse_custom_resolution(photo_text)
    video_target_size = parse_custom_resolution(video_text)

    files = [f for f in os.listdir(folder_path) if f.lower().endswith(PHOTO_EXTENSIONS + VIDEO_EXTENSIONS) and ".tmp" not in f.lower()]
    total_files = len(files)

    for index, file in enumerate(files):
        file_path = os.path.join(folder_path, file)
        log_message(f"Processing: {file}")
        ext = file.lower().split('.')[-1]
        if ext in PHOTO_EXTENSIONS:
            status, original_size, new_size = resize_image(file_path, photo_target_size)
        else:
            status, original_size, new_size = resize_video(file_path, video_target_size)
        log_message(f"{status}: {file}")
        total_original_size += original_size
        total_new_size += new_size
        update_progress(index + 1, total_files, total_original_size, total_new_size)

class ResizerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Media Resizer")
        self.geometry("650x550")

        self.folder_path = tk.StringVar()
        self.photo_mode = tk.StringVar(value="menu")
        self.video_mode = tk.StringVar(value="menu")
        self.photo_value = tk.StringVar(value="Original")
        self.video_value = tk.StringVar(value="Original")

        tk.Button(self, text="Select Folder", command=self.browse_folder).pack(pady=5)

        # PHOTO SECTION
        self.photo_frame = tk.Frame(self)
        self.photo_frame.pack(pady=5)
        tk.Label(self.photo_frame, text="Photo Resolution").pack(side=tk.LEFT)
        self.photo_menu = tk.OptionMenu(self.photo_frame, self.photo_value, *PHOTO_RESOLUTIONS.keys())
        self.photo_entry = tk.Entry(self.photo_frame, textvariable=self.photo_value, width=12)
        self.photo_toggle = tk.Button(self.photo_frame, text="✏", width=2, command=self.toggle_photo)
        self.photo_menu.pack(side=tk.LEFT)
        self.photo_toggle.pack(side=tk.RIGHT)

        # VIDEO SECTION
        self.video_frame = tk.Frame(self)
        self.video_frame.pack(pady=5)
        tk.Label(self.video_frame, text="Video Resolution").pack(side=tk.LEFT)
        self.video_menu = tk.OptionMenu(self.video_frame, self.video_value, *VIDEO_RESOLUTIONS.keys())
        self.video_entry = tk.Entry(self.video_frame, textvariable=self.video_value, width=12)
        self.video_toggle = tk.Button(self.video_frame, text="✏", width=2, command=self.toggle_video)
        self.video_menu.pack(side=tk.LEFT)
        self.video_toggle.pack(side=tk.RIGHT)

        # CONTROLS
        control_frame = tk.Frame(self)
        control_frame.pack(pady=10)
        self.start_button = tk.Button(control_frame, text="▶", command=self.start_processing)
        self.pause_button = tk.Button(control_frame, text="⏸")
        self.stop_button = tk.Button(control_frame, text="⏹")
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.pause_button.pack(side=tk.LEFT, padx=5)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # PROGRESS
        tk.Label(self, text="Total Progress").pack()
        self.total_progress = tk.DoubleVar()
        self.total_progress_bar = ttk.Progressbar(self, variable=self.total_progress, mode="determinate", length=400)
        self.total_progress_bar.pack()
        self.total_task_label = tk.Label(self, text="0/0")
        self.total_task_label.pack()
        self.size_label = tk.Label(self, text="Total Saved: 0 MB")
        self.size_label.pack()

        # LOGS
        self.log_text = tk.Text(self, height=10, state="disabled", wrap="none")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

    def browse_folder(self):
        self.folder_path.set(filedialog.askdirectory())

    def toggle_photo(self):
        if self.photo_mode.get() == "menu":
            self.photo_menu.pack_forget()
            self.photo_entry.pack(side=tk.LEFT)
            self.photo_toggle.pack(side=tk.RIGHT)
            self.photo_mode.set("entry")
        else:
            self.photo_entry.pack_forget()
            self.photo_menu.pack(side=tk.LEFT)
            self.photo_toggle.pack(side=tk.RIGHT)
            self.photo_mode.set("menu")

    def toggle_video(self):
        if self.video_mode.get() == "menu":
            self.video_menu.pack_forget()
            self.video_entry.pack(side=tk.LEFT)
            self.video_toggle.pack(side=tk.RIGHT)
            self.video_mode.set("entry")
        else:
            self.video_entry.pack_forget()
            self.video_menu.pack(side=tk.LEFT)
            self.video_toggle.pack(side=tk.RIGHT)
            self.video_mode.set("menu")

    def start_processing(self):
        folder = self.folder_path.get()
        photo = self.photo_value.get()
        video = self.video_value.get()
        if not folder:
            log_message("No folder selected.")
            return
        threading.Thread(target=process_folder, args=(folder, photo, video), daemon=True).start()

def update_progress(current, total, original_size, new_size):
    progress_percent = (current / total) * 100 if total else 0
    app.total_progress.set(progress_percent)
    app.total_progress_bar.update()
    app.total_task_label.config(text=f"{current}/{total}")
    saved_size = round(original_size - new_size, 2)
    app.size_label.config(text=f"Total Saved: {saved_size} MB")

def log_message(msg):
    app.log_text.config(state="normal")
    app.log_text.insert("end", msg + "\n")
    app.log_text.see("end")
    app.log_text.config(state="disabled")

app = ResizerApp()
app.mainloop()
