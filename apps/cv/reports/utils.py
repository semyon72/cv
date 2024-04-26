# IDE: PyCharm
# Project: cv
# Path: apps/cv
# File: report_tools.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-11-23 (y-m-d) 9:20 PM
import copy
import functools
from typing import NamedTuple, Union, Optional, Callable, Iterable, Type

from bs4 import BeautifulSoup, Tag, NavigableString

from reportlab.lib import colors, styles, units
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfdoc import PDFDocument
from reportlab.pdfgen import canvas
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import MultiCol, Flowable, Paragraph, flowables


def calc_line_height(fontname: str, fontsize: int):
    # reportlab.pdfbase._fontdata.ascent_descent - declares the ascent, descent for predefined fonts
    # see https://stackoverflow.com/a/27631737 - what ascent, descent ... means
    # the descent always has the negative value, because the zero axis is the `baseline`.
    face = pdfmetrics.getFont(fontname).face
    return (face.ascent - face.descent) / 1000 * fontsize


def string_width(s: str, fontname: str, fontsize: int):
    # same method has Canvas.stringWidth(...) and pdfmetrics.stringWidth(...)
    face: pdfmetrics.Font = pdfmetrics.getFont(fontname)
    return face.stringWidth(s, fontsize)


class Point(NamedTuple):
    x: float
    y: float


TPaddingValue = Union[int, float]
TPaddings = tuple[TPaddingValue, TPaddingValue, TPaddingValue, TPaddingValue]


class DrawHook:
    def __init__(self, multi_column: 'PaddedMultiCol' = None) -> None:
        self.multi_column = multi_column

    @property
    def multi_column(self):
        assert self._multi_column is not None, '`multi_column` is not initialized yet'
        return self._multi_column

    @multi_column.setter
    def multi_column(self, value):
        assert value is None or isinstance(value, PaddedMultiCol), '`multi_column` is required and must be PaddedMultiCol instance'
        self._multi_column = value

    def __call__(self, canv: Canvas, bottom_left: Point, top_right: Point, column: int):
        raise NotImplementedError


TDrawHookClasses = Optional[Iterable[Type[DrawHook]]]
TDrawHooks = Optional[Iterable[Union[Type[DrawHook], DrawHook]]]


