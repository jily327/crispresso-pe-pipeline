"""Generate a report with Python socket and DNS APIs denied before reporter import."""
import argparse
import errno
import json
from pathlib import Path
import socket

attempts = []


def denied(*args, **kwargs):
    attempts.append('network API')
    raise OSError(errno.ENETUNREACH, 'Network is unavailable for the offline qualification')


class OfflineSocket(socket.socket):
    connect = denied
    connect_ex = denied
    sendto = denied
    sendmsg = denied


socket.socket = OfflineSocket
socket.create_connection = denied
socket.getaddrinfo = denied

from peanalyzer.reporting import generate_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    manifest = generate_report(result_path=args.result, output=args.output)
    assert attempts == []
    value = dict(status='PASS', network_attempts=len(attempts),
        isolation='Python socket connection, datagram and DNS APIs denied before reporting import',
        report_artifacts=len(manifest.artifacts), package_version=manifest.package_version,
        kernel_network_namespace=False)
    args.evidence.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')
    print('PASS: offline report generation with no network attempts')


if __name__ == '__main__':
    main()
