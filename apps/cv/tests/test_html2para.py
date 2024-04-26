# IDE: PyCharm
# Project: cv
# Path: ${DIR_PATH}
# File: ${FILE_NAME}
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-11-30 (y-m-d) 10:34 PM

from unittest import TestCase

from ..reports.html2para import ParentedNode, HTMLParser, HTML2ParaParser


class TestParentedNode(TestCase):

    def test_empty_initialization(self):
        node = ParentedNode()
        self.assertIsNone(node.parent)
        self.assertEqual([], node.children)

    def test_simple_initialization(self):
        root = ParentedNode()
        child = ParentedNode(root)
        self.assertIsNone(root.parent)
        self.assertEqual([child], root.children)
        self.assertIs(root, child.parent)

    def test_parent_children(self):
        root = ParentedNode()
        child = ParentedNode()

        child.parent = root
        with self.subTest('child.parent = root'):
            self.assertIsNone(root.parent)
            self.assertEqual([child], root.children)
            self.assertIs(root, child.parent)

        root.children = None
        with self.subTest('root.children = None'):
            self.assertIsNone(child.parent)
            self.assertEqual([], root.children)

        root.children = child
        with self.subTest('root.children = child'):
            self.assertEqual([child], root.children)
            self.assertIs(root, child.parent)

    def test__add_child(self):
        root = ParentedNode()
        child = ParentedNode(root)

        child1 = ParentedNode()
        self.assertIsNone(child1.parent)
        child._add_child(child1)
        with self.subTest('child._add_child(child1)'):
            self.assertIsNotNone(child1.parent)
            self.assertIs(child, child1.parent)
            self.assertEqual([child1], child.children)

        root._add_child(child1)
        with self.subTest('root._add_child(child1)'):
            self.assertEqual([], child.children)
            self.assertIsNotNone(child1.parent)
            self.assertIs(root, child1.parent)
            self.assertEqual([child, child1], root.children)

        with self.subTest('root._add_child(None)'):
            with self.assertRaises(AssertionError):
                root._add_child(None)

        with self.subTest('root._add_child(1)'):
            with self.assertRaises(AssertionError):
                root._add_child(1)

        with self.subTest('root._add_child(root)'):
            with self.assertRaises(AssertionError):
                root._add_child(root)

    def test__remove_child(self):
        root = ParentedNode()
        child = ParentedNode(root)
        child1 = ParentedNode(child)

        self.assertIs(None, root.parent)
        self.assertIs(root, child.parent)
        self.assertIs(child, child1.parent)

        # nothing must happen
        root._remove_child(child1)
        self.assertIs(None, root.parent)
        self.assertIs(root, child.parent)
        self.assertIs(child, child1.parent)

        # nothing must happen
        root._remove_child(root)
        self.assertIs(None, root.parent)
        self.assertIs(root, child.parent)
        self.assertIs(child, child1.parent)

        child._remove_child(child1)
        with self.subTest('child._remove_child(child1)'):
            self.assertEqual([], child.children)
            self.assertIsNone(child1.parent)
            self.assertIs(root, child.parent)
            self.assertEqual([child], root.children)

        with self.subTest('root._remove_child'):
            with self.assertRaises(AssertionError):
                root._remove_child(None)

        with self.subTest('root._remove_child("fff")'):
            with self.assertRaises(AssertionError):
                root._remove_child("fff")

    def test_next_previous(self):
        root = ParentedNode()
        child = ParentedNode(root)
        child1 = ParentedNode(child)
        child2 = ParentedNode(child)
        child3 = ParentedNode(child)

        self.assertIs(None, root.parent)
        self.assertIs(root, child.parent)
        self.assertIs(child, child1.parent)
        self.assertIs(child, child2.parent)
        self.assertIs(child, child3.parent)

        self.assertEqual([child3], child2.next)
        self.assertEqual([child1], child2.previous)

        self.assertEqual([child2, child3], child1.next)
        self.assertEqual([], child1.previous)

    def test_data(self):
        root = ParentedNode()
        root.data = None
        self.assertEqual([None], root.data)

        root.data = [1, 2, 3]
        self.assertEqual([1, 2, 3], root.data)

        root.data.clear()
        self.assertEqual([], root.data)

    def test_clear_descendants(self):
        root = ParentedNode()
        child = ParentedNode(root)
        child1 = ParentedNode(child)
        child2 = ParentedNode(child)
        child3 = ParentedNode(child)

        child21 = ParentedNode(child2)
        child22 = ParentedNode(child2)

        child31 = ParentedNode(child3)

        # some partitial test
        self.assertEqual([child1, child2, child3], child.children)
        self.assertEqual([child21, child22], child2.children)
        self.assertEqual([child31], child3.children)

        child.clear_descendants()
        for i, node in enumerate((child1, child2, child3, child21, child22, child31)):
            with self.subTest(f'child.clear_descendants(keep_self=True) {i}'):
                self.assertIsNone(node.parent)
                self.assertEqual([], node.children)

        with self.subTest(f'child.parent == True'):
            self.assertIs(root, child.parent)
            self.assertEqual([], child.children)