class PaddedMultiCol(MultiCol):

    draw_hook_classes: TDrawHookClasses = None

    def __init__(self, contents, widths, minHeightNeeded=36, spaceBefore=None, spaceAfter=None,
                 padding=None, splitted=False, slice_number=0, draw_hooks: TDrawHooks = None,
                 debug=False):
        self.debug = debug
        self.padding = self._expand_padding(padding)
        self.splitted = splitted
        self.slice_number = slice_number
        self._draw_hooks = draw_hooks or self.draw_hook_classes
        super().__init__(contents, widths, minHeightNeeded, spaceBefore, spaceAfter)

    @functools.cached_property
    def draw_hooks(self) -> list[DrawHook]:
        res = []
        for hook in self._draw_hooks or []:
            if type(hook) is type and issubclass(hook, DrawHook):
                res.append(hook(self))
            elif isinstance(hook, DrawHook):
                hook.multi_column = self
                res.append(hook)
            else:
                raise ValueError('`draw_hooks` should be either subclass or instance of DrawHook')
        return res

    def _expand_padding(self, padding: Optional[TPaddingValue]) -> TPaddings:
        # rules as CSS
        # /* Apply to all four sides */
        # padding: 1em;
        # /* top and bottom | left and right */
        # padding: 5% 10%;
        # /* top | left and right | bottom */
        # padding: 1em 2em 2em;
        # /* top | right | bottom | left */
        # padding: 5px 1em 0 2em;
        if padding:
            if isinstance(padding, (int, float)):
                return padding, padding, padding, padding
            elif isinstance(padding, (list, tuple)):
                lp = len(padding)
                if lp == 1:
                    return padding[0], padding[0], padding[0], padding[0]
                elif lp == 2:
                    return padding[0], padding[1], padding[0], padding[1]
                elif lp == 3:
                    return padding[0], padding[1], padding[2], padding[1]
                else:
                    return padding[0:4]
        return 0, 0, 0, 0

    def _calc_columns_geom(self, bottom_left: Point) -> list[tuple[Point, Point]]:
        res = []
        bottom_x, bottom_y = bottom_left
        for column_width in self._nW:
            top_x = bottom_x + column_width + sum(self.padding[1::2])
            top_y = bottom_y + self.height
            res.append((Point(bottom_x, bottom_y), Point(top_x, top_y)))
            bottom_x = top_x
        return res

    def _calc_border_geom(self, bottom_left: Point, column) -> tuple[Point, Point]:
        top_x = bottom_left.x + self._nW[column] + sum(self.padding[1::2])
        top_y = bottom_left.y + self.height
        return bottom_left, Point(top_x, top_y)

    def draw_hook(self, canv: Canvas, bottom_left: Point, top_right: Point, column: int):
        # Common meaning of self.slice_number
        # `self.slice_number` shows the sequence number of the slice, regardless of whether it was split or not
        # Common meaning of self.splitted
        # `self.splitted` indicates, whether it was split or not
        # Examples:
        # self.splitted == False & self.slice_number == 0 -> if not split at all
        # self.splitted == True & self.slice_number == 0 -> first part if the content have been split at least once
        # self.splitted == False & self.slice_number > 0 -> last part if the content have been split at least once

        if self.debug:
            canv.line(*bottom_left, *top_right)
            canv.line(*top_right, *top_right._replace(y=bottom_left.y))

        for draw_hook in self.draw_hooks:
            draw_hook(canv, bottom_left, top_right, column)

    def _draw_debug_info(self, canv: Canvas, x, y, _sW=0):
        canv.saveState()
        canv.setFillColor(colors.orange)
        canv.circle(x, y, 5, fill=1)
        canv.setFillColor(colors.red)
        canv.drawString(x + 7, y, f'x:{round(x, 2)}, y:{round(y, 2)}, _sW:{round(_sW, 2)}')
        canv.rect(x, y, self._frame._aW, self.height)
        canv.restoreState()

    def drawOn(self, canv: Canvas, x, y, _sW=0):

        def _get_x_offset(column=0):
            offset = self.padding[3]
            if column > 0:
                offset += self.padding[1]
            return offset

        if self.debug:
            self._draw_debug_info(canv, x, y, _sW)

        # implementation of border drawing
        for column, col_geom in enumerate(self._calc_columns_geom(Point(x, y))):
            self.draw_hook(canv, *col_geom, column)

        # copied from original and slightly modified
        widths = self._nW
        for column, (faW, F) in enumerate(zip(widths, self.contents)):
            x += _get_x_offset(column)
            super(MultiCol, type(self)).drawOn(self, canv, x, y-self.padding[0], content=F, aW=faW)
            x += faW

    def _calc_padding_space(self):
        col_num = len(self.widths)
        return sum(self.padding[1::2]) * col_num, sum(self.padding[0::2])

    def wrap(self, aW, aH):
        pad_width, pad_height = self._calc_padding_space()
        w, h = super().wrap(aW-pad_width, aH-pad_height)
        self.width += pad_width
        self.height += pad_height
        return w + pad_width, h + pad_height

    def split(self, aW, aH):
        pad_width, pad_height = self._calc_padding_space()
        res = []
        for i, f in enumerate(super().split(aW-pad_width, aH-pad_height)):
            splitted = bool(i==0)
            slice_number = self.slice_number
            if i > 0:
                slice_number = self.slice_number+1
            res.append(
                type(self)(f.contents, f.widths, minHeightNeeded=f.minHeightNeeded,
                           spaceBefore=f.getSpaceBefore(), spaceAfter=f.getSpaceAfter(),
                           padding=self.padding, splitted=splitted, slice_number=slice_number,
                           draw_hooks=self.draw_hooks, debug=self.debug)
            )
        return res


