import asyncio
import atexit
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import webbrowser
import winreg
from logging import (
    DEBUG,
    INFO,
    Formatter,
    NullHandler,
    StreamHandler,
    getLogger,
    handlers,
)
from pathlib import Path
from typing import Callable, Dict, List, Optional

import click

# Constants
ROOT_DIR = Path.home() / ".browser_starter"
CONFIG_FILE = ROOT_DIR / "browser_starter.json"
DEFAULT_COUNTDOWN_SECONDS = 6

# Registered browsers
REGISTERED_BROWSERS: Dict[str, str] = {}


def log_setting(fileout: bool = True, stdout: bool = False):
    logger = getLogger(__name__)

    if not stdout and not fileout:
        logger = getLogger()
        logger.addHandler(NullHandler())
        return logger
    else:
        logger.setLevel(DEBUG)

    formater = Formatter(
        "{asctime} {name} {levelname:<8s} {message}", style="{"
    )

    if fileout:
        log_dir = ROOT_DIR / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "browser_starter.log"

        rotating_file_handler = handlers.RotatingFileHandler(
            filename=log_file,
            encoding="utf-8",
            maxBytes=1_000_000,
            backupCount=10,
        )
        rotating_file_handler.setFormatter(formater)
        logger.addHandler(rotating_file_handler)

    if stdout:
        stream_handler = StreamHandler()
        stream_handler.setLevel(INFO)
        stream_handler.setFormatter(formater)
        logger.addHandler(stream_handler)

    return logger


logger = log_setting()


def load_config() -> Dict:
    """Load configuration from JSON file."""
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(
            f"Config file {CONFIG_FILE} not found. Using default settings."
        )
        return {}
    except json.JSONDecodeError:
        logger.error(f"Error decoding {CONFIG_FILE}. Using default settings.")
        return {}


CONFIG = load_config()


def get_browser_path_windows(browser_name: str) -> Optional[str]:
    """
    Get browser path from Windows registry.
    """
    try:
        browser_key = rf"SOFTWARE\Clients\StartMenuInternet\{browser_name}"
        key_path = rf"{browser_key}\shell\open\command"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            command = winreg.QueryValueEx(key, "")[0]
            path = command.replace('"', "")
            return path
    except WindowsError as e:
        logger.error(f"Error getting browser path for {browser_name}: {e}")
        return None


def get_installed_browsers() -> Dict[str, Optional[str]]:
    """
    Get installed browsers based on the operating system.
    """
    system = platform.system()

    if system == "Windows":
        browsers: Dict[str, Optional[str]] = {}
        keys = [
            r"SOFTWARE\Clients\StartMenuInternet",
            r"SOFTWARE\WOW6432Node\Clients\StartMenuInternet",
        ]
        for key in keys:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as reg_key:
                    for i in range(winreg.QueryInfoKey(reg_key)[0]):
                        name = winreg.EnumKey(reg_key, i)
                        browsers[name] = get_browser_path_windows(name)
            except WindowsError as e:
                logger.error(f"Error accessing registry key {key}: {e}")
        return dict(sorted(browsers.items()))

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

    if system == "Darwin":  # macOS
        # TODO: Implement macOS browser detection here
        logger.warning("macOS browser detection not implemented yet.")
        return {}

    logger.warning(f"Unsupported operating system: {system}")
    return {}


def register_browser(name: str, path: str) -> None:
    """
    Register a browser.
    """
    try:
        webbrowser.register(name, None, webbrowser.BackgroundBrowser(path))
        REGISTERED_BROWSERS[name] = path
    except Exception as e:
        logger.error(f"Error registering browser {name}: {e}")


def register_all_installed_browsers() -> None:
    """
    Register all installed browsers.
    """
    for name, path in get_installed_browsers().items():
        if path:
            register_browser(name, path)


async def open_url(browser: webbrowser.BaseBrowser, url: str) -> None:
    """
    Open a URL asynchronously.
    """
    success = browser.open(url, new=2)  # new=2 specifies opening in a new tab
    logger.info(f"Opening URL: {url} - Success: {success}")
    await asyncio.sleep(0.5)


