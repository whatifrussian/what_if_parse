#!/usr/bin/python3

# TODO's residence:
# * cross OS packaging
# * pylint
# * documenting (README, docstring)
# * --quiet|-q option for disabling progress reports

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
        print('[get_page] Content type "%s" != "text/html"; url: %s' % \
            (content_type, url), file=sys.stderr)
        raise GetPageError()


def get_title(ref, refs_cnt, default_res='TODO'):
    header = '[get_title %d/%d] ' % (ref['num'], refs_cnt)
    print(header + 'Download page from %s' % ref['url'], file=sys.stderr)
    try:
        html = get_page(ref['url'])
    except GetPageError as e:
        print(header + 'Skip title extracting: get page error or wrong html page', \
            file=sys.stderr)
        return default_res
    print(header + 'Extract title from the page', file=sys.stderr)
    doc = lxml.html.document_fromstring(html)
    ts = doc.xpath('//title')
    if len(ts) == 0:
        return default_res
    res = ''
    for line in ts[0].text.split('\n'):
        line = line.strip()
        if len(line) > 0:
            res += line + ' '
    return res.rstrip()


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


def pop_footnotes(s):
    res = ''
    for fn in s['footnotes']:
        res += '[^%s]: %s' % (fn['num'], fn['body']) + s['par_sep']
    s['footnotes'] = []
    return res


def process_toplevel_a(a, s):
    title = a.xpath('./h1')[0].text.strip()
    url = full_url(a.get('href'), context_url=s['base_url'])
    num = int(url.rstrip('/').rsplit('/', 1)[1])

    s['slug'] = str(num).rjust(3, '0') + '-' + title.lower() \
        .replace(' ', '-').replace('.', '')

    res = title + s['line_break']
    res += url + s['par_sep']
    return res


def process_a(a, s):
    res = '[%s][%d]' % (innerHTML(a), s['ref_counter'])
    ref = {
        'num': s['ref_counter'],
        'url': full_url(a.get('href'), context_url=s['base_url']),
    }
    s['references'].append(ref)
    s['ref_counter'] += 1
    return res


def process_childs(elem, s, em_mark='*', strong_mark='**'):
    res = elem.text or ''
    for child in elem:
        tail_added = False
        if child.tag == 'em':
            child_mark = '_' if em_mark == '*' else '*'
            res += em_mark
            res += process_childs(child, s, em_mark=child_mark)
            res += em_mark
        elif child.tag == 'strong':
            child_mark = '__' if strong_mark == '**' else '**'
            res += strong_mark
            res += process_childs(child, s, strong_mark=child_mark)
            res += strong_mark
        elif child.tag == 'a':
            res += process_a(child, s)
        elif child.tag == 'span':
            res += process_span(child, s)
        elif child.tag == 'sup':
            res += '<sup>'
            res += process_childs(child, s)
            res += '</sup>'
        else:
            res += lxml.html.tostring(child, encoding='unicode')
            tail_added = True
        if not tail_added:
            res += child.tail or ''
    return res


def process_span(span, s):
    if span.get('class') != 'ref':
        return lxml.html.tostring(span, encoding='unicode')

    res = '[^%s]' % s['fn_counter']
    refbody = span.xpath('./span[@class="refbody"]')[0]
    # TODO: formulas in footnotes?
    refbody_parsed = process_childs(refbody, s).strip()
    footnote = {
        'num': s['fn_counter'],
        'body': refbody_parsed,
    }
    s['footnotes'].append(footnote)
    s['fn_counter'] += 1
    return res


def maybe_formula(par):
    if par.lstrip().startswith(r'\[') and par.rstrip().endswith(r'\]'):
        return '$$ ' + par.strip()[2:-2].strip() + ' $$'
    else:
        return ''


def process_toplevel_p(p, s):
    is_question = 'id' in p.attrib and p.attrib['id'] == 'question'
    is_attribute = 'id' in p.attrib and p.attrib['id'] == 'attribute'
    res = ''
    if is_question or is_attribute:
        res += '> '
    # TODO: check for formula only for entire fragment
    res += maybe_formula(p.text or '')
    res += process_childs(p, s)
    if is_question:
        res += s['line_break'] + '>' + s['line_break']
    else:
        res += s['par_sep']
    res += pop_footnotes(s)
    return res


def process_toplevel_img(img, s):
    url = full_url(img.get('src'), context_url=s['base_url'])
    img_file = url.rstrip('/').rsplit('/', 1)[1]
    img_name, img_ext = img_file.rsplit('.')
    img_file_ru = img_name + '_ru.' + img_ext

    res = '![](/uploads/%s/%s "%s")' % (s['slug'], img_file_ru, \
        img.get('title')) + s['line_break']
    res += '[labels]' + s['line_break']
    res += 'TODO' + s['line_break']
    res += '[/labels]' + s['line_break']
    res += 'render: ![](%s)' % url + s['par_sep']
    return res


def postprocess_references(s):
    res = ''
    refs_cnt = len(s['references'])
    for ref in s['references']:
        title = get_title(ref, refs_cnt)
        res += '[%s]: %s "%s"' % (ref['num'], ref['url'], title) + \
            s['par_sep']
    return res


def new_parser(url):
    return {
        'slug': None,
        'base_url': url,
        'ref_counter': 1,
        'fn_counter': 1,
        'par_sep': '\n\n',
        'line_break': '\n',
        'footnotes': [],
        'references': [],
    }


def process_article(url, html):
    doc = lxml.html.document_fromstring(html)
    article = doc.xpath('//body//article')[0]
    article_html = innerHTML(article)

    parser_state = new_parser(url)

    res = ''
    childs_cnt = len(article)
    childs_processed = 0
    func_dict = {
        'a': process_toplevel_a,
        'p': process_toplevel_p,
        'img': process_toplevel_img,
    }
    for child in article:
        print('Processed %d/%d top level elements' % (childs_processed, \
            childs_cnt), file=sys.stderr)
        if child.tag in func_dict.keys():
            res += func_dict[child.tag](child, parser_state)
        else:
            print('Unexpected toplevel element: ' + child.tag, file=sys.stderr)
        childs_processed += 1

    print('Postprocessing references...', file=sys.stderr)
    res += postprocess_references(parser_state)

    return article_html, res.strip(), parser_state['slug']


if __name__ == '__main__':
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

    article_html, article_md, slug = process_article(url, html)

    html_file = slug + '.html'
    md_file = slug + '.md'

    with open(html_file, 'w', encoding='utf-8') as f:
        print('Write article in html to file %s' % html_file, \
            file=sys.stderr)
        print(article_html, file=f)
    with open(md_file, 'w', encoding='utf-8') as f:
        print('Write article in markdown to file %s' % md_file, \
            file=sys.stderr)
        print(article_md, file=f)
