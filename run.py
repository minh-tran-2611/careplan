import argparse
import getpass
import os
import threading
import time
import urllib.request
import webbrowser

import uvicorn
from config.settings import get_settings


def open_when_ready(url: str):
    for _ in range(40):
        try:
            with urllib.request.urlopen(url + "/api/status", timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except OSError:
            time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description="CarePlan local server")
    parser.add_argument("--prompt-key", action="store_true")
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    settings = get_settings()
    if args.prompt_key and not settings.api_key:
        print("Enter NVIDIA API key, or press Enter to use the reference library only.")
        os.environ["NVIDIA_API_KEY"] = getpass.getpass("API key (hidden): ").strip()
        get_settings.cache_clear()
    host = os.getenv("HOST", "127.0.0.1")
    port = args.port or int(os.getenv("PORT", "8000"))
    url = f"http://127.0.0.1:{port}"
    print(f"Starting CarePlan at {url}")
    print("Keep this window open. Closing it stops the website. Ctrl+C to stop.")
    if args.open_browser:
        threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    uvicorn.run("api.server:app", host=host, port=port, access_log=False)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCarePlan stopped.")