async def open_urls_in_browser(
    browsername: str, urls: List[str], open_strategy: Callable
) -> None:
    """
    Open multiple URLs in the specified browser using the given strategy.
    """
    browser = webbrowser.get(browsername)
    browserpath = REGISTERED_BROWSERS[browsername]

    logger.info(f"Opening URLs in {browsername}")
    logger.debug(f"Registered browsers: {REGISTERED_BROWSERS}")
    logger.debug(
        f"Webbrowser browsers: {webbrowser._browsers}"  # type: ignore
    )

    start_page = get_start_page()
    process = subprocess.Popen(
        [browserpath, "--new-window", start_page], shell=True  # type: ignore
    )
    logger.info(f"Started browser process with PID: {process.pid}")

    await asyncio.sleep(3)  # Wait for the browser to initialize

    await open_strategy(browser, urls)


async def open_urls_fast(
    browser: webbrowser.BaseBrowser, urls: List[str]
) -> None:
    """
    Open URLs asynchronously in parallel (fast mode).
    """
    tasks = [open_url(browser, url) for url in urls]
    await asyncio.gather(*tasks)


async def open_urls_ordered(
    browser: webbrowser.BaseBrowser, urls: List[str]
) -> None:
    """
    Open URLs asynchronously in order (ordered mode).
    """
    for url in urls:
        await open_url(browser, url)


def get_start_page(
    countdown_seconds: int = DEFAULT_COUNTDOWN_SECONDS,
) -> Optional[str]:
    """
    Generate a temporary start page with a countdown timer.
    """
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

        atexit.register(lambda: os.remove(temp_file_name))

        return Path(temp_file_name).absolute().as_uri()
    except IOError as e:
        logger.error(f"Error creating temporary file: {e}")
        return None


def display_registered_browsers():
    if not REGISTERED_BROWSERS:
        click.echo("No browsers registered.")
        return

    click.echo("Browser list")
    items = REGISTERED_BROWSERS.items()
    max_key = max(len(item[0]) for item in items)
    max_value = max(len(item[1]) for item in items)

    # Consider the length of column names as well
    BROWSER_NAME_COLUMN = "browser-name"
    BROWSER_PATH_COLUMN = "path/to/browser"
    max_key = max(max_key, len(BROWSER_NAME_COLUMN))
    max_value = max(max_value, len(BROWSER_PATH_COLUMN))

    slash = "\\" if platform.system() == "Windows" else "/"

    # Display the header
    click.echo(f"  {BROWSER_NAME_COLUMN:<{max_key}} |>  ", nl=False)
    click.echo(f"{BROWSER_PATH_COLUMN.replace('/', slash)}")
    click.echo("-" * (max_key + max_value + 10))

    # Display browser information
    for key, value in items:
        click.echo(f"  {key:<{max_key}} |>  {value}")


async def main(
    browsernames: List[str], urls: List[str], fast_mode: bool = True
) -> None:
    """
    Main asynchronous function to open URLs in specified browsers.
    """
    register_all_installed_browsers()
    open_strategy = open_urls_fast if fast_mode else open_urls_ordered
    tasks = [
        open_urls_in_browser(browsername, urls, open_strategy)
        for browsername in browsernames
    ]
    await asyncio.gather(*tasks)


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option(
    "-b",
    "-bn",
    "--browser-name",
    multiple=True,
    help="(multiple) Name of the browser to use",
)
@click.option(
    "-bp",
    "--browser-path",
    multiple=True,
    help="(multiple) Path to the browser executable",
)
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=True),
    help="Path to TOML configuration file",
)
@click.option(
    "-f/-o",
    "--fast/--ordered",
    help="Fast mode (order not guaranteed)/Order keeping mode (slow/default)",
)
@click.option(
    "-l",
    "-bl",
    "--browser-list",
    is_flag=True,
    help="Listing the names of available browsers",
)
@click.argument("urls", nargs=-1, required=False)
def cli(browser_name, browser_path, config, fast, browser_list, urls):
    """Open URLs in specified browser.
    If no URLs are provided, only the start page will be opened."""
    if len(sys.argv) == 1:
        cli.main(["--help"])

    if browser_list:
        register_all_installed_browsers()
        display_registered_browsers()
        return

    if config:
        if browser_name or browser_path:
            click.echo(
                "Warning: Config file specified. "
                + "Ignoring browser name and path options.",
                err=True,
            )
        # TODO: Implement TOML file parsing and use its content
        click.echo("TOML configuration file support not yet implemented.")
        return

    browser = list()
    if not all([browser_name, browser_path]):
        click.echo(
            "Error: Either browser name or path must be specified.", err=True
        )
        return
    if browser_path:
        for name in browser_path:
            register_browser(name, name)
        browser.extend(list(browser_path))
    if browser_name:
        browser.extend(list(browser_name))

    if not urls:
        urls = []

    asyncio.run(main(browser, urls, fast))


if __name__ == "__main__":
    cli()
