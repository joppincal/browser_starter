import asyncio
import atexit
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
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
import yaml

# Location of configuration and log files
ROOT_DIR = Path.home() / ".browser_starter"
# Location of configuration file
CONFIG_FILE = ROOT_DIR / "browser_starter.json"
# Time before the start page automatically closes
DEFAULT_COUNTDOWN_SECONDS = 6

# Browser name and its path on the PC
REGISTERED_BROWSERS: Dict[str, str] = {}


def log_setting(fileout: bool = True, stdout: bool = False):
    """Logging Settings

    Args:
        fileout (bool, optional): Log file output or not. Defaults to True.
        stdout (bool, optional): Output std output or not. Defaults to False.

    Returns:
        _type_: logging.Logger
    """
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
        rotating_file_handler.setLevel(DEBUG)
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

    except json.JSONDecodeError:
        logger.error(f"Error decoding {CONFIG_FILE}. Using default settings.")

    return {}


CONFIG = load_config()


def load_parameter_file(path: Path) -> Dict:
    parameter_file = path.absolute()

    suffix = parameter_file.suffix
    func: Callable
    if suffix in (".yml", ".yaml"):
        func = yaml.safe_load
    elif suffix == ".json":
        func = json.load
    elif suffix == ".toml":
        func = tomllib.load
    else:
        func = lambda *a: None  # noqa

    try:
        with open(parameter_file, "rb") as f:
            return func(f)

    except FileNotFoundError:
        logger.warning(f"Parameter file {parameter_file} not found.")

    except yaml.YAMLError:
        logger.error(f"Error decoding {parameter_file}.")

    except json.JSONDecodeError:
        logger.error(f"Error decoding {parameter_file}.")

    except tomllib.TOMLDecodeError:
        logger.error(f"Error decoding {parameter_file}.")

    return {}


def run_with_parameter_file(p_file_path: Path):
    logger.info(f"Run with parameter file: {p_file_path}")

    parameter = load_parameter_file(p_file_path).items()
    threads = []

    for _, di in parameter:
        # Selecting a browser from the parameter file
        browsers = list()

        # Extract browser name
        pattern = r"^(-bn|--browser-name)\d*$"
        matching_items = [
            value for key, value in di.items() if re.match(pattern, key)
        ]
        if matching_items:
            browsers.extend(matching_items)

        # Extract browser path
        pattern = r"^(-bp|--browser-path)\d*$"
        matching_items = [
            value for key, value in di.items() if re.match(pattern, key)
        ]
        if matching_items:
            for path in matching_items:
                register_browser(path, path)
            browsers.extend(matching_items)

        # If no browser is specified, get the default browser
        if not browsers:
            default_browser_path = get_default_browser_path_windows()
            if default_browser_path:
                register_browser(default_browser_path, default_browser_path)
                browsers.append(default_browser_path)
            else:
                pass

        # Get URL from parameter file
        pattern = r"^(-u|--urls)"
        matching_items = [
            value for key, value in di.items() if re.match(pattern, key)
        ]
        urls = [
            url
            for item in matching_items
            for url in (item if isinstance(item, list) else [item])
            if isinstance(url, str)
        ]

        # Get fast mode from parameter file
        pattern = r"^(-f|--fast|-o|--ordered)$"
        matching_items = [
            key for key, _ in di.items() if re.match(pattern, key)
        ]
        if matching_items:
            if matching_items[0] in {"-f", "--fast"}:
                fast = True
            elif matching_items[0] in {"-o", "--ordered"}:
                fast = False
        else:
            fast = False

        logger.debug(
            "Parameter file parameter; "
            f"browsers: {browsers}, urls: {urls}, fast: {fast}"
        )

        t = threading.Thread(
            target=async_run_main, args=[browsers, urls, fast]
        )
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()


def get_browser_path_windows(browser_name: str) -> Optional[str]:
    """
    Get browser path from Windows registry.
    """
    logger.debug(f"Attempting to get browser path for {browser_name}")

    try:
        browser_key = rf"Software\Clients\StartMenuInternet\{browser_name}"
        key_path = rf"{browser_key}\shell\open\command"

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            command = winreg.QueryValueEx(key, "")[0]
            path = command.replace('"', "")
            logger.debug(f"Browser path found: {path}")

            return path

    except WindowsError as e:
        logger.error(f"Error getting browser path for {browser_name}: {e}")

        return None


def get_default_browser_path_windows() -> Optional[str]:
    """
    Get default browser path from Windows registry.
    """
    try:
        logger.debug("Attempting to get default browser path")

        key_path = r"Software\Microsoft\Windows\Shell"
        key_path += r"\Associations\UrlAssociations\https\UserChoice"

        # Get the ProgID from the user settings that open the Https link.
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            progid = winreg.QueryValueEx(key, "ProgID")[0]
        logger.debug(f"Default browser ProgID: {progid}")

        key_path = rf"{progid}\shell\open\command"

        # Get software path from ProgID
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key_path) as key:
            command = winreg.QueryValueEx(key, "")[0]
            match = re.search(r'"?([^"]+\.exe)"?', command)
            logger.debug(
                f"Default browser path found: "
                f"{match.group(1) if match else None}"
            )

            if match:
                return match.group(1)
            else:
                return None

    except WindowsError as e:
        logger.error(f"Error getting default browser path: {e}")

        return None