class TestHTMLParser(TestCase):

    def test_integration_complex_content(self):
        content = "<p>During my first <b>attempt <a href='#fffdddffd'><i>at</i></a></b> deploying using Apache,</p>" \
                  "<p>During my first <b>attempt at</b> deploying using Apache,</p>" \
                  "<ul>OOOOOOOOLLLLLLLL <b>bbb<a href='ggggggggggg/hhhhhhhhhh/'>bbb</a></b> <i>iiiiiii</i>" \
                  "<para align='LEFT' bordercolor='#FF0055'>OOOOOOOOLLLLLLLL IN PARA <b>bbb<a href='fdgdfgdf/dfgdfg/'>bbb</a></b> <i>iiiiiii</i>" \
                  "<li>111111111111111" \
                  "<ol> SUB OL <b>BBBBBB SUB OL</b> NNNNNN" \
                  "<li>FIRST SUB LI</li>" \
                  "<li>SECOND SUB LI</li>" \
                  "</ol>" \
                  "</li>" \
                  "<li>22222222222222</li>" \
                  "<li>33333333333333</li>" \
                  "TRAILER Before end PARA <b>BBBBBBB Before end PARA</b>" \
                  "</para>" \
                  "</ul>" \
                  "I had to permanently switch from Windows to Linux. " \
                  "<a href=\'https://jjjjj.mmm/jjjjjj/jjjjj?hjhj=98798\'>kjhkjhkjhjkhkjhkhkhkjhjkhjk</a>" \
                  "It took some time to renew practical skills with Debian + KDE and learn the other" \
                  " necessary parts for deploying WSGI applications. As a result, I renewed my knowledge" \
                  " and gained additional knowledge and skills in WSGI, Debian, Apache, OpenSSL ...."

        parser = HTMLParser()
        parser.feed(content)
        self.assertEqual(str(parser.root)[6:], content)

    def test_integration_simple_content(self):
        content = 'BEFORE <ol> OLLLLLLLLLL <i>IIIIIIIIIIIII</i> <li>LI11111 <ul>ULLLLLL <li>ULLII</li> ULLLLLL-TRAILER </ul></li> <li>LI2222222</li> OLLLL-TRAILER</ol>BETWEEN <b>BBBBBBBBBBBB</b> AFTER'
        # content = 'Prefix <i>i</i> <li>li#1-outer <li>li-lvl#1-#1</li><li>li-lvl#1-#2</li></li> text between lvl#0 <li>li#2-outer</li> text <b>BBBBBBBBBBBB</b> after lvl#0'

        parser = HTMLParser()
        parser.feed(content)
        self.assertEqual(str(parser.root)[6:], content)

    def test_integration_plain_content(self):
        content = 'Plain text'
        parser = HTMLParser()
        parser.feed(content)
        self.assertEqual(str(parser.root)[6:], content)

    def test_integration_empty_content(self):
        content = ''
        parser = HTMLParser()
        parser.feed(content)
        self.assertEqual(str(parser.root)[6:], content)

    def test_find_all_of_TagNode(self):
        content = 'Prefix <i>i</i> <li name="123">li#1-outer <li name="12345">li-lvl#1-#1</li><li>li-lvl#1-#2</li></li> text between lvl#0 <li>li#2-outer</li> text <b>BBBBBBBBBBBB</b> after lvl#0'

        parser = HTMLParser()
        parser.feed(content)
        res = parser.root.find_all('')
        with self.subTest('empty tag name (a tag that does not exist)'):
            self.assertEqual([], res)

        expects = [
            '<li name=\'123\'>li#1-outer <li name=\'12345\'>li-lvl#1-#1</li><li>li-lvl#1-#2</li></li>',
            '<li name=\'12345\'>li-lvl#1-#1</li>',
            '<li>li-lvl#1-#2</li>',
            '<li>li#2-outer</li>',
        ]
        res = parser.root.find_all('li')
        with self.subTest('all `li`'):
            self.assertEqual(expects, [str(t) for t in res])

        res = parser.root.find_all('li', name=True)
        with self.subTest('all `li` with attribute "name"'):
            self.assertEqual(expects[:2], [str(t) for t in res])

        res = parser.root.find_all('li', name='12345')
        with self.subTest('all `li` with attribute "name"="12345"'):
            self.assertEqual(expects[1:2], [str(t) for t in res])


