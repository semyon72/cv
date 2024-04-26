# IDE: PyCharm
# Project: cv
# Path: workroom/reportlab
# File: html2para.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-11-30 (y-m-d) 10:55 AM
import copy
import functools
import re
from typing import Optional, Union, Iterable, Any, NamedTuple, Type

import bs4
from reportlab.lib import styles
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.platypus import Flowable, Paragraph, flowables
import html.parser


class ParentedNode:

    def __init__(self, parent: Optional['ParentedNode'] = None) -> None:
        self._parent: Optional[ParentedNode] = None
        self.parent = parent
        self._children: list[ParentedNode] = []
        self._data: list[Any] = []

    def _add_child(self, other: 'ParentedNode'):
        assert isinstance(other, ParentedNode), f'`other` must be instance of ParentedNode (passed {other})'
        assert other is not self, f'`other` can not be self {other}'
        if other._parent:
            other._parent._remove_child(other)

        other._parent = self
        self._children.append(other)

    def _remove_child(self, other: 'ParentedNode'):
        assert isinstance(other, ParentedNode), f'`other` must be instance of ParentedNode (passed {other})'
        try:
            i = self._children.index(other)
        except ValueError:
            pass
        else:
            assert other._parent is self, f'Integrity was violated other.parent {other._parent} is not {self}'
            other._parent = None
            del self._children[i]

    def clear_descendants(self, keep_self=True):
        """
            clear all descendants recursively.
            It only clears the relationship.
        """
        stack = [self]
        while stack:
            if stack[-1]._children:
                stack.extend(stack[-1].children)
            else:
                last = stack.pop()
                if not keep_self or last is not self:
                    last.parent = None

    @property
    def children(self):
        return self._children

    @children.setter
    def children(self, node):
        """
            It will always clear the internal list of children

            if value is None children just will be cleared
            if value is Iterable then fill children

            If value is instance of ParentedNode, the child will be added.
            Looks like an ambiguous behavior. Not what is expected from the setter.
            But this allows to omit the public method that will duplicate ._add_child.
        """
        if node is None or isinstance(node, Iterable):
            for n in self._children:
                assert n._parent is self, f'Integrity was violated other.parent {n.parent} is not {self}'
                n._parent = None
            self._children.clear()

            if isinstance(node, Iterable):
                for n in node:
                    self._add_child(n)
        else:
            self._add_child(node)

    @property
    def parent(self) -> Optional['ParentedNode']:
        return self._parent

    @parent.setter
    def parent(self, node: 'ParentedNode'):
        """
            if Parent has children then it will process it appropriate, add and change relations.
        """
        if node:
            assert isinstance(node, ParentedNode), f'`node` must be instance of ParentedNode (passed {node})'
            assert node is not self, f'`node` can not be self {node}'

        if self._parent:
            self._parent._remove_child(self)

        if node:
            node._add_child(self)

    @property
    def next(self) -> Optional[list['ParentedNode']]:
        res = None
        if self._parent:
            children: list = self._parent.children
            try:
                i = children.index(self)
            except IndexError:
                pass
            else:
                if len(children)-1 > i:
                    res = children[i+1:]

        return res

    @property
    def previous(self) -> Optional[list['ParentedNode']]:
        res = None
        if self._parent:
            children: list = self._parent.children
            try:
                i = children.index(self)
            except IndexError:
                pass
            else:
                if len(children) - 1 > 0:
                    res = children[:i]

        return res

    @property
    def data(self) -> list[Any]:
        return self._data

    @data.setter
    def data(self, value: Any):
        self._data.clear()
        if not isinstance(value, Iterable) or isinstance(value, str):
            self._data.append(value)
        else:
            self._data.extend(value)


class TextNode(ParentedNode):

    def __str__(self) -> str:
        return ''.join(str(v) for v in self.data)


class TagNode(ParentedNode):

    def __init__(self, tag: str, attr: list[tuple[str, str]], parent: Optional['Tag'] = None) -> None:
        super().__init__(parent)
        self.tag = tag
        assert isinstance(attr, list)
        self.attr = attr
        self.closed = False

    def __str__(self):
        content = [str(tag) for tag in self.children]
        attrs = ''
        if self.attr:
            attrs = ' '+' '.join(f'{k}=\'{v}\'' for k, v in self.attr)
        return f'<{self.tag}{attrs}>{"".join(content)}{"</"+self.tag+">" if self.closed else ""}'

    def _test_attrs(self, **attrs):
        _attr = dict(self.attr)
        for k, v in attrs.items():
            tag_val = _attr.get(k, None)
            if tag_val is None or (isinstance(v, bool) and not v) or (not isinstance(v, bool) and tag_val != v):
                return False

        return True

    def find_all(self, tag_name, **attrs):
        res = []
        for child in self.children:
            if isinstance(child, TagNode):
                if child.tag.lower() == tag_name.lower() and child._test_attrs(**attrs):
                    res.append(child)
                res.extend(child.find_all(tag_name, **attrs))
        return res