class ExampleDrawHook(DrawHook):

    def __call__(self, canv: Canvas, bottom_left: Point, top_right: Point, column: int):
        # Common meaning of self.slice_number
        # `self.slice_number` shows the sequence number of the slice, regardless of whether it was split or not
        # Common meaning of self.splitted
        # `self.splitted` indicates, whether it was split or not
        # Examples:
        # self.splitted == False & self.slice_number == 0 -> if not split at all
        # self.splitted == True & self.slice_number == 0 -> first part if the content have been split at least once
        # self.splitted == False & self.slice_number > 0 -> last part if the content have been split at least once

        canv.saveState()
        canv.setStrokeColor(colors.black)
        canv.setLineWidth(1)
        if column == 0:
            if self.multi_column.slice_number == 0:
                canv.line(*bottom_left._replace(y=top_right.y), *top_right)
            canv.line(*top_right, *top_right._replace(y=bottom_left.y))

        if column > 0:
            if not self.multi_column.splitted:
                canv.line(*bottom_left, *bottom_left._replace(x=top_right.x))
        canv.restoreState()


class VerticalInnerBorders(DrawHook):
    width: float = 1
    color: colors.Color = colors.black

    def __init__(self, multi_column: 'PaddedMultiCol' = None, **kwargs) -> None:
        super().__init__(multi_column)
        self.width = kwargs.pop('width', self.width)
        self.color = kwargs.pop('color', self.color)

    def __call__(self, canv: Canvas, bottom_left: Point, top_right: Point, column: int):
        canv.saveState()
        canv.setStrokeColor(self.color)
        canv.setLineWidth(self.width)
        if column < len(self.multi_column.widths)-1:
            canv.line(*top_right, *top_right._replace(y=bottom_left.y))
        canv.restoreState()


class OnSaveToPDFFlowable(flowables.NullDraw):

    def __init__(self, *args, callback: Callable, **kwargs):
        """
            callback is (self_this_flowable, doc, filename, canvas)
        """

        self._callback = callback
        # signature reportlab.pdfbase.pdfdoc.PDFDocument.SaveToFile(self, filename, canvas)
        self._doc_SaveToFile = None
        super().__init__(*args, **kwargs)

    def wrap(self, availWidth, availHeight):
        return 0, 0

    def _on_doc_SaveToFile(self, filename, canvas: Canvas):
        if isinstance(self._callback, Callable):
            self._callback(self, self._doc_SaveToFile.__self__, filename, canvas)
            self._doc_SaveToFile(filename, canvas)

        assert self._doc_SaveToFile.__self__ is canvas._doc
        del canvas._doc.__dict__['SaveToFile']
        assert canvas._doc.SaveToFile == self._doc_SaveToFile
        self._doc_SaveToFile = None

    def draw(self):
        super().draw()
        if isinstance(self._callback, Callable):
            self._doc_SaveToFile = self.canv._doc.SaveToFile
            self.canv._doc.__dict__['SaveToFile'] = self._on_doc_SaveToFile


class PageOfPagesFlowable(OnSaveToPDFFlowable):

    def __init__(self, *args, **kwargs):
        # signature reportlab.pdfbase.pdfdoc.PDFDocument.SaveToFile(self, filename, canvas)
        self._doc_SaveToFile = None
        super().__init__(*args, callback=self.do_before_save, **kwargs)

    @staticmethod
    def do_before_save(self, doc: PDFDocument, filename, canvas):
        canv = type(canvas)(None, pagesize=canvas._pagesize)
        pos = ((.5*units.cm, .5*units.cm), (canv._pagesize[0]-1.0*units.cm, 1.5*units.cm))
        pn = len(doc.Pages.pages)
        for pi, page in enumerate(doc.Pages.pages, 1):
            canv._code.clear()
            p = Paragraph(f'<para align="center">-- {pi} / {pn} --</para>')
            w, h = p.wrapOn(canv, *pos[1])
            assert w <= pos[1][0] and h <= pos[1][1], 'page of pages more than hardcoded dimension'
            p.drawOn(canv, *pos[0])
            page.stream = page.stream + '\n'.join(canv._code)+'\n'
