#!/usr/bin/env python3

""" Main what-if downloading and parsing module

The module defines set of functions for downloading and parsing articles from
'https://what-if.xkcd.com'.

"""

import os
import re
import sys
import io
import logging
from datetime import tzinfo, timedelta, datetime
import lxml.html
import requests
from requests.exceptions import RequestException, BaseHTTPError


EXIT_SUCCESS = 0
EXIT_WRONG_ARGS = 1
EXIT_GET_PAGE_ERROR = 2


# Notabenoid doesn't display spaces at start of a line.
NOTABENOID_SPACES_WORKAROUND = True
# Avoid hardcoding here is pretty awkward as I remember.
TIMEZONE_OFFSET_HOURS = 3
# Avoid infinite freeze.
HTTP_TIMEOUT = 10


class TZ(tzinfo):
    """ Hardcoded Moscow timezone """
    def utcoffset(self, dt):
        return timedelta(hours=TIMEZONE_OFFSET_HOURS)

    def dst(self, dt):
        return timedelta(hours=TIMEZONE_OFFSET_HOURS)

    def tzname(self, dt):
        return "MSK"


class GetPageError(Exception):
    """ The exception raised when smth went wrong in 'get_page' function. """
    def __init__(self, desc, url, more=None):
        Exception.__init__(self)
        self.desc = desc
        self.url = url
        self.more = more

    def __str__(self):
        tmpl = 'The error "%s" occured while getting the page %s%s'
        if self.more:
            more_str = '; ' + str(self.more)
        else:
            more_str = ''
        return tmpl % (self.desc, self.url, more_str)


def timestamp():
    return datetime.now(TZ()).strftime('%Y%m%d-%H%M%S%z')


def safe_makedirs(directory):
    if os.path.isdir(directory):
        return
    os.makedirs(directory)


def is_text_html(url):
    try:
        res = requests.head(url, allow_redirects=True, timeout=HTTP_TIMEOUT)
    except (RequestException, BaseHTTPError):
        err = 'HTTP HEAD request failed before status code become available'
        raise GetPageError(err, url)
    if res.status_code != requests.codes['ok']:
        err = 'HTTP HEAD request failed'
        more = {'status_code': res.status_code}
        raise GetPageError(err, url, more)
    return res.headers['Content-Type'].startswith('text/html')


# It always returns HTML content in it's original encoding, so you should
# decode resulting string manually (e.g. using 'codecs' module) when you
# intent to process HTML manually. When lxml used to parse HTML, it decodes
# HTML string itself according to 'content-type' attribute in 'meta' tag.
# Related discussion: https://stackoverflow.com/a/25023776
def get_page(url, raise_non_text_html=False):
    """ Get HTML page or raise GetPageError exception.

    If content-type header isn't 'text/html' the exception raised as well as
    when download error occured.

    """
    if not is_text_html(url):
        if raise_non_text_html:
            err = 'Content-Type is differs from text/html'
            raise GetPageError(err, url)
        else:
            return None
    try:
        res = requests.get(url, timeout=HTTP_TIMEOUT)
    except (RequestException, BaseHTTPError):
        err = 'HTTP GET request failed before status code become available'
        raise GetPageError(err, url)
    if res.status_code != requests.codes['ok']:
        err = 'HTTP GET request failed'
        more = {'status_code': res.status_code}
        raise GetPageError(err, url, more)
    return res.content


def get_title(reference, refs_cnt, default_res='TODO'):
    """ Get a title of a page by its url.

    Download page from reference['url'] and extract title. If an error
    occured during page download or title cannot be extracted, returns
    a value of 'default_res' argument.

    """
    def cannot_get_warning(reference, exc):
        logging.warning('Cannot get a title for "%s": %s',
                        reference['url'], str(exc))

    log_header = '[get_title %d/%d] ' % (reference['num'], refs_cnt)
    logging.info(log_header + 'Download page from %s', reference['url'])
    try:
        html = get_page(reference['url'])
    except GetPageError as exc:
        cannot_get_warning(reference, exc)
        return default_res
    if html is None:
        return default_res
    logging.info(log_header + 'Extract title from the page')
    doc = lxml.html.document_fromstring(html)
    titles = doc.xpath('//title')
    if len(titles) == 0:
        return default_res
    res = ''
    try:
        title = titles[0].text
    except UnicodeDecodeError as exc:
        cannot_get_warning(reference, exc)
        return default_res
    for line in title.split('\n'):
        line = line.strip()
        if len(line) > 0:
            res += line + ' '
    return res.rstrip()


