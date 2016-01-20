#!/usr/bin/env python3

""" Main what-if downloading and parsing module

The module defines set of functions for downloading and parsing articles from
'http://what-if.xkcd.com'.

"""

# TODO's residence:
# * --quiet|-q option for disabling progress reports

import sys
import requests
from requests.exceptions import RequestException, BaseHTTPError
import lxml.html


EXIT_WRONG_ARGS = 1
EXIT_GET_PAGE_ERROR = 2


class GetPageError(Exception):
    """ The exception raised when smth went wrong in 'get_page' function. """
    pass


def get_page(url, utf8=False):
    """ Get HTML page or raise GetPageError exception.

    If content-type header isn't 'text/html' the exception raised as well as
    when download error occured.

    """
    # Disable pylint error message for 'requests.code.ok':
    # > Instance of 'LookupDict' has no 'ok' member (no-member)
    # pylint: disable=E1101
    try:
        req = requests.get(url, headers={'Accept': 'text/html'})
    except (RequestException, BaseHTTPError):
        print('[get_page] Exception occured at http request performing: ' \
            + url, file=sys.stderr)
        raise GetPageError()
    if req.status_code != requests.codes.ok:
        print('[get_page] HTTP status code: %d; url: %s' % \
            (req.status_code, url), file=sys.stderr)
        raise GetPageError()
    if utf8:
        req.encoding = 'utf-8'
    content_type = req.headers['content-type']
    if content_type.startswith('text/html'):
        return req.text
    else:
        print('[get_page] Content type "%s" != "text/html"; url: %s' % \
            (content_type, url), file=sys.stderr)
        raise GetPageError()


def get_title(reference, refs_cnt, default_res='TODO'):
    """ Get title of page by its url.

    Download page from reference['url'] and extract title. If some error
    occured, 'default_res' value returned.

    """
    header = '[get_title %d/%d] ' % (reference['num'], refs_cnt)
    print(header + 'Download page from %s' % reference['url'], file=sys.stderr)
    try:
        html = get_page(reference['url'])
    except GetPageError:
        print(header + 'Skip title extracting: get page error or wrong html page', \
            file=sys.stderr)
        return default_res
    print(header + 'Extract title from the page', file=sys.stderr)
    doc = lxml.html.document_fromstring(html)
    titles = doc.xpath('//title')
    if len(titles) == 0:
        return default_res
    res = ''
    for line in titles[0].text.split('\n'):
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


def inner_html(node, strip=True):
    """ Get inner HTML from lxml node.

    http://stackoverflow.com/a/24151860/1598057

    """
    res = node.text or ''
    for child in node:
        res += lxml.html.tostring(child, encoding='unicode')
    if strip:
        res = res.strip()
    return res


def pop_footnotes(state):
    """ Get preparsed footnotes text and flush it. """
    res = ''
    for footnote in state['footnotes']:
        res += '[^%s]: %s' % (footnote['num'], footnote['body']) + \
            state['par_sep']
    state['footnotes'] = []
    return res


def process_toplevel_a(a_elem, state):
    """ Process toplevel <a/> element (child of <article/>). """
    title = a_elem.xpath('./h1')[0].text.strip()
    url = full_url(a_elem.get('href'), context_url=state['base_url'])
    num = int(url.rstrip('/').rsplit('/', 1)[1])

    state['slug'] = str(num).rjust(3, '0') + '-' + title.lower() \
        .replace(' ', '-').replace('.', '').replace(',', '')

    res = title + state['line_break']
    res += url + state['par_sep']
    return res


def process_a(a_elem, state):
    """ Process inline <a/> element (somewhere under <article/>). """
    res = '[%s][%d]' % (inner_html(a_elem), state['ref_counter'])
    ref = {
        'num': state['ref_counter'],
        'url': full_url(a_elem.get('href'), context_url=state['base_url']),
    }
    state['references'].append(ref)
    state['ref_counter'] += 1
    return res