class TestHTML2ParaParser(TestCase):

    def test_integration_complex_content(self):
        content = "<p>During my first <b>attempt <a href='#fffdddffd'><i>at</i></a></b> deploying using Apache,</p>" \
                  "<p>During my first <b>attempt at</b> deploying using Apache,</p>" \
                  "<ul>OOOOOOOOLLLLLLLL <b>bbb<a href='ggggggggggg/hhhhhhhhhh/'>bbb</a></b> <i>iiiiiii</i>" \
                  "<para align='LEFT' bordercolor='#FF0055'>OOOOOOOOLLLLLLLL IN PARA <b>bbb<a href='fdgdfgdf/dfgdfg/'>bbb</a></b> <i>iiiiiii</i>" \
                  "<li>111111111111111" \
                  "<ol> SUB OL <b>BBBBBB SUB OL</b> NNNNNN" \
                  "<li>FIRST SUB LI</li>" \
                  "<li>SECOND SUB LI</li>" \
                  "</ol>" \
                  "</li>" \
                  "<li>22222222222222</li>" \
                  "<li>33333333333333</li>" \
                  "TRAILER Before end PARA <b>BBBBBBB Before end PARA</b>" \
                  "</para>" \
                  "</ul>" \
                  "I had to ... . <a href=\'https://jjj.mmm/jj/j?hjhj=98798\'>kjhkjhk</a>It took some time ...."

        expected = [
            "During my first <b>attempt <a href='#fffdddffd'><i>at</i></a></b> deploying using Apache,",
            "During my first <b>attempt at</b> deploying using Apache,",
            "OOOOOOOOLLLLLLLL <b>bbb<a href='ggggggggggg/hhhhhhhhhh/'>bbb</a></b> <i>iiiiiii</i>",
            "OOOOOOOOLLLLLLLL IN PARA <b>bbb<a href='fdgdfgdf/dfgdfg/'>bbb</a></b> <i>iiiiiii</i>",
            "111111111111111",
            " SUB OL <b>BBBBBB SUB OL</b> NNNNNN",
            "FIRST SUB LI",
            "SECOND SUB LI",
            "22222222222222",
            "33333333333333",
            "TRAILER Before end PARA <b>BBBBBBB Before end PARA</b>",
            "I had to ... . <a href=\'https://jjj.mmm/jj/j?hjhj=98798\'>kjhkjhk</a>It took some time ....",
        ]

        parser = HTML2ParaParser()
        parser.feed(content)
        self.assertEqual(str(parser.root)[6:], content)

        blocks = parser.get_blocks()
        parser.root.clear_descendants()
        for i, expect in enumerate(expected):
            with self.subTest(f'block #{i}'):
                self.assertEqual(expect, str(blocks[i]))

    def test_integration_simple_content(self):
        content = 'Prefix <i>i</i> <li>li#1-outer <li>li-lvl#1-#1</li><li>li-lvl#1-#2</li></li> text between lvl#0 <li>li#2-outer</li> text <b>BBBBBBBBBBBB</b> after lvl#0'

        parser = HTML2ParaParser()
        parser.feed(content)
        self.assertEqual(str(parser.root)[6:], content)

        expected = [
            'ParaBlock("Prefix <i>i</i> ", 0)',
            'ParaBlock("li#1-outer ", 0)',
            'ParaBlock("li-lvl#1-#1", 1)',
            'ParaBlock("li-lvl#1-#2", 1)',
            'ParaBlock(" text between lvl#0 ", 0)',
            'ParaBlock("li#2-outer", 0)',
            'ParaBlock(" text <b>BBBBBBBBBBBB</b> after lvl#0", 0)',
        ]

        blocks = parser.get_blocks()
        parser.root.clear_descendants()
        for i, expect in enumerate(expected):
            with self.subTest(f'block #{i}'):
                self.assertEqual(expect, repr(blocks[i]))