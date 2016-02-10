## About

The tool for grabbing http://what-if.xkcd.com articles into Markdown.

## Install

The script written on Python 3 and requires `requests` and `lxml` packages. You can install these packages by system package manager or by `pip` tool using `requirements.txt` file (it contains versions of packages that works for me).

## Usage

```
$ ./what_if_parse [num]
```

Where `num` is optional article number for grabbing. If it ommited, last article will grabbed.

More options described in the cheatsheet, which can be displayed by `./what_if_parse --help`.

Resulting HTML and Markdown will saved into files like `001-relativistic-baseball-20160210-232959+0300.html` and `001-relativistic-baseball-20160210-232959+0300.html`. A timestamp added for simplify tracking changes.

## License

The code, documentation and other repository content are in public domain.