class HTMLParser(html.parser.HTMLParser):

    def __init__(self, *, convert_charrefs=True):
        super().__init__(convert_charrefs=convert_charrefs)
        self.root = TagNode('root', [])
        self.current = self.root

    def get_tag_node(self, tag, attrs, current):
        return TagNode(tag, attrs, current)

    def handle_starttag(self, tag, attrs):
        self.current = self.get_tag_node(tag, attrs, self.current)

    def handle_endtag(self, tag):
        assert tag == self.current.tag, f'Try to close not last tag. last tag: `{self.current.tag}`, closing: `{tag}`'
        self.current.closed = True
        self.current = self.current.parent

    def get_text_node(self, current):
        return TextNode(current)

    def handle_data(self, data):
        data_tag = self.get_text_node(self.current)
        data_tag.data.append(data)
        self.current.children = data_tag


class ParaNode(TagNode):

    def __init__(self, tag: str, attr: list[tuple[str, str]], is_block: bool, parent: Optional['Tag'] = None) -> None:
        self.is_block = is_block
        super().__init__(tag, attr, parent)


class ParaBlock:

    def __init__(self, s: str, level: int = 0) -> None:
        self.s: str = s
        self.level: int = level
        self.node: Optional[ParaNode] = None

    def set_level(self, node: ParaNode):
        self.node = node
        # we need to skip the counting <root> node, <root> node has .parent is None
        start, lvl = node, 0
        while start.parent and start.parent.parent:
            if start.parent.is_block:
                lvl += 1
            start = start.parent
        self.level = lvl
        return self

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}("{self}", {self.level})'

    def __str__(self) -> str:
        return self.s


class HTML2ParaParser(HTMLParser):
    """
        It parses HTML content into a tree.

        The tree has one additional TagNode - 'root' which is never cloded.
        So, if it will converted into str then you will not have </root>
        The same rule applies to all unclosed <tag>-s

        Other nodes of Tree are either TextNone or ParaNode.
        ParaNode has one additional property .is_block wich is assigned during the parsing process.
        If the tag is recognized as a block (HTML2ParaParser.block_element contains tag),
        .is_block will be set to the appropriate boolean value.

        Method get_blocks() is a core that returns a `list[ParaBlock]` of parsed blocks (paragraphs) with nesting levels.
        ParaBlock, also has a .node that refers to the TagNode where the content was taken from.

        example:
            >>> content = 'Prefix <i>i</i> <li>li#1-outer <li>li-lvl#1-#1</li><li>li-lvl#1-#2</li></li> text between lvl#0 <li>li#2-outer</li> text <b>BBBBBBBBBBBB</b> after lvl#0'
            >>> parser = HTML2ParaParser()
            >>> parser.feed(content)
            >>> for block in parser.get_blocks():
            >>>     print(repr(block))
            ParaBlock("Prefix <i>i</i> ", 0)
            ParaBlock("li#1-outer ", 0)
            ParaBlock("li-lvl#1-#1", 1)
            ParaBlock("li-lvl#1-#2", 1)
            ParaBlock(" text between lvl#0 ", 0)
            ParaBlock("li#2-outer", 0)
            ParaBlock(" text <b>BBBBBBBBBBBB</b> after lvl#0", 0)
    """

    block_element = ('address', 'article', 'aside', 'blockquote', 'canvas', 'dd', 'div', 'dl', 'dt', 'fieldset',
                     'figcaption', 'figure', 'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'hr',
                     'li', 'main', 'nav', 'noscript', 'ol', 'p', 'pre', 'section', 'table', 'tfoot', 'ul', 'video',
                     'para')

    inline_element = ('a', 'abbr', 'acronym', 'b', 'bdo', 'big', 'br', 'button', 'cite', 'code', 'dfn', 'em', 'i',
                      'img', 'input', 'kbd', 'label', 'map', 'object', 'output', 'q', 'samp', 'script', 'select',
                      'small', 'span', 'strong', 'sub', 'sup', 'textarea', 'time', 'tt', 'var')

    def __init__(self, *, convert_charrefs=True):
        super().__init__(convert_charrefs=convert_charrefs)
        self._blocks = []

    def get_tag_node(self, tag, attrs, current):
        is_block = tag in self.block_element
        node = ParaNode(tag, attrs, is_block, current)
        return node

    def get_blocks(self, start: Optional[ParaNode] = None) -> list[ParaBlock]:
        if start is None:
            start = self.root
        res, cur_block = [], []
        for node in start.children:
            if isinstance(node, TextNode):
                cur_block.append(node)
            elif isinstance(node, ParaNode):
                if node.is_block:
                    if cur_block:
                        res.append(ParaBlock(''.join(str(n) for n in cur_block)).set_level(start))
                        cur_block.clear()

                    res.extend(self.get_blocks(node))
                else:
                    cur_block.append(node)

        if cur_block:
            res.append(ParaBlock(''.join(str(n) for n in cur_block)).set_level(start))

        return res


