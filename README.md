## About

The tool for grabbing http://what-if.xkcd.com articles into Markdown.

## Install

The script written on Python 3 and requires `requests` and `lxml` packages. You can install these packages by system package manager or by `pip` tool using `requirements.txt` file (it contains versions of packages that works for me).

## Usage

```
$ ./what_if_parse [num]
```

Where `num` is optional article number for grabbing. If it ommited, last article will grabbed.

Resulting HTML and Markdown will saved into files like `001-relativistic-baseball.html` and `001-relativistic-baseball.md`.

## License

The code, documentation and other repository content is in public domain.
