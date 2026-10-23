"""An isolated local PostgreSQL 17 cluster; never touches an existing installation."""
import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from dotenv import set_key

from app.config import ROOT
from scripts.bootstrap_db import provision

VERSION = "17.11-4"
ARCHIVE_URL = f"https://get.enterprisedb.com/postgresql/postgresql-{VERSION}-windows-x64-binaries.zip"
# Published by the EDB maintainer: https://github.com/EnterpriseDB/edb-installers/issues/706
ARCHIVE_SHA256 = "b9424ee7bc60b52450ff910a3630225df32e633f3cb29c1d126d9299d59aea28"
RUNTIME = ROOT / ".runtime"
TOOLS = ROOT / ".tools"
BIN = TOOLS / "pgsql/bin"
DATA = RUNTIME / "pgdata"
STATE = RUNTIME / "postgres.json"


def run(*args, check=True):
    # PostgreSQL helpers and background postgres must not create visible console windows.
    return subprocess.run([str(a) for a in args], check=check, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


def install():
    if (BIN / "pg_ctl.exe").exists() and (BIN / "initdb.exe").exists():
        return
    TOOLS.mkdir(exist_ok=True)
    archive = TOOLS / "postgresql.zip"
    if not archive.exists():
        print("Загрузка официального PostgreSQL 17 (~363 МБ)…", flush=True)
        urllib.request.urlretrieve(ARCHIVE_URL, archive)
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != ARCHIVE_SHA256:
        raise ValueError("Контрольная сумма PostgreSQL не совпала. Удалите только .tools/postgresql.zip и повторите загрузку.")
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            path = Path(item.filename)
            if path.parts[:2] not in [("pgsql", "bin"), ("pgsql", "lib"), ("pgsql", "share")]:
                continue
            destination = (TOOLS / path).resolve()
            if not destination.is_relative_to(TOOLS.resolve()):
                raise ValueError("Недопустимый путь в архиве PostgreSQL")
            bundle.extract(item, TOOLS)


def settings():
    if not STATE.exists():
        raise ValueError("Сначала выполните python -m scripts.local_postgres setup")
    return json.loads(STATE.read_text(encoding="utf-8"))


def start():
    settings()
    if run(BIN / "pg_ctl.exe", "status", "-D", DATA, check=False).returncode != 0:
        run(BIN / "pg_ctl.exe", "start", "-D", DATA, "-l", RUNTIME / "postgres.log", "-w", "-t", "30")


def setup():
    if os.name != "nt":
        raise ValueError("Этот помощник предназначен для Windows. На Linux используйте системный PostgreSQL и scripts.bootstrap_db.")
    install()
    RUNTIME.mkdir(exist_ok=True)
    if not STATE.exists():
        if DATA.exists():
            raise ValueError("Найден каталог pgdata без postgres.json. Автоматическая перезапись данных запрещена.")
        credentials = {"admin_password": secrets.token_urlsafe(28), "app_password": secrets.token_urlsafe(28), "port": 55432}
        STATE.write_text(json.dumps(credentials), encoding="utf-8")
    config = settings()
    if not (DATA / "PG_VERSION").exists():
        pwfile = RUNTIME / "initdb-password"
        try:
            pwfile.write_text(config["admin_password"], encoding="utf-8")
            run(BIN / "initdb.exe", "-D", DATA, "-U", "miniapp_admin", "--auth=scram-sha-256", "--encoding=UTF8", "--locale=C", f"--pwfile={pwfile}")
        finally:
            pwfile.unlink(missing_ok=True)
        with (DATA / "postgresql.conf").open("a", encoding="utf-8") as stream:
            stream.write(f"\n# Isolated teaching cluster\nlisten_addresses = '127.0.0.1'\nport = {config['port']}\n")
    start()
    admin_url = f"postgresql://miniapp_admin:{config['admin_password']}@127.0.0.1:{config['port']}/postgres"
    app_url = f"postgresql://teploe_zerno:{config['app_password']}@127.0.0.1:{config['port']}/teploe_zerno"
    provision(admin_url, app_url)
    set_key(str(ROOT / ".env"), "DATABASE_URL", app_url)
    print("Готово: отдельный PostgreSQL на 127.0.0.1:55432, БД teploe_zerno. DATABASE_URL сохранён в .env.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "start", "stop", "status"])
    action = parser.parse_args().action
    try:
        if action == "setup": setup()
        elif action == "start": start()
        else:
            settings()
            result = run(BIN / "pg_ctl.exe", action, "-D", DATA, *( ["-m", "fast", "-w"] if action == "stop" else []), check=False)
            return result.returncode
        return 0
    except Exception as exc:
        # Never print connection URLs, generated passwords, or SQL commands.
        print(f"Не удалось выполнить {action}: {str(exc) if isinstance(exc, ValueError) else type(exc).__name__}. См. .runtime/postgres.log.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