def full_url(url, context_url):
    """ Get full (absolute) URL from arbitrary URL and page where it placed.

    Assume 'context_url' are full url.

    """
    proto, tail = context_url.split(':', 1)
    context_base = proto + '://' + tail.lstrip('/').split('/', 1)[0]
    context_page = context_url.split('#', 1)[0]

    if url == '':
        return context_page
    elif url.startswith('#'):
        return context_page + url
    elif url.startswith('//'):
        return proto + ':' + url
    elif url.startswith('/'):
        return context_base.rstrip('/') + '/' + url.lstrip('/')
    elif url.startswith(('http://', 'https://', 'ftp://')):
        return url
    elif url.startswith('doi:'):
        return url
    else:
        # Need we support relational link like
        # 'smth.html', './smth.html', or '../smth.html'?
        raise NameError('bad url in \'full_url\':\nurl: ' + url + '\n')


def inner_html(node, strip=True):
    """ Get inner HTML from lxml node.

    https://stackoverflow.com/a/24151860/1598057

    """
    res = node.text or ''
    for child in node:
        res += lxml.html.tostring(child, encoding='unicode')
    if strip:
        res = res.strip()
    return res


def normalize_space(txt):
    """ Replace any space character or a sequence of space characters with one
    whitespace. It is similar to how a web browser interprets a text within an
    HTML tag.

    The idea comes from
    https://github.com/stevenvachon/normalize-html-whitespace
    """
    if not txt:
        return ''
    return re.sub(r'[\f\n\r\t\v ]+', ' ', txt)


def pop_footnotes(state):
    """ Get preparsed footnotes text and flush it. """
    res = ''
    for footnote in state['footnotes']:
        if footnote['is_multipar']:
            template = '[^%s]:\n%s'
            if NOTABENOID_SPACES_WORKAROUND:
                template = 'TODO: replace \'<-->\' with \'    \'\n' + template
        else:
            template = '[^%s]: %s'
        res += template % (footnote['num'], footnote['body'])
        res += state['par_sep']
    state['footnotes'] = []
    return res


def slugify(num, title):
    num_zero_filled = str(num).rjust(3, '0')
    title_slugified = title.lower() \
        .replace(' ', '-') \
        .replace('.', '') \
        .replace(',', '') \
        .replace("'", '') \
        .replace('!', '') \
        .replace('$', '') \
        .replace(':', '')
    return '{}-{}'.format(num_zero_filled, title_slugified)


def prefix_each_line(prefix, data):
    lines = [(line + '\n') for line in data.split('\n')]
    return prefix + prefix.join(lines).rstrip('\n')


def process_article_title(doc, state):
    """ Process the navigation bar and the <h2/> element.

    Add the article title into the result and fill 'slug'.

    """
    # Previous article number + 1. If the URL is just '#', it is the first
    # article.
    num = 1
    prev_button = doc.xpath('//body//nav/a/button[@class="prev"]')[0]
    href = prev_button.getparent().get('href')
    if href != '#':
        prev_url = full_url(href, context_url=state['base_url'])
        m = re.match(r'^https://[^/]+/(?P<num>\d+)/?(?:#.*)?$', prev_url)
        if not m:
            raise RuntimeError('Unexpected previous article URL: {}'.format(
                prev_url))
        num = int(m.group('num')) + 1

    title = doc.xpath('//body//h2[@id="title"]/a')[0].text.strip()
    url = 'https://what-if.xkcd.com/{}'.format(num)

    state['num'] = num
    state['slug'] = slugify(num, title)

    res = title + state['line_break']
    res += url + state['par_sep']
    return res


def process_a(a_elem, state):
    """ Process inline <a/> element (somewhere under <article/>). """
    txt = normalize_space(inner_html(a_elem))
    url = full_url(a_elem.get('href'), context_url=state['base_url'])

    # check if we already have that URL (in case of two or more links to the
    # same page)
    for ref in state['references']:
        if ref['url'] == url:
            return '[{}][{}]'.format(txt, ref['num'])

    res = '[{}][{}]'.format(txt, state['ref_counter'])
    ref = {
        'num': state['ref_counter'],
        'url': url,
    }
    state['references'].append(ref)
    state['ref_counter'] += 1
    return res


