#!/usr/bin/env python3
"""
Virtual Printer — TCP listener that saves received print jobs to files.

Listens on a TCP port and saves every received payload to a timestamped file
in an output directory. Useful for testing without a physical printer.

Usage:
    python virtual_printer.py                  # port 9200, saves to ./print_jobs/
    python virtual_printer.py --port 9300
    python virtual_printer.py --port 9200 --output C:\\PrintJobs

Install requirements:
    pip install colorama    # optional — for coloured console output

The saved filename encodes the timestamp and job number:
    print_job_20260222_201500_001.bin   — raw ZPL/RAW bytes
    print_job_20260222_201500_002.pdf   — PDF (detected from %PDF header)
    print_job_20260222_201500_003.zpl   — ZPL (detected from ^XA header)
"""

import argparse
import os
import socket
import threading
import datetime
import sys

# Optional coloured output
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    def ok(msg):   print(Fore.GREEN  + f'[✓] {msg}' + Style.RESET_ALL)
    def info(msg): print(Fore.CYAN   + f'[i] {msg}' + Style.RESET_ALL)
    def warn(msg): print(Fore.YELLOW + f'[!] {msg}' + Style.RESET_ALL)
    def err(msg):  print(Fore.RED    + f'[✗] {msg}' + Style.RESET_ALL)
except ImportError:
    def ok(msg):   print(f'[OK] {msg}')
    def info(msg): print(f'[..] {msg}')
    def warn(msg): print(f'[!!] {msg}')
    def err(msg):  print(f'[XX] {msg}')


_job_counter = 0
_counter_lock = threading.Lock()


def _next_job_number() -> int:
    global _job_counter
    with _counter_lock:
        _job_counter += 1
        return _job_counter


def _detect_extension(data: bytes) -> str:
    if data.startswith(b'%PDF'):
        return '.pdf'
    if data.lstrip().startswith(b'^XA') or b'^XA' in data[:20]:
        return '.zpl'
    return '.bin'


def handle_connection(conn: socket.socket, addr: tuple, output_dir: str):
    job_num = _next_job_number()
    ip, port = addr
    info(f'Connection #{job_num:03d} from {ip}:{port}')

    try:
        chunks = []
        conn.settimeout(3.0)
        while True:
            try:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            except socket.timeout:
                break

        data = b''.join(chunks)
        if not data:
            warn(f'Connection #{job_num:03d} — no data received')
            return

        ext = _detect_extension(data)
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'print_job_{ts}_{job_num:03d}{ext}'
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'wb') as f:
            f.write(data)

        ok(f'Job #{job_num:03d} saved — {len(data):,} bytes → {filepath}')

        # Print first 200 chars as text preview (useful for ZPL)
        try:
            preview = data[:200].decode('ascii', errors='replace').replace('\r', '').replace('\n', ' ')
            info(f'Preview: {preview}')
        except Exception:
            pass

    except Exception as e:
        err(f'Error handling connection #{job_num:03d}: {e}')
    finally:
        conn.close()


def start_server(port: int, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind(('0.0.0.0', port))
    except OSError as e:
        err(f'Cannot bind to port {port}: {e}')
        sys.exit(1)

    server.listen(10)
    ok(f'Virtual Printer listening on port {port}')
    info(f'Saving jobs to: {os.path.abspath(output_dir)}')
    info('Press Ctrl+C to stop\n')

    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(
                target=handle_connection,
                args=(conn, addr, output_dir),
                daemon=True,
            )
            t.start()
    except KeyboardInterrupt:
        info('Stopped.')
    finally:
        server.close()


def main():
    parser = argparse.ArgumentParser(
        description='Virtual Printer — saves TCP print jobs to files'
    )
    parser.add_argument(
        '--port', type=int, default=9200,
        help='TCP port to listen on (default: 9200)'
    )
    parser.add_argument(
        '--output', default='print_jobs',
        help='Directory to save print jobs (default: ./print_jobs)'
    )
    args = parser.parse_args()
    start_server(args.port, args.output)


if __name__ == '__main__':
    main()
