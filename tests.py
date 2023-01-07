#!/usr/bin/env python3

""" Unit testing module for what-if parser. """


from what_if_parse import process_article
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
        md = process_article(ParserTests.PAGE_URL, html)[1]

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


if __name__ == '__main__':
    unittest.main()