def process_childs(elem, state, em_mark='*', strong_mark='**'):
    """ Process some inline HTML element (somewhere under <article/>). """
    res = normalize_space(elem.text)
    for child in elem:
        tail_added = False
        # We can meet <p/> inside <blockquote/> as in
        # https://what-if.xkcd.com/160.
        if child.tag == 'p':
            # TODO: A formula inside <p/>, which is inside
            # <blockquote/>?
            res += process_childs(child, state)
            res += state['par_sep']
        elif child.tag == 'em':
            child_mark = '_' if em_mark == '*' else '*'
            res += em_mark
            res += process_childs(child, state, em_mark=child_mark)
            res += em_mark
        elif child.tag == 'strong' or child.tag == 'b':
            child_mark = '__' if strong_mark == '**' else '**'
            res += strong_mark
            res += process_childs(child, state, strong_mark=child_mark)
            res += strong_mark
        elif child.tag == 'a':
            res += process_a(child, state)
        elif child.tag == 'span':
            res += process_span(child, state)
        elif child.tag == 'sup':
            res += '^{'
            res += process_childs(child, state)
            res += '}'
        elif child.tag == 'sub':
            res += '_{'
            res += process_childs(child, state)
            res += '}'
        elif child.tag == 'br':
            res += state['par_sep']
        elif child.tag == 'img':
            res += process_img(child, state)
        else:
            tail = lxml.html.tostring(child, encoding='unicode')
            if res.endswith('\n'):
                tail = tail.lstrip()
            res += tail
            tail_added = True
        if not tail_added:
            tail = normalize_space(child.tail)
            if res.endswith('\n'):
                tail = tail.lstrip()
            res += tail
    return res


def process_span(span, state):
    """ Process inline <span/> element (somewhere under <article/>).

    Detect footnotes (its formatted as <span/>) and save its into 'state',
    later it will extracted in 'pop_footnotes' function. If span element isn't
    footnote, then return raw its content.

    """
    if span.get('class') != 'ref':
        return lxml.html.tostring(span, encoding='unicode')

    res = '[^%s]' % state['fn_counter']
    refbody = span.xpath('./span[@class="refbody"]')[0]
    # TODO: formulas in footnotes?
    refbody_parsed = process_childs(refbody, state).strip()
    is_multipar = state['par_sep'] in refbody_parsed
    if is_multipar:
        new_refbody = ''
        refbody_pars = refbody_parsed.split(state['par_sep'])
        for par in refbody_pars:
            for line in par.split(state['line_break']):
                new_refbody += state['indent'] + line + state['line_break']
            new_refbody = new_refbody.rstrip() + state['par_sep']
        refbody_parsed = new_refbody.rstrip()
    footnote = {
        'num': state['fn_counter'],
        'body': refbody_parsed,
        'is_multipar': is_multipar,
    }
    state['footnotes'].append(footnote)
    state['fn_counter'] += 1
    return res


def maybe_formula(par):
    """ Returns a non-inline formula or empty string if it isn't detected. """
    if par.lstrip().startswith(r'\[') and par.rstrip().endswith(r'\]'):
        return '$$ ' + par.strip()[2:-2].strip() + ' $$'
    else:
        return ''


def process_toplevel_p(p_elem, state):
    """ Process toplevel <p/> element (child of <article/>).

    Detect a question (citate) <p/> element and a non-inline formula. Dump
    paragraph footnotes after it.

    """
    is_question = 'id' in p_elem.attrib and p_elem.attrib['id'] == 'question'
    is_attribute = 'id' in p_elem.attrib and p_elem.attrib['id'] == 'attribute'
    res = ''
    if is_question or is_attribute:
        res += '> '
    formula = maybe_formula(p_elem.text or '')
    if formula:
        res += formula
    else:
        res += process_childs(p_elem, state)
    if is_question:
        res += state['line_break'] + '>' + state['line_break']
    else:
        res += state['par_sep']
    res += pop_footnotes(state)
    return res


