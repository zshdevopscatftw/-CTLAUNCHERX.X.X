#!/usr/bin/env python3
"""
CTLAUNCHER 1.0 [C] SAMSOFT 1999-2025 [MOJANG AB] [C]
TLauncher 2025 Style - One File, Auto-Download & Launch
"""
import tkinter as tk
from tkinter import ttk, messagebox
import json
import urllib.request
import shutil
import subprocess
import zipfile
import ssl
import threading
import sys
from pathlib import Path
import uuid

# SSL workaround for macOS/proxy issues
ssl._create_default_https_context = ssl._create_unverified_context

GAME_DIR = Path.home() / ".minecraft"
JAVA_BIN = "java"  # CHANGE TO JAVA 17+ IF NEEDED: e.g. "/opt/homebrew/opt/openjdk@17/bin/java"
SKIN_SERVER = "https://mc-heads.net"

class CTLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("CTLAUNCHER 1.0 [C] SAMSOFT 1999-2025 [MOJANG AB] [C]")
        self.root.geometry("1000x650")
        self.root.configure(bg="#0a0a0a")
        self.root.resizable(False, False)

        self.username = tk.StringVar(value="CatDev")
        self.version = tk.StringVar(value="1.20.1")
        self.ram = tk.IntVar(value=4)

        self.setup_theme()
        self.build_ui()
        self.load_versions()

    def setup_theme(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", background="#0a0a0a", foreground="#e0e0e0", font=("Segoe UI", 10))
        style.configure("TButton", background="#2e7d32", foreground="white", font=("Segoe UI", 11, "bold"), padding=8)
        style.map("TButton", background=[("active", "#388e3c")])
        style.configure("TEntry", fieldbackground="#1e1e1e", foreground="white", insertcolor="white")
        style.configure("TCombobox", fieldbackground="#1e1e1e", foreground="white")
        style.configure("TScale", background="#0a0a0a", troughcolor="#1e1e1e")

    def build_ui(self):
        # Sidebar
        sidebar = tk.Frame(self.root, bg="#111111", width=220)
        sidebar.pack(side="left", fill="y")
        tk.Label(sidebar, text="CTLAUNCHER", font=("Segoe UI", 20, "bold"), fg="#ffffff", bg="#111111").pack(pady=30)

        menu_items = ["Dashboard", "Versions", "Mods", "Settings", "Accounts", "Logout"]
        for text in menu_items:
            btn = tk.Button(sidebar, text=f"  {text}", font=("Segoe UI", 12), fg="#bbbbbb", bg="#111111", bd=0, anchor="w", padx=20, pady=10)
            btn.pack(fill="x")
            if text == "Dashboard":
                btn.config(fg="#4CAF50")

        # Main content
        main = tk.Frame(self.root, bg="#0a0a0a")
        main.pack(side="right", fill="both", expand=True)

        header = tk.Frame(main, bg="#1565c0", height=80)
        header.pack(fill="x")
        tk.Label(header, text="Dashboard", font=("Segoe UI", 24, "bold"), fg="white", bg="#1565c0").pack(pady=20)

        content = tk.Frame(main, bg="#0a0a0a")
        content.pack(fill="both", expand=True, padx=40, pady=20)

        # Username & Skin
        user_frame = tk.Frame(content, bg="#0a0a0a")
        user_frame.pack(side="left", padx=20, pady=20)
        ttk.Label(user_frame, text="Username").pack(anchor="w")
        ttk.Entry(user_frame, textvariable=self.username, width=30).pack(pady=5)
        self.skin_label = ttk.Label(user_frame, text="Skin Preview")
        self.skin_label.pack(pady=20)
        self.username.trace_add("write", lambda *args: self.update_skin_preview())

        # Version & RAM
        settings_frame = tk.Frame(content, bg="#0a0a0a")
        settings_frame.pack(side="right", padx=20, pady=20)
        ttk.Label(settings_frame, text="Version").pack(anchor="w")
        self.version_combo = ttk.Combobox(settings_frame, textvariable=self.version, state="readonly", width=25)
        self.version_combo.pack(pady=5)
        ttk.Label(settings_frame, text="Memory Allocation").pack(anchor="w", pady=10)
        ttk.Scale(settings_frame, from_=1, to=16, orient="horizontal", variable=self.ram, length=300).pack()
        self.ram_label = ttk.Label(settings_frame, text="4 GB")
        self.ram_label.pack(pady=5)
        self.ram.trace_add("write", self.update_ram_label)

        # Play button
        play_btn = ttk.Button(content, text="START MINECRAFT", command=self.play, style="TButton")
        play_btn.pack(pady=30, ipadx=40, ipady=15)

        # Status
        self.status = ttk.Label(content, text="Ready", foreground="#888888")
        self.status.pack(pady=5)
        self.progress = ttk.Progressbar(content, mode="indeterminate", length=500)
        self.progress.pack(pady=5)

    def update_ram_label(self, *args):
        self.ram_label.config(text=f"{self.ram.get()} GB")

    def update_skin_preview(self, *args):
        try:
            import requests
            from PIL import Image, ImageTk
            import io
            url = f"{SKIN_SERVER}/head/{self.username.get()}.png"
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).resize((128, 128))
                self.skin_photo = ImageTk.PhotoImage(img)
                self.skin_label.config(image=self.skin_photo, text="")
                return
        except:
            pass
        self.skin_label.config(text="Skin Preview", image="")

    def load_versions(self):
        try:
            url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
            with urllib.request.urlopen(url) as resp:
                data = json.loads(resp.read().decode())
            versions = [v["id"] for v in data["versions"] if v["type"] == "release"]
            self.version_combo["values"] = versions
        except:
            self.version_combo["values"] = ["1.20.1", "1.19.4"]

    def download_file(self, url: str, dest: Path):
        self.status.config(text=f"Downloading {url.split('/')[-1]}...")
        self.root.update()
        with urllib.request.urlopen(url) as resp, open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)

    def setup_version(self, version_id: str):
        version_dir = GAME_DIR / "versions" / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
        with urllib.request.urlopen(manifest_url) as resp:
            manifest = json.loads(resp.read().decode())
        for v in manifest["versions"]:
            if v["id"] == version_id:
                version_url = v["url"]
                break
        with urllib.request.urlopen(version_url) as resp:
            version_json = json.loads(resp.read().decode())

        version_json_path = version_dir / f"{version_id}.json"
        with open(version_json_path, "w") as f:
            json.dump(version_json, f)

        jar_path = version_dir / f"{version_id}.jar"
        if not jar_path.exists():
            self.download_file(version_json["downloads"]["client"]["url"], jar_path)

        libs_dir = GAME_DIR / "libraries"
        libs_dir.mkdir(parents=True, exist_ok=True)
        natives_dir = version_dir / "natives"
        natives_dir.mkdir(parents=True, exist_ok=True)

        self.status.config(text="Downloading libraries...")
        for lib in version_json["libraries"]:
            if "rules" in lib and not all(r.get("allowed", True) for r in lib["rules"]):
                continue
            if "downloads" in lib and "artifact" in lib["downloads"]:
                artifact = lib["downloads"]["artifact"]
                path = libs_dir / artifact["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    self.download_file(artifact["url"], path)
            if "natives" in lib:
                os_name = sys.platform.replace("win32", "windows").replace("darwin", "osx")
                classifier = lib["natives"].get(os_name)
                if classifier and "classifiers" in lib["downloads"]:
                    native = lib["downloads"]["classifiers"].get(classifier)
                    if native:
                        native_path = libs_dir / native["path"]
                        native_path.parent.mkdir(parents=True, exist_ok=True)
                        if not native_path.exists():
                            self.download_file(native["url"], native_path)
                        with zipfile.ZipFile(native_path, "r") as z:
                            for file in z.namelist():
                                if file.endswith((".so", ".dll", ".dylib", ".jnilib")):
                                    z.extract(file, natives_dir)

        assets_dir = GAME_DIR / "assets"
        index_path = assets_dir / "indexes" / f"{version_json['assetIndex']['id']}.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        if not index_path.exists():
            self.download_file(version_json["assetIndex"]["url"], index_path)

        self.status.config(text="Ready to launch!")

    def play(self):
        username = self.username.get().strip()
        if not username:
            messagebox.showerror("Error", "Enter a username!")
            return
        version = self.version.get()
        if not version:
            messagebox.showerror("Error", "Select a version!")
            return

        ram_gb = self.ram.get()
        max_ram = f"{ram_gb}G"

        self.progress.start()
        self.status.config(text="Preparing...")

        def launch_thread():
            error_msg = None
            try:
                version_dir = GAME_DIR / "versions" / version
                jar_path = version_dir / f"{version}.jar"
                version_json_path = version_dir / f"{version}.json"

                # Auto-download everything if missing
                if not jar_path.exists() or not version_json_path.exists():
                    self.root.after(0, lambda: self.status.config(text="Downloading game files..."))
                    self.setup_version(version)

                with open(version_json_path) as f:
                    version_json = json.load(f)

                natives_dir = version_dir / "natives"

                # FIXED: Full ordered classpath from version JSON
                classpath_parts = [str(jar_path)]
                for lib in version_json["libraries"]:
                    if "downloads" in lib and "artifact" in lib["downloads"]:
                        lib_path = GAME_DIR / "libraries" / lib["downloads"]["artifact"]["path"]
                        if lib_path.exists():
                            classpath_parts.append(str(lib_path))

                classpath = ":".join(classpath_parts)

                args = [
                    JAVA_BIN,
                    f"-Xmx{max_ram}",
                    f"-Xms1G",
                    "-Djava.library.path=" + str(natives_dir.resolve()),
                    "-cp", classpath,
                    "net.minecraft.client.main.Main",
                    "--username", username,
                    "--uuid", str(uuid.uuid3(uuid.NAMESPACE_DNS, f"OfflinePlayer:{username}")),
                    "--accessToken", "0",
                    "--userType", "legacy",
                    "--version", version,
                    "--gameDir", str(GAME_DIR.resolve()),
                    "--assetsDir", str((GAME_DIR / "assets").resolve()),
                    "--assetIndex", version_json["assetIndex"]["id"],
                ]

                self.root.after(0, lambda: self.status.config(text="Launching Minecraft..."))
                subprocess.run(args, check=True, cwd=str(GAME_DIR))
            except Exception as e:
                error_msg = str(e)
            finally:
                self.root.after(0, self.progress.stop)
                self.root.after(0, lambda: self.status.config(text="Ready"))
                if error_msg:
                    self.root.after(0, lambda msg=error_msg: messagebox.showerror("Error", msg))

        threading.Thread(target=launch_thread, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = CTLauncher(root)
    root.mainloop()
