"""Tải GGUF PhoGPT trực tiếp (resume được, in tiến độ). Chạy: python download_gguf.py"""
import sys, os, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

URL = "https://huggingface.co/vinai/PhoGPT-4B-Chat-gguf/resolve/main/PhoGPT-4B-Chat-Q4_K_M.gguf"
OUT_DIR = "models"
OUT = os.path.join(OUT_DIR, "PhoGPT-4B-Chat-Q4_K_M.gguf")
os.makedirs(OUT_DIR, exist_ok=True)


def main():
    done = os.path.getsize(OUT) if os.path.exists(OUT) else 0
    req = urllib.request.Request(URL, headers={"Range": f"bytes={done}-",
                                               "User-Agent": "datn-rag/1.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        if e.code == 416:  # đã tải đủ
            print(f"Đã có đủ file: {done/1e9:.2f} GB"); return
        raise
    total = done + int(resp.headers.get("Content-Length", 0))
    print(f"Tải {URL}\n-> {OUT} | bắt đầu từ {done/1e6:.0f} MB / tổng {total/1e9:.2f} GB")
    mode = "ab" if done else "wb"
    last = done
    with open(OUT, mode) as f:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if done - last >= 100 * 1024 * 1024:  # mỗi 100MB in 1 lần
                last = done
                print(f"  {done/1e6:.0f} MB ({done/total*100:.0f}%)")
    print(f"✅ Tải xong: {OUT} ({os.path.getsize(OUT)/1e9:.2f} GB)")


if __name__ == "__main__":
    main()
