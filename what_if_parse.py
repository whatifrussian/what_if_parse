#!/usr/bin/python3

# TODO's residence:
# * deduplicate code
# * cross OS packaging
# * pylint
# * documenting (README, docstring)
#
# Issues:
# * references in footnotes
# * don't switch italic/bold mark when its isn't beside

import sys
import requests
from requests.exceptions import RequestException, BaseHTTPError
import lxml.html


EXIT_WRONG_ARGS = 1
EXIT_GET_PAGE_ERROR = 2


class GetPageError(Exception):
    pass


def get_page(url, utf8=False):
    try:
        r = requests.get(url, headers={'Accept': 'text/html'})
    except (RequestException, BaseHTTPError) as e:
        print('[get_page] Exception occured at http request performing: ' \
            + url, file=sys.stderr)
        raise GetPageError()
    if r.status_code != requests.codes.ok:
        print('[get_page] HTTP status code: %d; url: %s' % \
            (r.status_code, url), file=sys.stderr)
        raise GetPageError()
    if utf8:
        r.encoding = 'utf-8'
    content_type = r.headers['content-type']
    if content_type.startswith('text/html'):
        return r.text
    else:
        print('[get_page] Content type "%s" != "text/html": ; url: %s' % \
            (content_type, url), file=sys.stderr)
        raise GetPageError()


def get_title(url, default_res='TODO'):
    print('[get_title] Download page from %s' % url, file=sys.stderr)
    try:
        html = get_page(url)
    except GetPageError as e:
        print('[get_title] Skip title extracting: get page error or wrong html page', \
            file=sys.stderr)
        return default_res
    print('[get_title] Extract title from the page', file=sys.stderr)
    doc = lxml.html.document_fromstring(html)
    ts = doc.xpath('//title')
    return ts[0].text.strip() if len(ts) >= 1 else default_res


# assume 'context_url' are full url
def full_url(url, context_url):
    proto, tail = context_url.split(':', 1)
    context_base = proto + '://' + tail.lstrip('/').split('/', 1)[0]

    if url.startswith('#'):
        context_page = context_url.split('#', 1)[0]
        return context_page + url
    elif url.startswith('//'):
        return proto + ':' + url
    elif url.startswith('/'):
        return context_base.rstrip('/') + '/' + url.lstrip('/')
    elif url.startswith(('http://', 'https://', 'ftp://')):
        return url
    else:
        # Need we support relational link like
        # 'smth.html', './smth.html', or '../smth.html'?
        raise NameError('bad url in \'full_url\':\nurl: ' + url + '\n')


# http://stackoverflow.com/a/24151860/1598057
def innerHTML(node, strip=True):
    res = node.text or ''
    for child in node:
        res += lxml.html.tostring(child, encoding='unicode')
    if strip:
        res = res.strip()
    return res


def process_footnotes(s):
    for fn in s['footnotes']:
        s['res'] += '[^%s]: %s' % (fn['num'], fn['body']) + s['par_sep']
    s['footnotes'] = []


def process_toplevel_a(a, s):
    title = a.xpath('./h1')[0].text.strip()
    url = full_url(a.get('href'), context_url=s['base_url'])
    num = int(url.rstrip('/').rsplit('/', 1)[1])

    s['slug'] = str(num).rjust(3, '0') + '-' + title.lower() \
        .replace(' ', '-').replace('.', '')
    s['res'] += title + s['line_break']
    s['res'] += url + s['par_sep']


def process_a(a, s):
    s['res'] += '[%s][%d]' % (innerHTML(a), s['ref_counter'])
    ref = {
        'num': s['ref_counter'],
        'url': full_url(a.get('href'), context_url=s['base_url']),
    }
    s['references'].append(ref)
    s['ref_counter'] += 1


# TODO: make it in some other way
def ret_span(span, orig_s):
    s = {
        'base_url': orig_s['base_url'],
        'ref_counter': 1,
        'fn_counter': 1,
        'par_sep': '\n\n',
        'line_break': '\n',
        'res': '',
        'footnotes': [],
        'references': [],
    }
    process_toplevel_p(span, s)
    return s['res'].strip()


def process_span(span, s):
    # TODO: extract number, don't reenum via 'fn_counver'
    if span.get('class') != 'ref':
        s['res'] += lxml.html.tostring(span, encoding='unicode')
        return

    s['res'] += '[^%s]' % s['fn_counter']
    footnote = {
        'num': s['fn_counter'],
        'body': ret_span(span.xpath('./span[@class="refbody"]')[0], s),
    }
    s['footnotes'].append(footnote)
    s['fn_counter'] += 1


def process_strong(strong, deep_level, s):
    s['res'] += '**' if (deep_level % 2 == 0) else '__'
    s['res'] += strong.text or ''
    for child in strong:
        tail_added = False
        if child.tag == 'em':
            process_em(child, deep_level + 1, s)
        elif child.tag == 'strong':
            process_strong(child, deep_level + 1, s)
        elif child.tag == 'a':
            process_a(child, s)
        elif child.tag == 'span':
            process_span(child, s)
        else:
            s['res'] += lxml.html.tostring(child, encoding='unicode')
            tail_added = True
        if not tail_added:
            s['res'] += child.tail or ''
    s['res'] += '**' if (deep_level % 2 == 0) else '__'