def process_toplevel_blockquote(elem, state):
    """ Process toplevel <blockquote/> element (child of <article/>).

    Detect non-inline formula. Dump paragraph footnotes after an element.

    """
    # TODO: check for formula only for entire fragment
    res = maybe_formula(elem.text or '')
    res += process_childs(elem, state)
    res = prefix_each_line('> ', res.strip())

    res += state['par_sep']
    res += pop_footnotes(state)
    return res


def process_toplevel_img(img, state):
    """ Process toplevel <img/> element (child of <article/>). """
    url = full_url(img.get('src'), context_url=state['base_url'])
    img_file = url.rstrip('/').rsplit('/', 1)[1]
    img_name, img_ext = img_file.rsplit('.')
    img_file_ru = img_name + '_ru.' + img_ext

    title_text = img.get('title').replace('"', '\\"')
    if len(title_text) == 0:
        res = '![](/uploads/%s/%s)' % \
            (state['slug'], img_file_ru) + state['line_break']
    else:
        res = '![](/uploads/%s/%s "%s")' % \
            (state['slug'], img_file_ru, title_text) + state['line_break']
    res += '[labels]' + state['line_break']
    res += 'TODO' + state['line_break']
    res += '[/labels]' + state['line_break']
    res += 'render: ![](%s)' % url + state['par_sep']
    return res


def process_img(img, state):
    """ Hack for correctly handle for images in multiparagraph
    footnotes.

    """
    return process_toplevel_img(img, state)


def postprocess_references(state):
    """ Format and return preparsed references. """
    res = ''
    refs_cnt = len(state['references'])
    for reference in state['references']:
        if state['args']['no_link_title']:
            title_text = 'TODO'
        else:
            title_text = get_title(reference, refs_cnt).replace('"', '\\"')
        res += '[%s]: %s "%s"' % \
            (reference['num'], reference['url'], title_text) + state['par_sep']
    return res


def new_parser(url, args):
    """ Return new (clean) parser state. """
    state = {
        'num': None,
        'slug': None,
        'base_url': url,
        'ref_counter': 1,
        'fn_counter': 1,
        'par_sep': '\n\n',
        'line_break': '\n',
        'indent': ' ' * 4,
        'footnotes': [],
        'references': [],
        'args': args,
    }
    if NOTABENOID_SPACES_WORKAROUND:
        state['indent'] = '<-->'
    return state


def process_article(url, html, args):
    """ Process all toplevel article elements (childs of <article/>).

    In markdown references added after all text paragraps (HTML toplevel
    elements representation). Returns article HTML (cutted from entire HTML),
    markdown and a 'slug' (king of article id, for using in filenames).

    """
    # The source HTML has no <meta charset="..."> tag. We should point the
    # source HTML encoding to lxml. Let's add the tag manually: I see no other
    # way to point the encoding. See also the get_page() comment.
    html = re.sub(b'<head>', b'<head><meta charset="utf-8">', html, 1)

    doc = lxml.html.document_fromstring(html)
    article = doc.xpath('//body//article')[0]
    article_html = inner_html(article)

    state = new_parser(url, args)

    res = process_article_title(doc, state)
    childs_cnt = len(article)
    childs_processed = 0
    func_dict = {
        'p': process_toplevel_p,
        'blockquote': process_toplevel_blockquote,
        'img': process_toplevel_img,
    }
    for child in article:
        logging.info('Processed %d/%d top level elements',
                     childs_processed, childs_cnt)
        if child.tag in func_dict.keys():
            res += func_dict[child.tag](child, state)
        else:
            logging.warning('Unexpected toplevel element: ' + child.tag)
        childs_processed += 1

    logging.info('Postprocessing references...')
    res += postprocess_references(state)

    return article_html, res.strip(), state


def usage(file=sys.stderr):
    """ Print info how to use the script. """
    print('\
Usage: %s [options] [num]\n\
\n\
The script will generate two files with naming scheme\n\
{num}-{title}-{timestamp}.{html,md}\n\
\n\
If "num" has special value "all", all articles are processed and stored\n\
in a "articles-{timestamp}" directory.\n\
\n\
Available options are the following.\n\
\n\
--native-newline  Don\'t replace native end of line character (EOL)\n\
                  with LF, which used by default. Be careful, native\n\
                  EOL can be painful when you try to diff\'ing changes\n\
                  across several OSes.\n\
\n\
--no-link-title   Don\'t collect titles for linked pages. It speeds up the\n\
                  process a lot.\n\
\n\
--help | -h | -?  Display this cheatsheet.' % sys.argv[0], file=file)


