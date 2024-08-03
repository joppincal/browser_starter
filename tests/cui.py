import sys
from pathlib import Path

import click

from .main import (
    ROOT_DIR,
    async_run_main,
    display_registered_browsers,
    get_default_browser_path_windows,
    logger,
    register_all_installed_browsers,
    register_browser,
    run_with_parameter_file,
)


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
