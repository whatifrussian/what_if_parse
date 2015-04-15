#!/usr/bin/python3


from what_if_parse import *
import unittest


class ParserTests(unittest.TestCase):
    url = 'TESTING'
    html_tmpl = '<html><body><article>%s</article></body></html>'

    def do_check(self, article_html, md):
        html = ParserTests.html_tmpl % article_html
        processed = process_article(ParserTests.url, html)[1]
        self.assertEqual(processed, md)

    def setUp(self):
        pass

    def test_italic_1(self):
        article_html = '<p><em>abc<em>012</em>def</em></p>'
        md = '*abc_012_def*'
        self.do_check(article_html, md)

    def test_bold_italic_1(self):
        article_html = '<p><em>abc<strong>012</strong>def</em></p>'
        md = '*abc**012**def*'
        self.do_check(article_html, md)


if __name__ == '__main__':
    unittest.main()