# TODO: deduplicate code
def process_em(em, deep_level, s):
    s['res'] += '*' if (deep_level % 2 == 0) else '_'
    s['res'] += em.text or ''
    for child in em:
        tail_added = False
        if child.tag == 'em':
            process_em(child, deep_level + 1, s)
        elif child.tag == 'strong':
            process_strong(child, deep_level + 1, s)
        elif child.tag == 'a':
            process_a(child, s)
        elif child.tag == 'span':
            process_span(child, s)
        else:
            s['res'] += lxml.html.tostring(child, encoding='unicode')
            tail_added = True
        if not tail_added:
            s['res'] += child.tail or ''
    s['res'] += '*' if (deep_level % 2 == 0) else '_'


def maybe_formula(par):
    if par.lstrip().startswith(r'\[') and par.rstrip().endswith(r'\]'):
        return '$$ ' + par.strip()[2:-2].strip() + ' $$'
    else:
        return par


def process_toplevel_p(p, s):
    is_question = 'id' in p.attrib and p.attrib['id'] == 'question'
    is_attribute = 'id' in p.attrib and p.attrib['id'] == 'attribute'
    if is_question or is_attribute:
        s['res'] += '> '
    # TODO: check for formula only for entire fragment
    s['res'] += maybe_formula(p.text or '')
    for child in p:
        tail_added = False
        if child.tag == 'em':
            process_em(child, 0, s)
        elif child.tag == 'strong':
            process_strong(child, 0, s)
        elif child.tag == 'a':
            process_a(child, s)
        elif child.tag == 'span':
            process_span(child, s)
        elif child.tag == 'sup':
            s['res'] += '<sup>' + ret_span(child, s) + '</sup>'
        else:
            s['res'] += lxml.html.tostring(child, encoding='unicode')
            tail_added = True
        if not tail_added:
            s['res'] += child.tail or ''
    if is_question:
        s['res'] += s['line_break'] + '>' + s['line_break']
    else:
        s['res'] += s['par_sep']
    process_footnotes(s)


def process_toplevel_img(img, s):
    url = full_url(img.get('src'), context_url=s['base_url'])
    img_file = url.rstrip('/').rsplit('/', 1)[1]
    img_name, img_ext = img_file.rsplit('.')
    img_file_ru = img_name + '_ru.' + img_ext
    s['res'] += '![](/uploads/%s/%s "%s")' % (s['slug'], img_file_ru, \
        img.get('title')) + s['line_break']
    s['res'] += '[labels]' + s['line_break']
    s['res'] += 'TODO' + s['line_break']
    s['res'] += '[/labels]' + s['line_break']
    s['res'] += 'render: ![](%s)' % url + s['par_sep']


def postprocess_references(s):
    for ref in s['references']:
        # TODO: check for spaces and so on
        title = get_title(ref['url'])
        s['res'] += '[%s]: %s "%s"' % (ref['num'], ref['url'], title) + \
            s['par_sep']

if len(sys.argv) == 1:
    url = 'http://what-if.xkcd.com'
elif len(sys.argv) == 2 and sys.argv[1].isdigit():
    url = 'http://what-if.xkcd.com/' + sys.argv[1].lstrip('0')
else:
    print('Usage: %s [num]' % sys.argv[0], file=sys.stderr)
    exit(EXIT_WRONG_ARGS)

print('Download article from %s' % url, file=sys.stderr)
try:
    html = get_page(url, utf8=True)
except GetPageError as e:
    print('Error when getting page, exitting...', file=sys.stderr)
    exit(EXIT_GET_PAGE_ERROR)
doc = lxml.html.document_fromstring(html)
article = doc.xpath('//body//article')[0]
article_html = innerHTML(article)

parser_state = {
    'slug': None,
    'base_url': url,
    'ref_counter': 1,
    'fn_counter': 1,
    'par_sep': '\n\n',
    'line_break': '\n',
    'res': '',
    'footnotes': [],
    'references': [],
}

childs_cnt = len(article)
childs_processed = 0
for child in article:
    print('Processed %d/%d top level elements' % (childs_processed, \
        childs_cnt), file=sys.stderr)
    if child.tag == 'a':
        process_toplevel_a(child, parser_state)
    elif child.tag == 'p':
        process_toplevel_p(child, parser_state)
    elif child.tag == 'img':
        process_toplevel_img(child, parser_state)
    childs_processed += 1

print('Postprocessing references...', file=sys.stderr)
postprocess_references(parser_state)

html_file = parser_state['slug'] + '.html'
md_file = parser_state['slug'] + '.md'

with open(html_file, 'w', encoding='utf-8') as f:
    print('Write article in html to file %s' % html_file, file=sys.stderr)
    print(article_html, file=f)
with open(md_file, 'w', encoding='utf-8') as f:
    print('Write article in markdown to file %s' % md_file, file=sys.stderr)
    print(parser_state['res'].rstrip(), file=f)
