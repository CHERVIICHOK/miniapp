"""Install the official Windows tunnel client into ignored project tools."""
import hashlib
import json
import sys
import urllib.request

from app.config import ROOT


def main():
    try:
        tools = ROOT / ".tools"
        tools.mkdir(exist_ok=True)
        target = tools / "cloudflared.exe"
        checksum_file = tools / "cloudflared.sha256"
        if target.exists() and checksum_file.exists():
            with target.open("rb") as stream:
                installed_digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if installed_digest == checksum_file.read_text(encoding="ascii").strip():
                print("cloudflared уже установлен, контрольная сумма проверена.")
                return 0
        request = urllib.request.Request("https://api.github.com/repos/cloudflare/cloudflared/releases/latest", headers={"User-Agent": "teploe-zerno-lab"})
        with urllib.request.urlopen(request, timeout=30) as response:
            release = json.load(response)
        asset = next(asset for asset in release["assets"] if asset["name"] == "cloudflared-windows-amd64.exe")
        url = asset["browser_download_url"]
        if not url.startswith("https://github.com/cloudflare/cloudflared/releases/download/"):
            raise ValueError("Недопустимый адрес загрузки")
        temporary = tools / "cloudflared.exe.part"
        expected = asset.get("digest")
        if not expected or not expected.startswith("sha256:"):
            raise ValueError("GitHub не предоставил SHA-256. Проверьте файл вручную по странице официального релиза.")
        if target.exists():
            with target.open("rb") as stream:
                existing_digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if existing_digest == expected.removeprefix("sha256:"):
                (tools / "cloudflared.sha256").write_text(existing_digest, encoding="ascii")
                print(f"cloudflared {release['tag_name']} уже установлен и проверен.")
                return 0
        with urllib.request.urlopen(url, timeout=45) as response, temporary.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        with temporary.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != expected.removeprefix("sha256:"):
            raise ValueError("Контрольная сумма cloudflared не совпала")
        temporary.replace(target)
        (tools / "cloudflared.sha256").write_text(digest, encoding="ascii")
        print(f"cloudflared {release['tag_name']} установлен и проверен.")
        return 0
    except Exception as exc:
        print(f"Не удалось установить cloudflared ({type(exc).__name__}). Повторите команду. Официальный релиз: https://github.com/cloudflare/cloudflared/releases", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
