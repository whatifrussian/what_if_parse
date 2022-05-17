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

## Known problems

The HTML layout was changed on the website and the tool does not reflect it.

The article number/title is necessary to generate a 'slug', but they're not
parsed at the moment. I use the following workaround for a while:

```diff
diff --git a/what_if_parse.py b/what_if_parse.py
index e196e9b..b8789c6 100755
--- a/what_if_parse.py
+++ b/what_if_parse.py
@@ -446,6 +446,7 @@ def process_article(url, html):
         'blockquote': process_toplevel_blockquote,
         'img': process_toplevel_img,
     }
+    state['slug'] = '158-hot-banana'
     for child in article:
         logging.info('Processed %d/%d top level elements',
                      childs_processed, childs_cnt)
```

## License

The code, documentation and other repository content are in public domain.
