#!/usr/bin/env python3

""" Unit testing module for what-if parser. """


from unittest.mock import Mock, patch

from what_if_parse import GetPageError, full_url, get_page, process_article
import unittest


class ParserTests(unittest.TestCase):
    """ Set of tests for HTML to markdown parsing. """
    PAGE_TITLE = 'A testing title'
    PREV_URL = 'https://what-if.xkcd.com/9999/'
    NEXT_URL = 'https://what-if.xkcd.com/10001/'
    PAGE_URL = 'https://what-if.xkcd.com/10000/'
    HTML_TMPL = """
        <html><body><section id="entry-wrapper">'
            <nav class="main-nav">'
                <a href="{prev_url}">
                    <button class="prev">&#x25c0;&#xFE0E;</button>
                </a>
                <a href="{next_url}">
                    <button class="next">&#x25b6;&#xFE0E;</button>
                </a>
            </nav>
            <h2 id="title"><a href="">{title}</a></h2>
            <article>
                {article_html}
            </article>
        </section></body></html>
    """

    def do_check_equal(self, article_html, article_md):
        """ Wrap HTML paragraps into the template, parse and equal check."""
        html = bytes(self.HTML_TMPL.format(
            prev_url=self.PREV_URL,
            next_url=self.NEXT_URL,
            title=self.PAGE_TITLE,
            article_html=article_html), encoding='utf-8')
        args = {
            'native_newline': False,
            'verbose': False,
            'no_link_title': False,
        }
        md = process_article(ParserTests.PAGE_URL, html, args)[1]

        exp = '{title}\n{page_url}\n\n{article_md}'.format(
                title=self.PAGE_TITLE,
                page_url=self.PAGE_URL.rstrip('/'),
                article_md=article_md)
        self.assertEqual(md, exp)

    def setUp(self):
        """ Setting up, nothing to do. """
        pass

    def test_italic_1(self):
        """ Test a italic text inside a italic text. """
        article_html = '<p><em>abc<em>012</em>def</em></p>'
        article_md = '*abc_012_def*'
        self.do_check_equal(article_html, article_md)

    def test_bold_italic_1(self):
        """ Test a bold text inside a italic text. """
        article_html = '<p><em>abc<strong>012</strong>def</em></p>'
        article_md = '*abc**012**def*'
        self.do_check_equal(article_html, article_md)

    def test_modern_navigation_without_buttons(self):
        """The article number comes from its URL, not fragile button HTML."""
        html = bytes(self.HTML_TMPL.format(
            prev_url='/9999/',
            next_url='/10001/',
            title='<span>A testing title</span>',
            article_html='<p>Body</p>',
        ).replace('<button class="prev">&#x25c0;&#xFE0E;</button>', 'Previous')
          .replace('<button class="next">&#x25b6;&#xFE0E;</button>', 'Next'),
          encoding='utf-8')
        state = process_article(self.PAGE_URL, html, {
            'native_newline': False,
            'verbose': False,
            'no_link_title': True,
        })[2]
        self.assertEqual(state['num'], 10000)
        self.assertEqual(state['slug'], '10000-a-testing-title')

    def test_relative_url(self):
        self.assertEqual(
            full_url('../images/example.png', self.PAGE_URL),
            'https://what-if.xkcd.com/images/example.png',
        )

    @patch('what_if_parse.requests.get')
    def test_get_page_uses_get_without_head(self, get):
        response = Mock(
            content=b'<html></html>',
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
        response.raise_for_status.return_value = None
        get.return_value = response
        self.assertEqual(get_page(self.PAGE_URL), b'<html></html>')
        get.assert_called_once()

    @patch('what_if_parse.requests.get')
    def test_get_page_rejects_non_html(self, get):
        response = Mock(content=b'data', headers={'Content-Type': 'image/png'})
        response.raise_for_status.return_value = None
        get.return_value = response
        with self.assertRaises(GetPageError):
            get_page(self.PAGE_URL, raise_non_text_html=True)


if __name__ == '__main__':
    unittest.main()