def get_installed_browsers() -> Dict[str, Optional[str]]:
    """
    Get installed browsers based on the operating system.
    """
    system = platform.system()
    logger.info(f"Detecting installed browsers on {system}")

    browsers: Dict[str, Optional[str]] = {}

    if system == "Windows":
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

        browsers = dict(sorted(browsers.items()))

    elif system == "Linux":
        common_browsers = [
            "firefox",
            "google-chrome",
            "chromium-browser",
            "opera",
            "brave-browser",
            "vivaldi",
        ]

        browsers = {
            browser: shutil.which(browser)
            for browser in common_browsers
            if shutil.which(browser)
        }

    elif system == "Darwin":  # macOS
        # TODO: Implement macOS browser detection here
        logger.warning("macOS browser detection not implemented yet.")

    else:
        logger.warning(f"Unsupported operating system: {system}")

    logger.debug(f"Detected browsers: {browsers}")

    return browsers


def register_browser(name: str, path: str) -> None:
    """
    Register a browser.
    """
    logger.info(f"Registering browser: {name} at path: {path}")

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
    logger.debug(f"Browser path: {browserpath}")

    logger.info(f"Opening URLs in {browsername}")

    start_page = get_start_page()
    logger.debug(f"Start page URL: {start_page}")

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
        logger.debug(f"Created temporary start page: {temp_file_name}")

        atexit.register(lambda: os.remove(temp_file_name))

        return Path(temp_file_name).absolute().as_uri()
    except IOError as e:
        logger.error(f"Error creating temporary file: {e}")

        return None


def display_registered_browsers():
    """
    Registered Name |> Path
    """
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


def async_run_main(
    browsernames: List[str], urls: List[str], fast_mode: bool = True
):
    asyncio.run(main(browsernames, urls, fast_mode))


async def main(
    browsernames: List[str], urls: List[str], fast_mode: bool = True
) -> None:
    """
    Main asynchronous function to open URLs in specified browsers.
    """
    start_time = time.perf_counter()

    open_strategy = open_urls_fast if fast_mode else open_urls_ordered
    tasks = [
        open_urls_in_browser(browsername, urls, open_strategy)
        for browsername in browsernames
    ]
    logger.info(f"Starting main function with browsers: {browsernames}")
    logger.info(f"URLs to open: {urls}")
    logger.info(f"Fast mode: {fast_mode}")
    logger.debug(f"Registered browsers: {REGISTERED_BROWSERS}")
    logger.debug(
        f"Webbrowser browsers: {webbrowser._browsers}"  # type: ignore
    )

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError as e:
        logger.warning("Main function cancelled:", exc_info=e)
    finally:
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        logger.info(f"Total execution time: {elapsed_time:.4f} seconds")


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option(
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
    "-pf",
    "--parameter-file",
    "p_file",
    default=None,
    is_flag=False,
    flag_value=ROOT_DIR / "browser_starter_parameter.yaml",
    help="Path to parameter file",
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
@click.option(
    "-u",
    "--urls",
    multiple=True,
    help="(multiple) URL to open (Option name can be omitted)",
)
@click.argument("urls_", nargs=-1, required=False)
def cli(browser_name, browser_path, p_file, fast, browser_list, urls, urls_):
    """Open URLs in specified browser.
    If no URLs are provided, only the start page will be opened."""
    logger.info("Starting CLI")
    logger.debug(f"Command line arguments: {sys.argv}")

    # Display help when no argument is given
    if len(sys.argv) == 1:
        cli.main(["--help"])

    register_all_installed_browsers()

    # Display browser list and exit
    if browser_list:
        display_registered_browsers()
        return

    # When a parameter file is passed, process accordingly
    if p_file:
        p_file_path = Path(p_file)

        if not p_file_path.exists():
            logger.warning(f"Parameter file {p_file_path} not found.")
            return

        if browser_name or browser_path or urls:
            click.echo(
                "Warning: Config file specified. " + "Ignoring other options.",
                err=True,
            )

        run_with_parameter_file(p_file_path)

        return

    browsers = list()
    # If neither bn nor bp is specified, get the user default for the computer
    if not any([browser_name, browser_path]):
        default_browser_path = get_default_browser_path_windows()
        if default_browser_path:
            register_browser(default_browser_path, default_browser_path)
            browsers.append(default_browser_path)
        else:
            pass
    # When bp is specified, set to webbrowser
    if browser_path:
        for path in browser_path:
            register_browser(path, path)
        browsers.extend(list(browser_path))
    # When bn is specified, check if webbrowser is configured
    if browser_name:
        browsers.extend(list(browser_name))

    logger.info(f"Selected browsers: {browsers}")

    if urls and urls_:
        # Because the firing order of URLs can no longer be guaranteed
        click.echo(
            "Warning: Do not mix option names --urls with and without "
            "omitted ones. The omitted notation is recommended."
        )
        return
    if not urls:
        urls = urls_

    logger.info(f"URLs to open: {urls}")

    async_run_main(browsers, urls, fast)


if __name__ == "__main__":
    cli()
