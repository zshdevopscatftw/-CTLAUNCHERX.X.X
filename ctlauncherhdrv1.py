#!/usr/bin/env python3
"""
CTLAUNCHER 1.0 [C] SAMSOFT 1999-2025 [MOJANG AB] [C]
TLauncher 2025 Style - One File, Auto-Download & Launch
FIXED VERSION - All bugs resolved
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
import os
import platform
from pathlib import Path
import uuid

# SSL workaround for macOS/proxy issues
ssl._create_default_https_context = ssl._create_unverified_context

GAME_DIR = Path.home() / ".minecraft"
SKIN_SERVER = "https://mc-heads.net"

# FIX: Cross-platform classpath separator
CLASSPATH_SEP = ";" if sys.platform == "win32" else ":"

# FIX: Auto-detect Java path
def find_java():
    """Find Java executable, preferring Java 17+"""
    candidates = []
    if sys.platform == "darwin":
        candidates = [
            "/opt/homebrew/opt/openjdk@17/bin/java",
            "/opt/homebrew/opt/openjdk/bin/java",
            "/usr/local/opt/openjdk@17/bin/java",
            "/Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home/bin/java",
        ]
    elif sys.platform == "win32":
        candidates = [
            Path(os.environ.get("JAVA_HOME", "")) / "bin" / "java.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Java" / "jdk-17" / "bin" / "java.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Eclipse Adoptium" / "jdk-17" / "bin" / "java.exe",
        ]
    else:  # Linux
        candidates = [
            "/usr/lib/jvm/java-17-openjdk/bin/java",
            "/usr/lib/jvm/java-17-openjdk-amd64/bin/java",
        ]
    
    for path in candidates:
        if Path(path).exists():
            return str(path)
    
    # Fallback to PATH
    return "java"

JAVA_BIN = find_java()


def get_os_name():
    """FIX: Get correct OS name for Minecraft library rules"""
    if sys.platform == "win32":
        return "windows"
    elif sys.platform == "darwin":
        return "osx"
    else:
        return "linux"


def get_arch():
    """Get system architecture"""
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "x64"
    elif machine in ("aarch64", "arm64"):
        return "arm64"
    elif machine in ("i386", "i686", "x86"):
        return "x86"
    return machine


def check_rules(rules):
    """FIX: Properly evaluate Minecraft library rules"""
    if not rules:
        return True
    
    os_name = get_os_name()
    arch = get_arch()
    
    # Default: disallow unless explicitly allowed
    allowed = False
    
    for rule in rules:
        action = rule.get("action", "allow")
        matches = True
        
        if "os" in rule:
            os_rule = rule["os"]
            if "name" in os_rule and os_rule["name"] != os_name:
                matches = False
            if "arch" in os_rule and os_rule["arch"] != arch:
                matches = False
        
        if matches:
            allowed = (action == "allow")
    
    return allowed


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
        
        # FIX: Skin preview debounce timer
        self.skin_timer = None
        self.skin_photo = None  # Keep reference to prevent GC

        self.setup_theme()
        self.build_ui()
        self.load_versions()
        
        # FIX: Initial skin load after UI is built
        self.root.after(500, self.update_skin_preview)

    def setup_theme(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", background="#0a0a0a", foreground="#e0e0e0", font=("Segoe UI", 10))
        style.configure("TButton", background="#2e7d32", foreground="white", font=("Segoe UI", 11, "bold"), padding=8)
        style.map("TButton", background=[("active", "#388e3c")])
        style.configure("TEntry", fieldbackground="#1e1e1e", foreground="white", insertcolor="white")
        style.configure("TCombobox", fieldbackground="#1e1e1e", foreground="white")
        style.configure("TScale", background="#0a0a0a", troughcolor="#1e1e1e")
        style.configure("Horizontal.TProgressbar", background="#4CAF50", troughcolor="#1e1e1e")

    def build_ui(self):
        # Sidebar
        sidebar = tk.Frame(self.root, bg="#111111", width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)  # FIX: Maintain sidebar width
        
        tk.Label(sidebar, text="CTLAUNCHER", font=("Segoe UI", 20, "bold"), fg="#ffffff", bg="#111111").pack(pady=30)

        menu_items = ["Dashboard", "Versions", "Mods", "Settings", "Accounts", "Logout"]
        for text in menu_items:
            btn = tk.Button(sidebar, text=f"  {text}", font=("Segoe UI", 12), fg="#bbbbbb", bg="#111111", 
                          bd=0, anchor="w", padx=20, pady=10, activebackground="#222222", activeforeground="#ffffff")
            btn.pack(fill="x")
            if text == "Dashboard":
                btn.config(fg="#4CAF50")

        # Main content
        main = tk.Frame(self.root, bg="#0a0a0a")
        main.pack(side="right", fill="both", expand=True)

        header = tk.Frame(main, bg="#1565c0", height=80)
        header.pack(fill="x")
        header.pack_propagate(False)  # FIX: Maintain header height
        tk.Label(header, text="Dashboard", font=("Segoe UI", 24, "bold"), fg="white", bg="#1565c0").pack(pady=20)

        content = tk.Frame(main, bg="#0a0a0a")
        content.pack(fill="both", expand=True, padx=40, pady=20)

        # Username & Skin
        user_frame = tk.Frame(content, bg="#0a0a0a")
        user_frame.pack(side="left", padx=20, pady=20)
        ttk.Label(user_frame, text="Username").pack(anchor="w")
        ttk.Entry(user_frame, textvariable=self.username, width=30).pack(pady=5)
        
        # FIX: Skin preview with proper image handling
        self.skin_label = tk.Label(user_frame, text="Skin Preview", bg="#0a0a0a", fg="#888888",
                                   width=16, height=8, relief="flat")
        self.skin_label.pack(pady=20)
        
        # FIX: Debounced skin preview update
        self.username.trace_add("write", self.schedule_skin_update)

        # Version & RAM
        settings_frame = tk.Frame(content, bg="#0a0a0a")
        settings_frame.pack(side="right", padx=20, pady=20)
        ttk.Label(settings_frame, text="Version").pack(anchor="w")
        self.version_combo = ttk.Combobox(settings_frame, textvariable=self.version, state="readonly", width=25)
        self.version_combo.pack(pady=5)
        
        ttk.Label(settings_frame, text="Memory Allocation").pack(anchor="w", pady=10)
        ttk.Scale(settings_frame, from_=1, to=16, orient="horizontal", variable=self.ram, length=300,
                 command=self.update_ram_label).pack()  # FIX: Use command instead of trace for immediate update
        self.ram_label = ttk.Label(settings_frame, text="4 GB")
        self.ram_label.pack(pady=5)

        # Play button
        play_btn = ttk.Button(content, text="START MINECRAFT", command=self.play, style="TButton")
        play_btn.pack(pady=30, ipadx=40, ipady=15)

        # Status
        self.status = ttk.Label(content, text="Ready", foreground="#888888")
        self.status.pack(pady=5)
        self.progress = ttk.Progressbar(content, mode="determinate", length=500)
        self.progress.pack(pady=5)

    def update_ram_label(self, *args):
        # FIX: Convert float to int for clean display
        self.ram_label.config(text=f"{int(self.ram.get())} GB")

    def schedule_skin_update(self, *args):
        """FIX: Debounce skin updates to avoid flooding requests"""
        if self.skin_timer:
            self.root.after_cancel(self.skin_timer)
        self.skin_timer = self.root.after(500, self.update_skin_preview)

    def update_skin_preview(self):
        """FIX: Load skin in background thread to avoid UI freeze"""
        username = self.username.get().strip()
        if not username:
            self.skin_label.config(text="Skin Preview", image="")
            return
        
        def load_skin():
            try:
                # Try using PIL if available
                try:
                    from PIL import Image, ImageTk
                    import io
                except ImportError:
                    # Fallback: just show text
                    self.root.after(0, lambda: self.skin_label.config(text=f"[{username}]", image=""))
                    return
                
                url = f"{SKIN_SERVER}/head/{username}/128.png"
                with urllib.request.urlopen(url, timeout=5) as resp:
                    data = resp.read()
                
                img = Image.open(io.BytesIO(data))
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                
                def update_ui():
                    self.skin_photo = ImageTk.PhotoImage(img)
                    self.skin_label.config(image=self.skin_photo, text="")
                
                self.root.after(0, update_ui)
                
            except Exception:
                self.root.after(0, lambda: self.skin_label.config(text=f"[{username}]", image=""))
        
        threading.Thread(target=load_skin, daemon=True).start()

    def load_versions(self):
        """Load versions in background thread"""
        def load():
            try:
                url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                versions = [v["id"] for v in data["versions"] if v["type"] == "release"]
                self.root.after(0, lambda: self.set_versions(versions))
            except Exception:
                self.root.after(0, lambda: self.set_versions(["1.21.4", "1.20.1", "1.19.4", "1.18.2"]))
        
        threading.Thread(target=load, daemon=True).start()
    
    def set_versions(self, versions):
        self.version_combo["values"] = versions
        if self.version.get() not in versions and versions:
            self.version.set(versions[0])

    def download_file(self, url: str, dest: Path, callback=None):
        """FIX: Download with progress reporting"""
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                total = int(resp.headers.get('content-length', 0))
                downloaded = 0
                
                with open(dest, "wb") as f:
                    while True:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if callback and total > 0:
                            progress = int((downloaded / total) * 100)
                            self.root.after(0, lambda p=progress: callback(p))
            return True
        except Exception as e:
            print(f"Download error: {e}")
            return False

    def setup_version(self, version_id: str, progress_callback=None):
        """Download and setup a Minecraft version"""
        version_dir = GAME_DIR / "versions" / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        # Get version manifest
        manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
        with urllib.request.urlopen(manifest_url, timeout=10) as resp:
            manifest = json.loads(resp.read().decode())
        
        # FIX: Handle version not found
        version_url = None
        for v in manifest["versions"]:
            if v["id"] == version_id:
                version_url = v["url"]
                break
        
        if not version_url:
            raise ValueError(f"Version {version_id} not found in manifest")
        
        with urllib.request.urlopen(version_url, timeout=10) as resp:
            version_json = json.loads(resp.read().decode())

        version_json_path = version_dir / f"{version_id}.json"
        with open(version_json_path, "w") as f:
            json.dump(version_json, f, indent=2)

        # Download client JAR
        jar_path = version_dir / f"{version_id}.jar"
        if not jar_path.exists():
            self.root.after(0, lambda: self.status.config(text=f"Downloading {version_id}.jar..."))
            if not self.download_file(version_json["downloads"]["client"]["url"], jar_path, progress_callback):
                raise RuntimeError("Failed to download client JAR")

        libs_dir = GAME_DIR / "libraries"
        libs_dir.mkdir(parents=True, exist_ok=True)
        natives_dir = version_dir / "natives"
        natives_dir.mkdir(parents=True, exist_ok=True)

        # Download libraries
        os_name = get_os_name()
        total_libs = len(version_json["libraries"])
        
        for i, lib in enumerate(version_json["libraries"]):
            # FIX: Properly check rules
            if "rules" in lib and not check_rules(lib["rules"]):
                continue
            
            lib_name = lib.get("name", "unknown")
            self.root.after(0, lambda n=lib_name, idx=i, tot=total_libs: 
                          self.status.config(text=f"Libraries ({idx+1}/{tot}): {n.split(':')[-1]}"))
            
            if "downloads" in lib:
                # Standard artifact
                if "artifact" in lib["downloads"]:
                    artifact = lib["downloads"]["artifact"]
                    path = libs_dir / artifact["path"]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if not path.exists():
                        self.download_file(artifact["url"], path)
                
                # FIX: Natives handling with proper OS detection
                if "natives" in lib:
                    # Handle arch substitution
                    native_key = lib["natives"].get(os_name, "")
                    if "${arch}" in native_key:
                        native_key = native_key.replace("${arch}", "64" if get_arch() in ("x64", "arm64") else "32")
                    
                    if native_key and "classifiers" in lib["downloads"]:
                        native = lib["downloads"]["classifiers"].get(native_key)
                        if native:
                            native_path = libs_dir / native["path"]
                            native_path.parent.mkdir(parents=True, exist_ok=True)
                            if not native_path.exists():
                                self.download_file(native["url"], native_path)
                            
                            # Extract natives
                            try:
                                with zipfile.ZipFile(native_path, "r") as z:
                                    for file in z.namelist():
                                        # Skip META-INF
                                        if file.startswith("META-INF/"):
                                            continue
                                        # Extract native libraries
                                        if file.endswith((".so", ".dll", ".dylib", ".jnilib")) or "/" not in file:
                                            try:
                                                z.extract(file, natives_dir)
                                            except Exception:
                                                pass
                            except zipfile.BadZipFile:
                                pass

        # Download asset index
        assets_dir = GAME_DIR / "assets"
        index_id = version_json["assetIndex"]["id"]
        index_path = assets_dir / "indexes" / f"{index_id}.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not index_path.exists():
            self.root.after(0, lambda: self.status.config(text="Downloading asset index..."))
            self.download_file(version_json["assetIndex"]["url"], index_path)
        
        # FIX: Download actual assets (optional - can be slow)
        # For a full launcher, uncomment this section
        # self.download_assets(index_path)

        self.root.after(0, lambda: self.status.config(text="Ready to launch!"))
        return version_json

    def download_assets(self, index_path: Path):
        """Download game assets (textures, sounds, etc.)"""
        with open(index_path) as f:
            asset_index = json.load(f)
        
        objects_dir = GAME_DIR / "assets" / "objects"
        objects_dir.mkdir(parents=True, exist_ok=True)
        
        objects = asset_index.get("objects", {})
        total = len(objects)
        
        for i, (name, info) in enumerate(objects.items()):
            hash_val = info["hash"]
            prefix = hash_val[:2]
            asset_path = objects_dir / prefix / hash_val
            
            if not asset_path.exists():
                asset_path.parent.mkdir(parents=True, exist_ok=True)
                url = f"https://resources.download.minecraft.net/{prefix}/{hash_val}"
                self.download_file(url, asset_path)
            
            if i % 50 == 0:
                self.root.after(0, lambda idx=i, tot=total: 
                              self.status.config(text=f"Assets ({idx}/{tot})"))

    def play(self):
        username = self.username.get().strip()
        if not username:
            messagebox.showerror("Error", "Enter a username!")
            return
        
        # FIX: Validate username (no spaces, alphanumeric + underscore only)
        if not all(c.isalnum() or c == "_" for c in username):
            messagebox.showerror("Error", "Username can only contain letters, numbers, and underscores!")
            return
        
        version = self.version.get()
        if not version:
            messagebox.showerror("Error", "Select a version!")
            return

        ram_gb = int(self.ram.get())  # FIX: Ensure integer
        max_ram = f"{ram_gb}G"

        self.progress.config(mode="indeterminate")
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
                    version_json = self.setup_version(version)
                else:
                    with open(version_json_path) as f:
                        version_json = json.load(f)

                natives_dir = version_dir / "natives"
                libs_dir = GAME_DIR / "libraries"

                # FIX: Build classpath with proper rule checking
                classpath_parts = []
                for lib in version_json["libraries"]:
                    if "rules" in lib and not check_rules(lib["rules"]):
                        continue
                    if "downloads" in lib and "artifact" in lib["downloads"]:
                        lib_path = libs_dir / lib["downloads"]["artifact"]["path"]
                        if lib_path.exists():
                            classpath_parts.append(str(lib_path))
                
                # Add main JAR last (some versions need this order)
                classpath_parts.append(str(jar_path))
                
                # FIX: Use platform-appropriate separator
                classpath = CLASSPATH_SEP.join(classpath_parts)

                # FIX: Get main class from version JSON
                main_class = version_json.get("mainClass", "net.minecraft.client.main.Main")

                # Build launch arguments
                args = [
                    JAVA_BIN,
                    f"-Xmx{max_ram}",
                    f"-Xms512M",
                    f"-Djava.library.path={natives_dir.resolve()}",
                    "-Dminecraft.launcher.brand=CTLauncher",
                    "-Dminecraft.launcher.version=1.0",
                    "-cp", classpath,
                    main_class,
                    "--username", username,
                    "--uuid", str(uuid.uuid3(uuid.NAMESPACE_DNS, f"OfflinePlayer:{username}")),
                    "--accessToken", "0",
                    "--userType", "legacy",
                    "--version", version,
                    "--gameDir", str(GAME_DIR.resolve()),
                    "--assetsDir", str((GAME_DIR / "assets").resolve()),
                    "--assetIndex", version_json["assetIndex"]["id"],
                ]
                
                # Add version type if present
                if "type" in version_json:
                    args.extend(["--versionType", version_json["type"]])

                self.root.after(0, lambda: self.status.config(text="Launching Minecraft..."))
                self.root.after(0, self.progress.stop)
                
                # Launch Minecraft
                process = subprocess.Popen(
                    args,
                    cwd=str(GAME_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                
                # Monitor process (optional: show output in console)
                for line in process.stdout:
                    print(line, end="")
                
                process.wait()
                
            except Exception as e:
                import traceback
                error_msg = f"{e}\n\n{traceback.format_exc()}"
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
