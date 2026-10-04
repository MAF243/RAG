"""Run the personal backend and Streamlit UI using the active Python environment."""

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


def port_number(value):
    number = int(value)
    if not 1024 <= number <= 65535:
        raise argparse.ArgumentTypeError("Gunakan port 1024–65535.")
    return number


def main():
    parser = argparse.ArgumentParser(
        description="Jalankan Teman Belajar lokal. Ctrl+C menghentikan kedua server."
    )
    parser.add_argument("--backend-port", type=port_number, default=8000)
    parser.add_argument("--ui-port", type=port_number, default=8501)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if args.backend_port == args.ui_port:
        parser.error("Port backend dan UI harus berbeda.")
    for port in (args.backend_port, args.ui_port):
        with socket.socket() as connection:
            try:
                connection.bind(("127.0.0.1", port))
            except OSError:
                parser.error(f"Port {port} sedang dipakai. Tutup server lama atau pilih port lain.")
    project = Path(__file__).resolve().parent
    env = os.environ.copy()
    env["RAG_API_URL"] = f"http://127.0.0.1:{args.backend_port}/api/v1"
    commands = [
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.backend_port),
            "--workers",
            "1",
            "--no-proxy-headers",
        ],
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "ui/app.py",
            "--server.address",
            "127.0.0.1",
            "--server.port",
            str(args.ui_port),
            "--server.headless",
            "true",
        ],
    ]
    processes = []

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    # This launcher only probes its own loopback server, without external proxies.
    local_http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        backend = subprocess.Popen(commands[0], cwd=project, env=env)
        processes.append(backend)
        deadline = time.monotonic() + 30
        while True:
            if backend.poll() is not None:
                raise RuntimeError("Backend gagal dimulai. Periksa pesan di atas.")
            try:
                with local_http.open(
                    f"http://127.0.0.1:{args.backend_port}/health", timeout=1
                ) as response:
                    if response.status == 200:
                        break
            except (urllib.error.URLError, TimeoutError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Backend belum siap setelah 30 detik.") from None
                time.sleep(0.3)
        processes.append(subprocess.Popen(commands[1], cwd=project, env=env))
        url = f"http://127.0.0.1:{args.ui_port}"
        print(f"\nTeman Belajar: {url}\nTekan Ctrl+C untuk berhenti.\n", flush=True)
        if not args.no_browser:
            # Wait until Streamlit is listening before opening the browser.
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if processes[-1].poll() is not None:
                    raise RuntimeError("UI gagal dimulai. Periksa pesan di atas.")
                try:
                    with local_http.open(url + "/_stcore/health", timeout=1) as response:
                        if response.status == 200:
                            webbrowser.open(url)
                            break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(0.3)
        while all(process.poll() is None for process in processes):
            time.sleep(0.3)
        raise RuntimeError("Salah satu server berhenti. Periksa pesan di atas.")
    except KeyboardInterrupt:
        print("\nMenghentikan Teman Belajar…")
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    return 0


if __name__ == "__main__":
    sys.exit(main())
