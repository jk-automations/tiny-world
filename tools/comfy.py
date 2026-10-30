"""Tiny comfy client: upload inputs, queue an API-format graph, wait, download outputs.
Usage from code: run(graph, out_dir) -> list of saved paths."""
import json, time, urllib.parse, urllib.request, uuid, mimetypes
from pathlib import Path

BASE = "http://127.0.0.1:8188"

def _req(path, data=None, headers=None, timeout=60):
    req = urllib.request.Request(BASE + path, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def upload(path, kind="image"):
    """Upload a local file to ComfyUI's input folder; returns the name to use in Load* nodes."""
    p = Path(path); b = uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{p.name}\"\r\n"
            f"Content-Type: {mimetypes.guess_type(p.name)[0] or 'application/octet-stream'}\r\n\r\n").encode()
    body += p.read_bytes() + f"\r\n--{b}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{b}--\r\n".encode()
    out = json.loads(_req("/upload/image", body, {"Content-Type": f"multipart/form-data; boundary={b}"}))
    return out["name"]

def run(graph, out_dir, poll=5):
    pid = json.loads(_req("/prompt", json.dumps({"prompt": graph, "client_id": uuid.uuid4().hex}).encode(),
                          {"Content-Type": "application/json"}))["prompt_id"]
    t0 = time.time()
    while True:
        h = json.loads(_req(f"/history/{pid}"))
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                raise RuntimeError(json.dumps(st.get("messages", []))[-2000:])
            if st.get("completed"):
                break
        time.sleep(poll)
    saved = []
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for node in h[pid]["outputs"].values():
        for key in ("images", "videos", "gifs", "audio"):
            for f in node.get(key, []):
                q = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f.get("type", "output")})
                dst = Path(out_dir) / f["filename"]; dst.write_bytes(_req(f"/view?{q}", timeout=600)); saved.append(str(dst))
    print(f"done in {time.time() - t0:.0f}s: {saved}")
    return saved