def process_childs(elem, state, em_mark='*', strong_mark='**'):
    """ Process some inline HTML element (somewhere under <article/>). """
    res = elem.text or ''
    for child in elem:
        tail_added = False
        if child.tag == 'em':
            child_mark = '_' if em_mark == '*' else '*'
            res += em_mark
            res += process_childs(child, state, em_mark=child_mark)
            res += em_mark
        elif child.tag == 'strong':
            child_mark = '__' if strong_mark == '**' else '**'
            res += strong_mark
            res += process_childs(child, state, strong_mark=child_mark)
            res += strong_mark
        elif child.tag == 'a':
            res += process_a(child, state)
        elif child.tag == 'span':
            res += process_span(child, state)
        elif child.tag == 'sup':
            res += '<sup>'
            res += process_childs(child, state)
            res += '</sup>'
        else:
            res += lxml.html.tostring(child, encoding='unicode')
            tail_added = True
        if not tail_added:
            res += child.tail or ''
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
    footnote = {
        'num': state['fn_counter'],
        'body': refbody_parsed,
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
    # TODO: check for formula only for entire fragment
    res += maybe_formula(p_elem.text or '')
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
    res = '> '
    # TODO: check for formula only for entire fragment
    res += maybe_formula(elem.text or '')
    res += process_childs(elem, state)
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
        res = '![](/uploads/%s/%s)' % (state['slug'], img_file_ru) + \
            state['line_break']
    else:
        res = '![](/uploads/%s/%s "%s")' % (state['slug'], img_file_ru, \
            title_text) + state['line_break']
    res += '[labels]' + state['line_break']
    res += 'TODO' + state['line_break']
    res += '[/labels]' + state['line_break']
    res += 'render: ![](%s)' % url + state['par_sep']
    return res


def postprocess_references(state):
    """ Format and return preparsed references. """
    res = ''
    refs_cnt = len(state['references'])
    for reference in state['references']:
        title_text = get_title(reference, refs_cnt).replace('"', '\\"')
        res += '[%s]: %s "%s"' % (reference['num'], reference['url'], \
            title_text) + state['par_sep']
    return res


def new_parser(url):
    """ Return new (clean) parser state. """
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
    """ Process all toplevel article elements (childs of <article/>).

    In markdown references added after all text paragraps (HTML toplevel
    elements representation). Returns article HTML (cutted from entire HTML),
    markdown and a 'slug' (king of article id, for using in filenames).

    """
    doc = lxml.html.document_fromstring(html)
    article = doc.xpath('//body//article')[0]
    article_html = inner_html(article)

    state = new_parser(url)

    res = ''
    childs_cnt = len(article)
    childs_processed = 0
    func_dict = {
        'a': process_toplevel_a,
        'p': process_toplevel_p,
        'blockquote': process_toplevel_blockquote,
        'img': process_toplevel_img,
    }
    for child in article:
        print('Processed %d/%d top level elements' % (childs_processed, \
            childs_cnt), file=sys.stderr)
        if child.tag in func_dict.keys():
            res += func_dict[child.tag](child, state)
        else:
            print('Unexpected toplevel element: ' + child.tag, file=sys.stderr)
        childs_processed += 1

    print('Postprocessing references...', file=sys.stderr)
    res += postprocess_references(state)

    return article_html, res.strip(), state['slug']


def main():
    """ Main actions sequence.

    Get and check arguments, call downloading and parsing functions, write
    results to files.

    """
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
    except GetPageError:
        print('Error when getting page, exitting...', file=sys.stderr)
        exit(EXIT_GET_PAGE_ERROR)

    article_html, article_md, slug = process_article(url, html)

    html_file = slug + '.html'
    md_file = slug + '.md'

    with open(html_file, 'w', encoding='utf-8') as html_file_fd:
        print('Write article in html to file %s' % html_file, \
            file=sys.stderr)
        print(article_html, file=html_file_fd)
    with open(md_file, 'w', encoding='utf-8') as md_file_fd:
        print('Write article in markdown to file %s' % md_file, \
            file=sys.stderr)
        print(article_md, file=md_file_fd)


if __name__ == '__main__':
    main()
