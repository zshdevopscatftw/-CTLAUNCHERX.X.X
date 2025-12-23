#!/usr/bin/env python3
"""
CAT'S MC LAUNCHER 0.2 HDR - Auto-Download on Play
TLauncher-Style • Offline Mode • Full Auto-Install
Samsoft / Team Flames 2025
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
import hashlib
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# CONFIG
# ============================================================
LAUNCHER_VERSION = "0.2 HDR - Auto-Download"
WIDTH, HEIGHT = 900, 620

# Mojang API URLs
VERSION_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
RESOURCES_URL = "https://resources.download.minecraft.net"

# Colors
COLORS = {
    'bg_dark': '#1e1e2e',
    'bg_panel': '#252536',
    'bg_input': '#2d2d44',
    'accent': '#00d26a',
    'accent_hover': '#00ff7f',
    'text': '#ffffff',
    'text_dim': '#8888aa',
    'error': '#ff4757',
    'success': '#2ed573',
}

# Minecraft directory
MC_DIR = Path.home() / "Library" / "Application Support" / "minecraft" if platform.system() == "Darwin" else Path.home() / ".minecraft"

# SSL context
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# ============================================================
# DOWNLOAD MANAGER
# ============================================================
class DownloadManager:
    def __init__(self, mc_dir, status_callback=None, progress_callback=None):
        self.mc_dir = Path(mc_dir)
        self.status_callback = status_callback or (lambda x: print(x))
        self.progress_callback = progress_callback or (lambda x: None)
        self.cancelled = False

    def download_file(self, url, dest_path, expected_hash=None):
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if dest_path.exists() and expected_hash:
            with open(dest_path, 'rb') as f:
                file_hash = hashlib.sha1(f.read()).hexdigest()
            if file_hash == expected_hash:
                return True

        try:
            with urllib.request.urlopen(url, timeout=30, context=SSL_CONTEXT) as response:
                data = response.read()

            if expected_hash:
                file_hash = hashlib.sha1(data).hexdigest()
                if file_hash != expected_hash:
                    return False

            with open(dest_path, 'wb') as f:
                f.write(data)

            return True
        except Exception as e:
            self.status_callback(f"Download failed: {url} → {e}")
            return False

    def get_version_manifest(self):
        try:
            with urllib.request.urlopen(VERSION_MANIFEST_URL, timeout=30, context=SSL_CONTEXT) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            self.status_callback(f"Manifest fetch failed: {e}")
            return None

    def download_version(self, version_id):
        self.cancelled = False
        self.status_callback(f"Fetching {version_id} info...")
        self.progress_callback(5)

        manifest = self.get_version_manifest()
        if not manifest:
            return False

        version_url = None
        for v in manifest["versions"]:
            if v["id"] == version_id:
                version_url = v["url"]
                break

        if not version_url:
            self.status_callback(f"Version {version_id} not found!")
            return False

        version_dir = self.mc_dir / "versions" / version_id
        version_dir.mkdir(parents=True, exist_ok=True)
        json_path = version_dir / f"{version_id}.json"

        self.status_callback(f"Downloading {version_id}.json...")
        self.progress_callback(10)

        try:
            with urllib.request.urlopen(version_url, timeout=30, context=SSL_CONTEXT) as resp:
                version_data = json.loads(resp.read().decode())
            with open(json_path, 'w') as f:
                json.dump(version_data, f, indent=2)
        except Exception as e:
            self.status_callback(f"JSON download failed: {e}")
            return False

        if self.cancelled:
            return False

        # Client JAR
        self.status_callback(f"Downloading {version_id}.jar...")
        self.progress_callback(15)
        if 'downloads' in version_data and 'client' in version_data['downloads']:
            client = version_data['downloads']['client']
            jar_url = client.get('url')
            jar_hash = client.get('sha1')
            jar_path = version_dir / f"{version_id}.jar"
            if not self.download_file(jar_url, jar_path, jar_hash):
                self.status_callback("Client JAR download failed!")
                return False

        # Libraries & Natives
        self.status_callback("Downloading libraries...")
        libraries = version_data.get('libraries', [])
        total_libs = len(libraries)

        os_name = 'osx' if platform.system() == 'Darwin' else platform.system().lower()

        for i, lib in enumerate(libraries):
            if self.cancelled:
                return False
            progress = 20 + int((i / total_libs) * 40)
            self.progress_callback(progress)

            if not self._should_use_library(lib, os_name):
                continue

            if 'downloads' in lib:
                downloads = lib['downloads']
                if 'artifact' in downloads:
                    artifact = downloads['artifact']
                    url = artifact.get('url')
                    path = artifact.get('path')
                    sha1 = artifact.get('sha1')
                    if url and path:
                        dest = self.mc_dir / 'libraries' / path
                        self.download_file(url, dest, sha1)

                if 'classifiers' in downloads and 'natives' in lib:
                    native_key = lib['natives'].get(os_name, '')
                    if native_key in downloads['classifiers']:
                        native = downloads['classifiers'][native_key]
                        url = native.get('url')
                        path = native.get('path')
                        sha1 = native.get('sha1')
                        if url and path:
                            dest = self.mc_dir / 'libraries' / path
                            self.download_file(url, dest, sha1)
                            # Extract natives
                            natives_dir = version_dir / 'natives'
                            natives_dir.mkdir(parents=True, exist_ok=True)
                            with zipfile.ZipFile(dest, 'r') as z:
                                for file in z.namelist():
                                    if file.endswith((".so", ".dylib", ".jnilib")):
                                        z.extract(file, natives_dir)

        # Asset index
        self.status_callback("Downloading asset index...")
        self.progress_callback(65)
        if 'assetIndex' in version_data:
            asset_index = version_data['assetIndex']
            index_url = asset_index.get('url')
            index_id = asset_index.get('id')
            index_hash = asset_index.get('sha1')
            if index_url:
                index_path = self.mc_dir / 'assets' / 'indexes' / f'{index_id}.json'
                if not self.download_file(index_url, index_path, index_hash):
                    return False

        self.status_callback(f"{version_id} ready!")
        self.progress_callback(100)
        return True

    def _should_use_library(self, lib_data, os_name):
        if 'rules' not in lib_data:
            return True
        for rule in lib_data['rules']:
            action = rule.get('action', 'allow')
            if 'os' in rule:
                rule_os = rule['os'].get('name', '')
                if rule_os == os_name:
                    return action == 'allow'
        return True

# ============================================================
# LAUNCHER GUI
# ============================================================
class CatMCLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title(f"CAT'S MC LAUNCHER {LAUNCHER_VERSION}")
        self.root.geometry(f"{WIDTH}x{HEIGHT}")
        self.root.configure(bg=COLORS['bg_dark'])

        self.download_manager = DownloadManager(MC_DIR, self.update_status, self.update_progress)

        self.build_gui()

    def build_gui(self):
        main_frame = tk.Frame(self.root, bg=COLORS['bg_dark'])
        main_frame.pack(fill='both', expand=True)

        # Header
        header = tk.Frame(main_frame, bg=COLORS['bg_panel'], height=60)
        header.pack(fill='x')
        tk.Label(header, text=f"CAT'S MC LAUNCHER {LAUNCHER_VERSION}", font=('Segoe UI', 16, 'bold'),
                bg=COLORS['bg_panel'], fg=COLORS['accent']).pack(pady=15)

        # Content
        content = tk.Frame(main_frame, bg=COLORS['bg_dark'])
        content.pack(fill='both', expand=True, padx=20, pady=20)

        # Username
        ttk.Label(content, text="Username").pack(anchor='w')
        self.username_entry = ttk.Entry(content, width=40)
        self.username_entry.pack(pady=5, fill='x')

        # Version selector
        ttk.Label(content, text="Version").pack(anchor='w', pady=(10, 0))
        self.version_combo = ttk.Combobox(content, state="readonly", width=40)
        self.version_combo.pack(pady=5, fill='x')
        self.load_versions()

        # RAM slider
        ttk.Label(content, text="RAM Allocation").pack(anchor='w', pady=(10, 0))
        self.ram_scale = ttk.Scale(content, from_=1, to=32, orient="horizontal", length=400)
        self.ram_scale.set(4)
        self.ram_scale.pack(pady=5)
        self.ram_label = ttk.Label(content, text="4 GB")
        self.ram_label.pack()
        self.ram_scale.config(command=self.update_ram_label)

        # Play button
        self.play_btn = ttk.Button(content, text="▶  PLAY", command=self.play)
        self.play_btn.pack(pady=30, ipadx=30, ipady=15)

        # Status
        self.status_text = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(content, textvariable=self.status_text, foreground=COLORS['text_dim'])
        self.status_label.pack(pady=5)

        self.progress = ttk.Progressbar(content, mode="indeterminate", length=400)
        self.progress.pack(pady=5)

    def update_ram_label(self, value):
        self.ram_label.config(text=f"{int(float(value))} GB")

    def load_versions(self):
        try:
            with urllib.request.urlopen(VERSION_MANIFEST_URL, timeout=30, context=SSL_CONTEXT) as resp:
                data = json.loads(resp.read().decode())
            versions = [v["id"] for v in data["versions"] if v["type"] == "release"]
            self.version_combo["values"] = versions
            # Auto-select latest release
            self.version_combo.current(0)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load versions: {e}")
            self.version_combo["values"] = ["1.21.3", "1.20.6", "1.19.4"]
            self.version_combo.current(0)

    def update_status(self, text):
        self.status_text.set(text)
        self.root.update_idletasks()

    def update_progress(self, value):
        self.progress['value'] = value
        self.root.update_idletasks()

    def play(self):
        version = self.version_combo.get()
        username = self.username_entry.get().strip() or f"Player{random.randint(1000,9999)}"

        if not version:
            messagebox.showwarning("No Version", "Select a version first!")
            return

        self.progress.start()
        self.update_status(f"Preparing {version}...")

        def launch_task():
            try:
                version_dir = MC_DIR / "versions" / version
                jar_path = version_dir / f"{version}.jar"

                if not jar_path.exists():
                    self.update_status(f"Downloading {version}...")
                    self.download_manager.download_version(version)

                # Build launch args
                natives_dir = version_dir / "natives"
                classpath = self._build_classpath(version)

                args = [
                    "java",
                    f"-Xmx{int(self.ram_scale.get())}G",
                    f"-Xms1G",
                    f"-Djava.library.path={natives_dir}",
                    "-cp", classpath,
                    "net.minecraft.client.main.Main",
                    "--username", username,
                    "--uuid", str(uuid.uuid3(uuid.NAMESPACE_DNS, f"OfflinePlayer:{username}")),
                    "--accessToken", "0",
                    "--userType", "legacy",
                    "--version", version,
                    "--gameDir", str(MC_DIR),
                    "--assetsDir", str(MC_DIR / "assets"),
                    "--assetIndex", version,
                ]

                self.update_status("Launching Minecraft...")
                subprocess.run(args, check=True, cwd=str(MC_DIR))
                self.update_status("Game closed")
            except Exception as e:
                self.update_status(f"Launch failed: {str(e)}")
            finally:
                self.progress.stop()

        threading.Thread(target=launch_task, daemon=True).start()

    def _build_classpath(self, version):
        version_json_path = MC_DIR / "versions" / version / f"{version}.json"
        if not version_json_path.exists():
            return str(MC_DIR / "versions" / version / f"{version}.jar")

        with open(version_json_path) as f:
            version_json = json.load(f)

        classpath = [str(MC_DIR / "versions" / version / f"{version}.jar")]

        for lib in version_json.get("libraries", []):
            if "downloads" in lib and "artifact" in lib["downloads"]:
                path = MC_DIR / "libraries" / lib["downloads"]["artifact"]["path"]
                if path.exists():
                    classpath.append(str(path))

        return ":".join(classpath)

if __name__ == "__main__":
    root = tk.Tk()
    app = CatMCLauncher(root)
    root.mainloop()
