from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request

from command_dispatch import dispatch_command


def _queue_url(base_url: str, script: str) -> str:
    return f"{base_url.rstrip('/')}/{script}"


def _request(
    method: str,
    url: str,
    token: str,
    body: dict | None = None,
) -> tuple[int, bytes]:
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _dequeue(base_url: str, token: str) -> dict | None:
    status, payload = _request("GET", _queue_url(base_url, "dequeue.php"), token)
    if status == 204:
        return None
    if status != 200:
        raise RuntimeError(f"dequeue failed with status {status}: {payload.decode('utf-8', 'replace')}")
    job = json.loads(payload.decode("utf-8"))
    if not isinstance(job, dict):
        raise RuntimeError("dequeue returned invalid json")
    return job


def _ack(base_url: str, token: str, job_id: int, status: str) -> None:
    ack_status, payload = _request(
        "POST",
        _queue_url(base_url, "ack.php"),
        token,
        {"id": job_id, "status": status},
    )
    if ack_status != 200:
        raise RuntimeError(f"ack failed with status {ack_status}: {payload.decode('utf-8', 'replace')}")


def run_queue_poller(
    base_url: str,
    dequeue_token: str,
    debounce_seconds: float,
    poll_interval_seconds: float,
    stop_event: threading.Event,
) -> None:
    print(f"Queue poller on {base_url} every {poll_interval_seconds}s", file=sys.stderr)
    while not stop_event.is_set():
        try:
            job = _dequeue(base_url, dequeue_token)
            if job is None:
                stop_event.wait(poll_interval_seconds)
                continue

            job_id = int(job["id"])
            command_name = str(job["command"])
            print(f"Queue job {job_id}: {command_name}", file=sys.stderr)
            try:
                sent = dispatch_command(command_name, debounce_seconds)
                if sent:
                    _ack(base_url, dequeue_token, job_id, "done")
                else:
                    print(f"Queue job {job_id} debounced, will retry after lease", file=sys.stderr)
            except Exception as exc:
                print(f"Queue job {job_id} failed: {exc}", file=sys.stderr)
                try:
                    _ack(base_url, dequeue_token, job_id, "failed")
                except Exception as ack_exc:
                    print(f"Queue ack failed for job {job_id}: {ack_exc}", file=sys.stderr)
        except Exception as exc:
            print(f"Queue poller error: {exc}", file=sys.stderr)
            stop_event.wait(poll_interval_seconds)


def start_queue_poller_thread(
    base_url: str,
    dequeue_token: str,
    debounce_seconds: float,
    poll_interval_seconds: float,
    stop_event: threading.Event,
) -> threading.Thread:
    thread = threading.Thread(
        target=run_queue_poller,
        args=(base_url, dequeue_token, debounce_seconds, poll_interval_seconds, stop_event),
        daemon=True,
        name="fan-queue-poller",
    )
    thread.start()
    return thread
