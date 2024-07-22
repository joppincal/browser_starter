[JP](README.md)/[EN](README.en.md)

# Browser Starter

Browser Starter is a Python script that allows you to easily open multiple URLs in specified browsers.

## Features

- Support for multiple browsers and URLs
- Choice between fast mode and order-preserving mode
- Batch configuration using parameter files

## Installation

Install using Poetry:

```bash
poetry install
```

## Usage

Run Browser Starter with command-line arguments:

```bash
python browser_starter.py [OPTIONS] [URLS]
```

Options:

- -bn, --browser-name: Name of the browser to use (multiple allowed)
- -bp, --browser-path: Path to the browser executable (multiple allowed)
- -pf, --parameter-file: Path to parameter file
- -f, --fast: Fast mode (order not guaranteed)
- -o, --ordered: Order-preserving mode (default, slower)
- -l, -bl, --browser-list: List available browsers
- -u, --urls: URL to open (multiple allowed, option name can be omitted)

## Configuration

You can store settings in JSON format at ~/.browser_starter/browser_starter.json.

## Parameter File

Use a parameter file in YAML, JSON, or TOML format to specify multiple combinations of browsers and URLs at once.

## Logging

Logs are saved to ~/.browser_starter/log/browser_starter.log.

## Contributing

Please use the GitHub issue tracker for bug reports and feature requests.