def get_args():
    """ Return URL and flags to process, set logging level. Print
    help and exit when user ask to help or provide wrong arguments.

    """
    has_url = False
    url = 'https://what-if.xkcd.com'
    args = {
        'native_newline': False,
        'verbose': False,
        'no_link_title': False,
        'fetch_all_articles': False,
        'output_directory': '.',
        'timestamp_in_filename': True,
    }

    if sys.argv[0].endswith('what_if_parse_all.py'):
        sys.argv.append('--no-link-title')
        sys.argv.append('--verbose')
        sys.argv.append('all')

    for a in sys.argv[1:]:
        if a in ('--help', '-h', '-?'):
            usage(file=sys.stdout)
            exit(EXIT_SUCCESS)
        elif a in ('--verbose', '-v'):
            args['verbose'] = True
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.INFO)
        elif a == '--native-newline':
            args['native_newline'] = True
        elif a == '--no-link-title':
            args['no_link_title'] = True
        elif a.isdigit() or a == 'all':
            if has_url:
                logging.critical(
                    'An article number found at least twice in arguments')
                usage()
                exit(EXIT_WRONG_ARGS)
            elif a == 'all':
                args['fetch_all_articles'] = True
                args['output_directory'] = 'articles-{timestamp}'.format(
                    timestamp=timestamp())
                args['timestamp_in_filename'] = False
                has_url = True
            else:
                url = 'https://what-if.xkcd.com/{num}/'.format(
                    num=a.lstrip('0'))
                has_url = True
        else:
            usage()
            exit(EXIT_WRONG_ARGS)

    return (url, args)


def download_article(url):
    """ Return string with HTML of requested article or exit with
    an error.

    """
    logging.info('Download article from %s', url)
    try:
        html = get_page(url, raise_non_text_html=True)
    except GetPageError as exc:
        logging.critical('==== Following error occured when getting page ====')
        logging.critical(str(exc))
        logging.critical('==== Exiting ===')
        exit(EXIT_GET_PAGE_ERROR)
    return html


def save_article(slug, args, a_html, a_md):
    """ Write resulting HTML and Markdown to appropriate files. """
    if args['timestamp_in_filename']:
        tstamp = timestamp()
        html_file = '{slug}-{tstamp}.html'.format(slug=slug, tstamp=tstamp)
        md_file = '{slug}-{tstamp}.md'.format(slug=slug, tstamp=tstamp)
    else:
        html_file = '{slug}.html'.format(slug=slug)
        md_file = '{slug}.md'.format(slug=slug)

    odir = args['output_directory']
    html_file = os.path.join(odir, html_file)
    md_file = os.path.join(odir, md_file)

    safe_makedirs(odir)

    # https://stackoverflow.com/a/23434608
    newline = None if args['native_newline'] else ''
    with io.open(html_file, 'w', encoding='utf-8', newline=newline) as f:
        logging.info('Write article in html to file %s', html_file)
        f.write(a_html + '\n')
    with open(md_file, 'w', encoding='utf-8', newline=newline) as f:
        logging.info('Write article in markdown to file %s', md_file)
        f.write(a_md + '\n')


def prettify_logging():
    """ Setup logger format. """
    # TODO: colors when isatty()
    root_logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '{asctime} {levelname:4s} {message}', style='{')
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def main():
    """ Main actions sequence.

    Get and check arguments, download and parse article, write results
    to files.

    """
    prettify_logging()
    url, args = get_args()
    if args['fetch_all_articles']:
        while True:
            html = download_article(url)
            a_html, a_md, state = process_article(url, html, args)
            slug = state['slug']
            num = state['num']
            save_article(slug, args, a_html, a_md)
            if num == 1:
                break
            url = 'https://what-if.xkcd.com/{num}/'.format(num=num-1)
    else:
        html = download_article(url)
        a_html, a_md, state = process_article(url, html, args)
        slug = state['slug']
        save_article(slug, args, a_html, a_md)


if __name__ == '__main__':
    main()
