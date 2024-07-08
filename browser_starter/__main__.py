import atexit
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser
import winreg
from datetime import datetime

try:
    from icecream import ic  # type: ignore

    ic.configureOutput(prefix=lambda: f"ic| {datetime.now()}| ")
except ImportError:  # Graceful fallback if IceCream isn't installed.
    ic = lambda *a: None if not a else (a[0] if len(a) == 1 else a)  # noqa

REGISTERED_BROWSERS = {}


def get_browser_path_windows(browser_name):
    try:
        browser_key = rf"SOFTWARE\Clients\StartMenuInternet\{browser_name}"
        key_path = rf"{browser_key}\shell\open\command"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            command = winreg.QueryValueEx(key, None)[0]
            path = command.replace(
                '"', ""
            )  # Extract the path from the command
            return path
    except WindowsError:
        return None


def get_installed_browsers():
    system = platform.system()

    if system == "Windows":
        browsers = dict()
        keys = [
            r"SOFTWARE\Clients\StartMenuInternet",
            r"SOFTWARE\WOW6432Node\Clients\StartMenuInternet",
        ]
        for key in keys:
            try:
                reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key)
                for i in range(winreg.QueryInfoKey(reg_key)[0]):
                    name = winreg.EnumKey(reg_key, i)
                    browsers[name] = get_browser_path_windows(name)

            except WindowsError:
                pass
        return {t[0]: t[1] for t in sorted(browsers.items())}

    if system == "Linux":
        common_browsers = [
            "firefox",
            "google-chrome",
            "chromium-browser",
            "opera",
            "brave-browser",
            "vivaldi",
        ]
        return {
            browser: shutil.which(browser)
            for browser in common_browsers
            if shutil.which(browser)
        }

    return {}


def register_browser(name: str, path: str):
    webbrowser.register(name, None, webbrowser.BackgroundBrowser(path))
    REGISTERED_BROWSERS[name] = path


def register_all_installed_browser():
    for name, path in get_installed_browsers().items():
        register_browser(name, path)


def open_urls_in_the_specified_browsers(
    browsernames: list[str] = [], URLs: list = []
):
    for browsername in browsernames:
        open_urls_in_the_specified_browser(browsername, URLs)


def open_urls_in_the_specified_browser(browsername: str, URLs: list = []):
    browser = webbrowser.get(browsername)
    browserpath = REGISTERED_BROWSERS[browsername]

    ic(REGISTERED_BROWSERS)
    ic(webbrowser._browsers)  # type: ignore

    ic(browser)

    i = 0
    start_page = get_start_page()
    ic(
        subprocess.Popen(
            [
                browserpath,
                "--new-window",
                start_page,
            ],
            shell=True,
        )
    )

    if URLs:
        time.sleep(1)
        for URL in URLs:
            i += 1
            ic(i, browser.open(URL))
            time.sleep(0.5)


def get_start_page(countdown_seconds=6):
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <title>browser-starter start page</title>
    </head>
    <body>
        <h1>browser-starter start page</h1>
        <p>仕様上の都合のため、このファイルが表示されます</p>
        <p id="JMessage"></p>
        <p>This file is displayed due to specification convenience</p>
        <p id="EMessage"></p>
        <script>
            var sec = {countdown_seconds};
            function count_down() {{
                sec--;
                var jmsg = sec + "秒後、このタブを閉じます";
                document.getElementById("JMessage").innerText = jmsg;
                var emsg = sec + " seconds later, close this tab";
                document.getElementById("EMessage").innerText = emsg;
                if (sec == 0) {{
                    window.close();
                }}
            }}
            count_down();
            setInterval(count_down, 1000);
        </script>
    </body>
    </html>
    """

    try:
        with tempfile.NamedTemporaryFile(
            "w", delete=False, suffix=".html", encoding="utf-8"
        ) as f:
            f.write(html_content)
            temp_file_name = f.name

        # 終了時にファイルを削除するための関数を登録
        atexit.register(lambda: os.remove(temp_file_name))

        file_uri = "file://" + os.path.abspath(temp_file_name)
        return file_uri
    except IOError as e:
        ic(f"エラー: ファイルの作成中に問題が発生しました: {e}")
        return None


if __name__ == "__main__":
    register_all_installed_browser()
    open_urls_in_the_specified_browsers(sys.argv[1:2], sys.argv[2:])