class Content2Paragraphs:

    default_indent = 18

    default_block_style: styles.ParagraphStyle = styles.ParagraphStyle(
        'ListItem', parent=styles.getSampleStyleSheet()['BodyText'],
        spaceBefore=0, spaceAfter=3, alignment=TA_JUSTIFY,
        # firstLineIndent=default_indent
    )

    def __init__(self, content, **kw_para) -> None:
        self._kw_para = kw_para
        self.content = content

    def get_paragraph(self, block: ParaBlock):
        kw = {
            'style': self.default_block_style,
        }
        if block.level > 0:
            style = copy.copy(self.default_block_style)
            style.leftIndent = self.default_indent * block.level
            kw['style'] = style
            kw['bulletText'] = flowables._bulletNames['squarelrs']

        kw.update(self._kw_para)
        block.s = TextLink2A()(block.s)
        return Paragraph(block.s, **kw)

    @functools.cached_property
    def paragraphs(self):
        parser = HTML2ParaParser()
        parser.feed(self.content)
        return [self.get_paragraph(block) for block in parser.get_blocks()]


class TextLink2A:

    http_url_pattern: re.Pattern = re.compile(
        r"(?P<url>https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}"
        r"\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*))"
    )

    a_format_string = "<a href=\"{url}\" color=\"blue\">{url}</a>"

    def __call__(self, content: str) -> str:
        """
            Implemented simple `url` string http[s]://domain.tld/request/string?query=string parsing and wrap it
            inside <a href=\"{url}\" color=\"blue\">{url}</a>
            It parses only first TextNode's children of block.

            The issue of a dot at the end of a `url` can be solved by replacing the dot
            with a comma, a space, any symbol that forbidden in an `url` or wrapping in an `a` tag.
        """
        parser = HTMLParser()
        parser.feed(content)
        repl_num = 0
        for n in parser.root.children:
            if isinstance(n, TextNode):
                repl_str, repl_num = self.http_url_pattern.subn(
                    lambda m: self.a_format_string.format(**m.groupdict()),
                    str(n)
                )
                if repl_num:
                    n.data = repl_str

        return ''.join(str(n) for n in parser.root.children) if repl_num > 0 else content


if __name__ == '__main__':
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

    # content = 'BEFORE <ol> OLLLLLLLLLL <i>IIIIIIIIIIIII</i> <li>LI11111 <ul>ULLLLLL <li>ULLII</li> ULLLLLL-TRAILER </ul></li> <li>LI2222222</li> OLLLL-TRAILER</ol>BETWEEN <b>BBBBBBBBBBBB</b> AFTER'
    # content = 'OLLLLLLLLLL <i>IIIIIIIIIIIII</i> <li>LI11111 <li>LI11-11111</li><li>LI11-222222</li></li> <li>LI222222</li> BETWEEN <b>BBBBBBBBBBBB</b> AFTER'
    # content = 'OLLLLLLLLLL AFTER'
    # content = ''
    content = 'Prefix <i>i</i> <li name="123">li#1-outer <li name="12345">li-lvl#1-#1</li><li>li-lvl#1-#2</li></li> text between lvl#0 <li>li#2-outer</li> text <b>BBBBBBBBBBBB</b> after lvl#0'

    parser = HTMLParser()
    parser.feed(content)
    print(str(parser.root)[6:])
    print(content)
    print(str(parser.root)[6:] == content)
    res = parser.root.find_all('li', name=True)

    parser.root.clear_descendants()

    parser = HTML2ParaParser()
    parser.feed(content)
    blocks = parser.get_blocks()
    parser.root.clear_descendants()
    for block in blocks:
        print(repr(block))
