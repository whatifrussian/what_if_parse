#!/usr/bin/python3

""" Unit testing module for what-if parser. """


from what_if_parse import process_article
import unittest


class ParserTests(unittest.TestCase):
    """ Set of tests for HTML to markdown parsing. """
    PAGE_URL = 'TESTING'
    HTML_TMPL = '<html><body><article>%s</article></body></html>'

    def do_check_equal(self, article_html, article_md):
        """ Wrap HTML paragraps into the template, parse and equal check."""
        html = ParserTests.HTML_TMPL % article_html
        processed = process_article(ParserTests.PAGE_URL, html)[1]
        self.assertEqual(processed, article_md)

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
