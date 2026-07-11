# what_if_parse

A tool for downloading `https://what-if.xkcd.com` articles and converting
their contents to Markdown. Python 3.10 or newer is supported.

## Install

Create a virtual environment and install the dependencies:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

## Usage

```sh
python what_if_parse.py [num]
```

`num` is optional. If omitted, the latest article is downloaded. Pass `all`
to download every article, newest first.

See all options with `python what_if_parse.py --help`.

Generated HTML and Markdown files are written to the current directory and
include a timestamp in their names.

## Docker

Build the image and write generated files into a local `output` directory:

```sh
docker build -t what-if-parse .
mkdir -p output
docker run --rm -v "$PWD/output:/output" what-if-parse 1
```

The container runs as an unprivileged user. On Linux, make sure the mounted
directory is writable by that user.

## Development

```sh
python -m pip install -r requirements-dev.txt
python -m unittest --verbose
ruff check .
docker build -t what-if-parse:test .
docker run --rm what-if-parse:test --help
```

## License

The code, documentation and other repository content are in public domain.
