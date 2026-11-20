#!/usr/bin/python3
"""Supervise bundled processes, using app-private IPC across Flatpak instances."""
import fcntl
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

BASE = Path('/app/share/juhradial')
runtime = Path(os.environ['XDG_RUNTIME_DIR']) / 'app' / os.environ['FLATPAK_ID']
runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
# KWin needs a host-visible script path; the app runtime is already shared.
os.environ['TMPDIR'] = str(runtime)
settings = [sys.executable, str(BASE / 'settings-qt/main.py')]
control_path = runtime / 'supervisor.sock'
lock = (runtime / 'supervisor.lock').open('w')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    for command in ('restart-daemon', 'restart-overlay', 'quit'):
        if '--' + command in sys.argv:
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(3)
                client.connect(str(control_path))
                client.sendall(command.encode())
            sys.exit(0)
    if '--background' in sys.argv:
        sys.exit(0)
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(3)
        client.connect(str(control_path))
        client.sendall(b'settings')
    sys.exit(0)

if '--quit' in sys.argv:
    sys.exit(0)

# Do not mix a native installation's daemon with this app's private config.
for name in ('org.kde.juhradialmx', 'org.kde.juhradialmx.overlay'):
    check = subprocess.run(['dbus-send', '--session', '--print-reply',
                            '--dest=org.freedesktop.DBus', '/org/freedesktop/DBus',
                            'org.freedesktop.DBus.NameHasOwner', 'string:' + name],
                           capture_output=True, text=True, timeout=3)
    if check.returncode or 'boolean true' in check.stdout:
        sys.exit('Session bus unavailable or another JuhRadial instance is running: ' + name)

control_path.unlink(missing_ok=True)
control = socket.socket(socket.AF_UNIX)
control.bind(str(control_path))
os.chmod(control_path, 0o600)
control.listen(4)
control.settimeout(.2)
children = []
stopping = False

def stop(*_):
    global stopping
    stopping = True

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

def launch(command):
    child = subprocess.Popen(command)
    children.append(child)
    return child

def terminate(child):
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()

config = Path(os.environ['XDG_CONFIG_HOME']) / 'juhradial/config.json'
daemon_command = ['/app/bin/juhradiald', '--config', str(config)]
overlay_command = [sys.executable, str(BASE / 'juhradial-overlay.py')]
daemon = launch(daemon_command)
overlay = launch(overlay_command)
if not any(arg in sys.argv for arg in ('--background', '--restart-daemon', '--restart-overlay')):
    launch(settings + sys.argv[1:])
try:
    failures = 0
    while not stopping and overlay.poll() is None:
        try:
            client, _ = control.accept()
        except socket.timeout:
            client = None
        if client is not None:
            with client:
                client.settimeout(1)
                try:
                    command = client.recv(64).decode('ascii')
                except (TimeoutError, UnicodeError):
                    command = ''
            if command == 'settings':
                launch(settings)
            elif command == 'quit':
                stopping = True
            elif command == 'restart-overlay':
                terminate(overlay)
                overlay = launch(overlay_command)
            elif command == 'restart-daemon':
                terminate(daemon)
                daemon = launch(daemon_command)
                failures = 0
        if daemon.poll() is not None:
            if daemon.returncode == 0 or failures >= 3:
                print('Daemon stopped or repeatedly failed; stopping bundled processes', flush=True)
                break
            failures += 1
            print(f'Daemon exited ({daemon.returncode}); restarting', flush=True)
            time.sleep(1)
            if not stopping:
                daemon = launch(daemon_command)
finally:
    for child in children:
        terminate(child)
    control.close()
    control_path.unlink(missing_ok=True)
    # These transient scripts were loaded by our daemon, not installed on disk.
    for plugin in ('juhradialmx-active-window', 'juhradialmx-cursor-screen'):
        subprocess.run(['dbus-send', '--session', '--print-reply', '--dest=org.kde.KWin',
                        '/Scripting', 'org.kde.kwin.Scripting.unloadScript', 'string:' + plugin],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
