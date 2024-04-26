# IDE: PyCharm
# Project: cv
# Path: apps/cv
# File: report.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-10-29 (y-m-d) 3:18 PM
import copy
import datetime
import functools
import itertools
import math
import pathlib
import string
import tempfile

from dateutil.relativedelta import relativedelta
import PIL.Image as PILImage

from functools import cached_property
from typing import Union, Optional

from django.db.models import F, Case, When, Sum
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.slidebox import SlideBox
from reportlab.graphics.shapes import (
    String, AttrMap, AttrMapValue, isSeq, isStr, SequenceOf, isBoolean
)


from reportlab.lib import styles, colors, units
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Flowable, Table, TableStyle, NullDraw, Image,
    HRFlowable, KeepTogether
)
import reportlab.platypus.flowables as flowables

from django.db.models.fields import Field

from apps.cv import models
from ..reports.reportlab_fixes import Drawing, BalancedColumns
from . import utils
from .html2para import Content2Paragraphs, TextLink2A

import reportlab.rl_config as rl_config
rl_config.shapeChecking = False


"""
Best examples for chart's gallery with source code 
https://www.reportlab.com/chartgallery/
"""


class OutlineEntryFlowable(flowables.AnchorFlowable):
    def __init__(self, name, title, level=0, closed=False):
        super().__init__(name)
        self._title = title
        self._level = level
        self._closed = closed

    def draw(self):
        self.canv.addOutlineEntry(self._title, self._name, self._level, closed=self._closed)


class ShowOutlineFlowable(flowables.NullDraw):

    def wrap(self, availWidth, availHeight):
        return 0, 0

    def draw(self):
        super().draw()
        self.canv.showOutline()


class ResourceTable(Flowable):

    resource_name_style: styles.ParagraphStyle = styles.ParagraphStyle(name='ResourceNameColumn', alignment=TA_RIGHT)
    resource_link_style: styles.ParagraphStyle = styles.getSampleStyleSheet()['BodyText']

    def __init__(self, resources: dict, *, debug=False):
        self._resources = resources
        self._debug = debug

    def _check_href_link(self, link):
        # email regexp - (?:[A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@([A-Za-z0-9-]+(?:\.[A-Z|a-z]{2,})+)
        """
            TODO: Need to testis link broken to mark it
            if link is good it will return Title of page,
            otherwise the link with '<font color="red">BROKEN</font>' notice.
        """
        return link

    def _on_resource_link(self, resource: str, link: str):
        link = TextLink2A()(link)
        return Paragraph(link, self.resource_link_style)

    def _on_resource(self, resource: str):
        bullets = {
            'tel': u'\u260E',
            'email': u'\u2709',
        }
        return Paragraph(f"<b>{resource}:</b>", style=self.resource_name_style, bulletText=bullets.get(resource))

    def _get_resource_table_col_widths(self, aW: float, res_table: Table = None):
        col_widths = None
        # calculate col_widths
        if aW:
            # 'am'*5 - average for 10 chars. The other way is to calculate all the lengths of each real string
            # and divide by the number of characters to figure out the min width that should be used.
            rn_style = self.resource_name_style
            w10 = utils.string_width('am' * 5, rn_style.fontName, rn_style.fontSize)
            w1 = min(aW // 10 * 3, w10)
            col_widths = [w1, aW - w1]

        return col_widths

    @cached_property
    def resource_table(self) -> Table:
        """
            initialize resorce's table
        """
        tb_style_opt = [
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEBEFORE', (0, 0), (0, -1), 1, colors.darkorange),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.lightgrey, None])

        ]
        if self._debug:
            tb_style_opt.append(('GRID', (0, 0), (-1, -1), 0.25, colors.red))

        res_table = []
        for res, val in self._resources.items():
            res = res.strip(string.punctuation + string.whitespace)
            p_res = self._on_resource(res)
            p_val = self._on_resource_link(res, val)
            res_table.append([p_res, p_val])

        return Table(res_table, style=TableStyle(tb_style_opt)) if res_table else NullDraw()

    def drawOn(self, canvas, x, y, _sW=0):
        rt = self.resource_table
        rt.drawOn(canvas, x, y, _sW=0)

    def wrap(self, availWidth, availHeight):
        rt = self.resource_table
        rt._colWidths = rt._argW = self._get_resource_table_col_widths(availWidth, rt)
        return rt.wrap(availWidth, availHeight)


class Photo(Flowable):

    def __init__(self, image: Union[str, pathlib.Path]):
        self._image = image

    def _get_photo(self, aw=None) -> Image:
        if not hasattr(self, f'_{type(self).__name__}__photo'):
            lr_pad = 12
            aw = aw or self.canv._pagesize[0]
            if not self._image:
                self.__photo = Spacer(aw-lr_pad, 0.1)
            else:
                with PILImage.open(self._image) as im:
                    im: PILImage.Image = im
                    # 1/3 of aw if landscape and 1/4 of aw if portrait
                    # ratio = 3 if im.width > im.height else 4
                    ratio = 1
                    scale = (aw-lr_pad) / ratio / im.width
                    # *2 - will keep better resolution of original in pdf
                    scim: PILImage.Image = im.resize((int(im.width * scale * 2), int(im.height * scale * 2)))
                    with tempfile.NamedTemporaryFile() as file:
                        scim.save(file, format=im.format)
                        self.__photo = Image(file.name, width=int(scim.width / 2), height=int(scim.height / 2), kind='bound', lazy=0)
        return self.__photo

    def drawOn(self, canvas, x, y, _sW=0):
        photo = self._get_photo()
        photo.drawOn(canvas, x, y, _sW)

    def wrap(self, availWidth, availHeight):
        photo = self._get_photo(availWidth)
        return photo.wrap(availWidth, availHeight)


class PhotoResourceTable(Flowable):

    caption_text = 'communication resources'

    def __init__(self, image: Union[str, pathlib.Path], resources: dict, *, debug=False):
        self._photo = Photo(image)
        self._resource_table = ResourceTable(resources, debug=debug)
        self._debug = debug

    def _get_result_table(self) -> Table:
        if not hasattr(self, f'_{type(self).__name__}__result_table'):
            style = [
                    ('VALIGN', (0, 0), (0, 0), 'CENTER'),
                    ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                    ('VALIGN', (1, 0), (1, 0), 'TOP'),
                ]
            if self._debug:
                style.append(('GRID', (0, 0), (-1, -1), 0.25, colors.red))

            self.__result_table = Table(
                [[
                    self._photo,
                    [
                        Paragraph(f'{self.caption_text.capitalize()}:', style=styles.getSampleStyleSheet()['Heading3']),
                        self._resource_table
                    ]
                ]], style=style, colWidths=['33%', '67%']
            )
        return self.__result_table

    def drawOn(self, canvas: Canvas, x, y, _sW=0):
        outline_name = self.caption_text.lower().replace(' ', '_')
        canvas.addOutlineEntry(f'{self.caption_text.capitalize()}', outline_name)
        canvas.bookmarkHorizontalAbsolute(outline_name, y + self.height)
        rt = self._get_result_table()
        rt.drawOn(canvas, x, y, _sW)

    def wrap(self, availWidth, availHeight):
        rt = self._get_result_table()
        self.width, self.height = rt.wrap(availWidth, availHeight)
        return self.width, self.height


class LanguageFlowable(Flowable):
    """
        data are dictionary such as
        {'English': 'B2', 'Ukrainian': 'Native', Spanish': 'upper-intermediate'}
    """

    language_available_levels: list[tuple[str, str]] = [
        ('Z', 'Zero'), ('A1', 'Elementary'), ('A2', 'Pre-intermediate'),
        ('B1', 'Intermediate'), ('B2', 'Upper-Intermediate'), ('C1', 'Advanced'),
        ('C2', 'Proficiency'), ('N', 'Native')
    ]

    stylesheets = styles.getSampleStyleSheet()
    default_paragraph_style = stylesheets['BodyText']

    def __init__(self, data: Union[models.CVLanguage, dict], *,
                 width=0, hAlign='LEFT', vAlign='BOTTOM', _showBoundary=None, debug=True):
        # CVLanguage
        #     lang = models.CharField(max_length=24)
        #     level = models.CharField(max_length=24)
        #     notes = models.CharField(max_length=248)
        super().__init__()
        self.width = width
        self.hAlign = hAlign
        self.vAlign = vAlign
        self._showBoundary = _showBoundary
        self._debug = debug
        self.spaceAfter = 2
        self.data = data
        self.width = width

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        self._data, self._data_warning = self._process_raw_data(value)
        self.reset_table()

    def _process_raw_data(self, data: Union[dict, object]) -> tuple[dict[str, Union[str, Union[int, str]]], list[str]]:
        """
            data is a dictionary such as, one of:
                {'lang': 'English', 'level': 'B2', 'notes': 'some notes'},
                {'lang': 'Ukrainian', 'level': 'Native'},
                {'lang': 'Spanish', 'level': 'upper-intermediate', 'some another notes'},
            or object, each of which has attributes with identical names

            returns 2-tuple
            * [0] is {'lang': 'English', 'level': 4, 'notes': 'some notes'}
            * [1] is ['warning1', 'warning2', ... ]

            One difference is that level 'level': 4 is index in self.language_available_levels
        """
        accessor = dict.__getitem__ if isinstance(data, dict) else getattr
        res = {
            'lang': accessor(data, 'lang'),
            'level': accessor(data, 'level'),
            'notes': accessor(data, 'notes')
        }

        warnings = []
        avail_levels = [v.lower() for v in itertools.chain(*self.language_available_levels)]
        try:
            i = avail_levels.index(res['level'].lower())
        except ValueError:
            # to add an error message on pdf
            if not warnings:
                warnings.append(f'Available levels are: {avail_levels}')
            warnings.append(f'Unknown level \"{res["level"]}\"')
        else:
            res['level'] = i // 2

        return res, warnings

    def _get_slide(self) -> Drawing:
        sb = SlideBox()
        sb.startColor = colors.darkorange
        sb.endColor = colors.green
        sb.sourceLabelFontSize += 2
        sb.numberOfBoxes = len(self.language_available_levels)
        is_custom_level = not isinstance(self.data['level'], int)
        if is_custom_level:
            # add some information for custom_level
            sb.trianglePosition = 0
            sb.triangleFillColor = colors.red
            sb.sourceLabelFontName = "Helvetica-BoldOblique"
            sb.sourceLabelText = ': '.join(('Custom level', self.data['level']))
            sb.sourceLabelFillColor = colors.red
        else:
            sb.trianglePosition = self.data['level'] + 1
            sb.sourceLabelText = ': '.join(self.language_available_levels[self.data['level']])

        g = sb.draw()
        for n in g.getContents():
            if isinstance(n, String):
                try:
                    il = int(n.text) - 1
                except:
                    pass
                else:
                    n.text = self.language_available_levels[il][0]

        d = Drawing(*sb._getDrawingDimensions(), g)
        d.vAlign = 'TOP'
        return d

    @functools.cached_property
    def result_table(self) -> Table:
        slide = self._get_slide()
        data = [[Paragraph(self.data['lang'], style=self.default_paragraph_style), slide]]
        style = TableStyle(
            [
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                ('VALIGN', (0, 0), (0, 0), 'TOP'),
                ('ALIGN', (1, 0), (1, 0), 'CENTER'),
                ('VALIGN', (1, 0), (1, 0), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (0, 0), 10),
                # ('LINEBEFORE', (0, 0), (0, -1), .5, colors.darkorange),
                # ('LINEAFTER', (1, 0), (1, 0), .5, colors.darkorange),
                ('LINEAFTER', (-1, 0), (-1, -1), .5, colors.darkorange),
                ('LINEBELOW', (1, 0), (1, 0), .5, colors.darkorange),
                ('LINEBELOW', (0, -1), (-1, -1), .5, colors.darkorange),
            ]
        )
        if self._debug:
            style.add('GRID', (0, 0), (-1, -1), 1, colors.black)

        if self.data['notes']:
            p = Paragraph(
                f"<para bulletColor='orangered'>{self.data['notes']}</para>",
                style=styles.ParagraphStyle(
                    'LanguageNotes', parent=self.default_paragraph_style,
                    fontSize=self.default_paragraph_style.fontSize-1
                ),
                bulletText=flowables._bulletNames['rarrowhead'],  # squarelrs
            )
            data.append([p])
            style.add('SPAN', (0, 1), (-1, 1))


        tb = Table(data, ['30%', '70%'], style=style)
        return tb

    def reset_table(self):
        self.__dict__.pop('reset_table', None)

    def wrap(self, availWidth, availHeight):
        # 200 == .68 -> 294.12 for ['30%', '70%']
        w = self.width or availWidth
        result_table = self.result_table

        # simple scaling
        sbd = result_table._cellvalues[0][1]
        sbdw = sbd.width if isinstance(sbd, Drawing) else sbd[0].width
        mag_dif = sbdw / 294.12
        if w * mag_dif < sbdw:
            sbd.renderScale = w / sbdw * mag_dif

        width, height = result_table.wrapOn(self.canv, w, availHeight)
        return width, height

    def drawOn(self, canvas, x, y, _sW=0):
        return self.result_table.drawOn(canvas, x, y, _sW)

    def split(self, availWidth, availheight):
        return self.result_table.splitOn(self.canv, self.width or availWidth, availheight)


class PositionedParagraph(Drawing):

    _attrMap = AttrMap(
        BASE=Drawing,
        x=AttrMapValue(False, desc="drawing position x", initial=0),
        y=AttrMapValue(False, desc="drawing position y", initial=0),
        aW=AttrMapValue(False, desc="available width", initial=0),
        aH=AttrMapValue(False, desc='available height', initial=0),
        f=AttrMapValue(False, desc='Flowable'),
    )

    def __init__(self, f: Paragraph):
        self.x = 0
        self.y = 0
        self.aW = 0
        self.aH = 0
        self.f: Flowable = f
        self.canv = None
        self.width = 0
        self.height = 0
        self.contents = []

    def wrap(self, availWidth, availHeight):
        self.aW = availWidth
        self.aH = availHeight
        self.width, self.height = self.f.wrap(availWidth, availHeight)
        self.height += 12
        return self.width, self.height

    def draw(self, showBoundary=rl_config._unset_):
        self.f._showBoundary = showBoundary
        self.f.drawOn(self.canv, self.x, self.y+6)


ChartLegendColorsHex = (
        "#000000", "#FFFF00", "#1CE6FF", "#FF34FF", "#FF4A46", "#008941", "#006FA6", "#A30059",
        "#FFDBE5", "#7A4900", "#0000A6", "#63FFAC", "#B79762", "#004D43", "#8FB0FF", "#997D87",
        "#5A0007", "#809693", "#FEFFE6", "#1B4400", "#4FC601", "#3B5DFF", "#4A3B53", "#FF2F80",
        "#61615A", "#BA0900", "#6B7900", "#00C2A0", "#FFAA92", "#FF90C9", "#B903AA", "#D16100",
        "#DDEFFF", "#000035", "#7B4F4B", "#A1C299", "#300018", "#0AA6D8", "#013349", "#00846F",
        "#372101", "#FFB500", "#C2FFED", "#A079BF", "#CC0744", "#C0B9B2", "#C2FF99", "#001E09",
        "#00489C", "#6F0062", "#0CBD66", "#EEC3FF", "#456D75", "#B77B68", "#7A87A1", "#788D66",
        "#885578", "#FAD09F", "#FF8A9A", "#D157A0", "#BEC459", "#456648", "#0086ED", "#886F4C",

        "#34362D", "#B4A8BD", "#00A6AA", "#452C2C", "#636375", "#A3C8C9", "#FF913F", "#938A81",
        "#575329", "#00FECF", "#B05B6F", "#8CD0FF", "#3B9700", "#04F757", "#C8A1A1", "#1E6E00",
        "#7900D7", "#A77500", "#6367A9", "#A05837", "#6B002C", "#772600", "#D790FF", "#9B9700",
        "#549E79", "#FFF69F", "#201625", "#72418F", "#BC23FF", "#99ADC0", "#3A2465", "#922329",
        "#5B4534", "#FDE8DC", "#404E55", "#0089A3", "#CB7E98", "#A4E804", "#324E72", "#6A3A4C",
        "#83AB58", "#001C1E", "#D1F7CE", "#004B28", "#C8D0F6", "#A3A489", "#806C66", "#222800",
        "#BF5650", "#E83000", "#66796D", "#DA007C", "#FF1A59", "#8ADBB4", "#1E0200", "#5B4E51",
        "#C895C5", "#320033", "#FF6832", "#66E1D3", "#CFCDAC", "#D0AC94", "#7ED379", "#012C58"
)

ChartLegendColors: tuple[colors.Color] = tuple(colors.HexColor(_color) for _color in ChartLegendColorsHex)


class SkillFactPieChart(Drawing):
    """
        Chart Features
        --------------

        This Pie chart itself is a simple chart with exploded slices:
        - **self.pie.slices.popout = 5**
    """

    _attrMap = AttrMap(
        BASE=Drawing,
        data=AttrMapValue(isSeq, desc="List of values"),
        caption_text=AttrMapValue(isStr, desc="Caption string"),
        colors=AttrMapValue(SequenceOf(colors.Color), desc="list of Color"),
        auto_render_scale=AttrMapValue(isBoolean, desc="Auto-calculation renderScale", initial=True),
    )

    def __init__(self, width=200, height=200, *nodes, **keywords):
        self.data = keywords.pop('data', [])
        self.colors = keywords.pop('colors', ChartLegendColors[2: len(self.data)+2])
        self.caption_text = keywords.pop('caption_text', 'Pie chart')
        self.auto_render_scale = keywords.pop('auto_render_scale', True)
        super().__init__(width, height, *nodes, **keywords)

    def init_legend(self, aW, aH):
        legend_name = 'legend'
        d = getattr(self, legend_name, None)
        if d is None:
            def best_fit_by_width(l: Legend, aW):
                best_i = [0 for _ in range(6)]
                best_i[0] = l.columnMaximum

                ldata = len(self.data)
                for colnum in range(1, ldata+1):
                    l.columnMaximum = int(math.ceil(ldata / colnum))
                    mX, mY, mxX, mxY = l.getBounds()
                    w = mxX - mX
                    scale = aW / w
                    best_i = [l.columnMaximum, scale, mX, mY, mxX, mxY]  # [0] - columnMaximum, [1] - min_diff
                    if scale < 1.0:
                        break
                return best_i
            l = Legend()
            l.alignment = 'right'
            l.variColumn = True
            # If need to split into 12 chars (for example)
            # l.colorNamePairs = [(c, '\n'.join([lbl[i:i+12] for i in range(0, len(lbl), 12)])) for (lbl, days), c in zip(self.data, self.colors)]
            l.colorNamePairs = [(c, lbl) for (lbl, days), c in zip(self.data, self.colors)]

            best_colMax, scale, mX, mY, mxX, mxY = best_fit_by_width(l, aW)
            l.columnMaximum = best_colMax
            w, h = mxX - mX, mxY - mY + 12
            d = Drawing(w, h, l)

            scale = min(d.renderScale, scale)
            if scale != 1.0:
                d.width *= scale
                d.height *= scale

            d.scale(scale, scale)
            d.shift((0-mX)*scale, (0-mY+6)*scale)

            self.add(d, name=legend_name)
        return d

    def init_caption(self, aW, aH):
        cap = getattr(self, 'caption', None)
        if cap is None:
            cap = PositionedParagraph(Paragraph(f'<u><b>{self.caption_text}</b></u>'))
            self.add(cap, name='caption')
            cap.width, cap.height = cap.wrapOn(self.canv, aW, aH)
        return cap

    def init_chart(self, aW, aH):
        pc = getattr(self, 'chart', None)
        if pc is None:
            pc = Pie(checkLabelOverlap=True)
            pc.sideLabels = True
            pc.width = 100  # it can be commented out due to equality to the default value
            pc.height = 100  # it can be commented out due to equality to the default value
            pc.data, pc.labels = [], []
            max_i = 0
            for i, (l, d) in enumerate(self.data):
                if d.days > self.data[max_i][1].days:
                    max_i = i
                pc.data.append(d.days)
                # pc.labels.append(str(i+1))
                pc.slices[i].fillColor = self.colors[i]

            pc.slices.strokeWidth = 0.5
            pc.slices[max_i].popout = 10
            pc.slices[max_i].strokeWidth = 2
            pc.slices[max_i].strokeDashArray = [2, 2]
            pc.slices[max_i].labelRadius = 1.25
            pc.slices[max_i].fontColor = colors.red

            self.add(pc, name='chart')

        return pc

    def wrap(self, aW, aH):
        legend = self.init_legend(aW, aH)
        self.height = legend.height

        pc = self.init_chart(aW, aH)
        mX, mY, mxX, mxY = pc.getBounds()
        pc.x -= mX
        pc.y -= mY
        pc.y += self.height
        self.height += mxY - mY

        # different charts have different width (column width is constant)
        # => need to calc max_width and set appropriate scale
        if self.auto_render_scale:
            self.renderScale = min(self.renderScale, aW / self.width)

        cap = self.init_caption(aW / self.renderScale, aH / self.renderScale)
        cap.y = self.height
        self.height += cap.height

        w, h = super().wrap(aW, aH)

        if self.renderScale != 1.0:
            if self.auto_render_scale:
                # allowable deviation (issue of float rounding)
                deviation = aW - w
                if deviation <= 100 / 1e14:
                    self.width = aW
                    w = aW

        if w > aW:
            raise ValueError(f'calculated width {w} exceeds available width {aW}')

        if h > aH:
            raise ValueError(f'calculated height {h} exceeds available height {aH}')

        return w, h

    def draw(self, showBoundary=False):
        super().draw(showBoundary)
        self.canv.saveState()
        self.canv.scale(self.renderScale, self.renderScale)
        self.caption.canv = self.canv
        self.caption.draw(showBoundary)
        self.canv.restoreState()
        del self.caption.canv


class SkillFactsAttrMixin:
    technology_key_name = 'tech'
    technology_type_key_name = 'tech_type'
    technology_duration_key_name = 'sum_duration'

    section_body_style = styles.ParagraphStyle(
        'SectionBodyText', parent=styles.getSampleStyleSheet()['BodyText'],
        alignment=TA_LEFT,
        fontSize=styles.getSampleStyleSheet()['BodyText'].fontSize - 2,
    )

    date_style = styles.ParagraphStyle(
        'DateStyle', parent=section_body_style, alignment=TA_CENTER, textColor=colors.Color(0, 0, 0, 0.6),
    )


class SkillFactsTable(SkillFactsAttrMixin, Flowable):

    def __init__(self, profile: models.CVUserProfile):
        super().__init__()

        self.profile = profile
        self._data = [*self.get_queryset()]
        self._balanced_sumary_table = None

    def get_queryset(self):
        """
            Main SQL something like
                SELECT sum(
                    case when pt.duration is null then (strftime('%s') - strftime('%s', date(p.begin)))*1e6
                    else pt.duration end) as duration, t.technology, t.technology_type
                FROM cv_cvprojecttechnology pt,
                     cv_cvproject p,
                     cv_cvtechnologies t
                WHERE pt.technology_id = t.id
                  and pt.project_id = p.id
                group by t.technology
                order by duration desc
        """
        sum_duration = Sum(
            Case(
                When(duration__isnull=True, then=datetime.date.today() - F('project__begin')),
                default=F('duration')
            )
        )
        filtered_qs = models.CVProjectTechnology.objects.select_related('project', 'technology').filter(project__profile=self.profile)

        qs = filtered_qs.values(
            tech=F('technology__technology'),
            tech_type=F('technology__technology_type')
        ).annotate(sum_duration=sum_duration).order_by('-sum_duration')
        # qs will result in SQL (for SQLite )
        # SELECT "cv_cvtechnologies"."technology" AS "tech", "cv_cvtechnologies"."technology_type" AS "tech_type",
        #        SUM(CASE
        #            WHEN "cv_cvprojecttechnology"."duration" IS NULL
        #            THEN django_timestamp_diff(2023-12-05, "cv_cvproject"."begin")
        #            ELSE "cv_cvprojecttechnology"."duration"
        #            END) AS "sum_duration"
        # FROM "cv_cvprojecttechnology"
        #     INNER JOIN "cv_cvproject" ON ("cv_cvprojecttechnology"."project_id" = "cv_cvproject"."id")
        #     INNER JOIN "cv_cvtechnologies" ON ("cv_cvprojecttechnology"."technology_id" = "cv_cvtechnologies"."id")
        # WHERE "cv_cvproject"."profile_id" = 8
        # GROUP BY 1, 2
        # ORDER BY 3 DESC
        return qs

    def translate_to_table_data(self, item_index, item):

        tech_duration = item[self.technology_duration_key_name]
        tech_dates = [datetime.date.today() - tech_duration, datetime.date.today()]
        if tech_duration:
            if tech_duration.days < 1 and tech_duration.total_seconds() > 0.1:
                tech_duration = datetime.timedelta(1)
            tech_dates[1] = tech_dates[0] + tech_duration

        _, pdur = CompletePDFReport.date_dif_format(self, *tech_dates)

        return [
            Paragraph(str(item_index+1), style=self.section_body_style),
            Paragraph(str(item[self.technology_key_name]), style=self.section_body_style),
            Paragraph(
                str(models.CVTechnologies.TechnologyTypes(item[self.technology_type_key_name]).label),
                style=self.section_body_style
            ),
            Paragraph(f'<para align="right">{pdur}</para>', style=self.date_style),
        ]

    def get_balanced_summary_table(self) -> BalancedColumns:
        # [{'tech': 'SQL', 'tech_type': 'PROG_LANG', 'sum_duration': datetime.timedelta(days=9145)}, ...]
        if not self._balanced_sumary_table:
            header_bgcolor: colors.Color = colors.orange
            header_bgcolor.alpha = 0.4
            style = TableStyle([
                # ('GRID', (0, 0), (-1, -1), .5, colors.red),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), (None, colors.lightgrey)),
                ('HALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LINEBEFORE', (0, 0), (0, -1), .5, colors.orange),
                ('LINEAFTER', (-1, 0), (-1, -1), .5, colors.orange),
                # ('LINEBELOW', (0, -1), (-1, -1), .5, colors.orange),
                ('LINEBELOW', (0, 0), (-1, -1), .5, colors.orange),
                ('LINEABOVE', (0, 0), (-1, 0), .5, colors.orange),
                ('BACKGROUND', (0, 0), (-1, 0), header_bgcolor),
            ])

            header = [
                Paragraph(f'<b>{v}</b>', style=self.section_body_style) for v in ('#', 'Technology', 'Type', 'Duration')
            ]

            table = type('TTable', (Table, ), {'deepcopy': lambda slf: slf})(
                [header, *(self.translate_to_table_data(i, item) for i, item in enumerate(self._data))],
                style=style,
                colWidths=['10%', '33%', '33%', '24%'],
                repeatRows=1
            )

            self._balanced_sumary_table = BalancedColumns(table)

        return self._balanced_sumary_table

    def wrap(self, availWidth, availHeight):
        ST = self.get_balanced_summary_table()
        ST._frame = self._frame
        res = ST.wrapOn(self.canv, availWidth, availHeight)
        del ST._frame
        return res

    def drawOn(self, canvas, x, y, _sW=0):
        ST = self.get_balanced_summary_table()
        ST.drawOn(canvas, x, y, _sW)


class SkillFactsGroupedTable(SkillFactsAttrMixin, Flowable):

    def __init__(self, data):
        super().__init__()
        self.data = data
        self._balanced_grouped_tables = None
        self.bg_color_index = 2

    def _translate_duration(self, tech_duration: datetime.timedelta) -> str:
        tech_dates = [datetime.date.today() - tech_duration, datetime.date.today()]
        if tech_duration:
            if tech_duration.days < 1 and tech_duration.total_seconds() > 0.1:
                tech_duration = datetime.timedelta(1)
            tech_dates[1] = tech_dates[0] + tech_duration

        _, pdur = CompletePDFReport.date_dif_format(self, *tech_dates)
        return pdur

    def _get_table(self, tech_type, total_dur, items):
        tech_para = Paragraph(
            f'<b>{models.CVTechnologies.TechnologyTypes(tech_type).label}</b>',
            style=self.section_body_style
        )
        data = [[tech_para, '', '', '']]
        for i, (tech, dur) in enumerate(items, 1):
            data.append([
                Paragraph(f'{i}', style=self.section_body_style),
                Paragraph(f'{tech}', style=self.section_body_style),
                Paragraph(f'{self._translate_duration(dur)}', style=self.date_style),
                Paragraph(f'{round(dur.days / total_dur.days * 100, 2)}%', style=self.section_body_style)
            ])

        bg_color: colors.Color = copy.copy(ChartLegendColors[self.bg_color_index])
        bg_color.alpha = .15
        tbl_style = TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), bg_color),
                ('SPAN', (0, 0), (-1, 0)),
                ('GRID', (0, 0), (-1, -1), .5, colors.orange),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]
        )
        self.bg_color_index += 1
        table = type('TTable', (Table, ), {'deepcopy': lambda slf: slf})(
            data,
            style=tbl_style, colWidths=['10%', '45%', '25%', '20%'],
            spaceAfter=12
        )

        return table

    def get_balanced_grouped_tables(self) -> BalancedColumns:
        if not self._balanced_grouped_tables:
            res = []

            grouped = {}
            for item in self.data:
                dur = item[self.technology_duration_key_name]
                techs = grouped.setdefault(item[self.technology_type_key_name], [datetime.timedelta(0), []])
                techs[0] += dur
                techs[1].append([item[self.technology_key_name], dur])

            for tech_type, (total_dur, items) in grouped.items():
                table = self._get_table(tech_type, total_dur, items)
                res.append(table)

            self._balanced_grouped_tables = BalancedColumns(res, nCols=2)

        return self._balanced_grouped_tables

    def wrap(self, availWidth, availHeight):
        ST = self.get_balanced_grouped_tables()
        ST._frame = self._frame
        res = ST.wrapOn(self.canv, availWidth, availHeight)
        del ST._frame
        return res

    def drawOn(self, canvas, x, y, _sW=0):
        ST = self.get_balanced_grouped_tables()
        ST.drawOn(canvas, x, y, _sW)


class CompletePDFReport:

    def __init__(self, profile: models.CVUserProfile, filename, debug=False) -> None:
        self.page_size = rl_config.defaultPageSize
        self.file = filename
        self.profile = profile
        self._debug = debug

        self.section_heading_style = styles.ParagraphStyle(
            'SectionHeadingStyle',
            parent=styles.getSampleStyleSheet()['Heading3'],
            keepWithNext=True,
        )
        self.sub_section_heading_style = styles.getSampleStyleSheet()['Heading4']

        self.section_body_style = styles.ParagraphStyle(
            'SectionBodyText', parent=styles.getSampleStyleSheet()['BodyText'],
            alignment=TA_JUSTIFY
        )
        self.indentation = utils.string_width(' ' * 8, self.section_body_style.fontName, self.section_body_style.fontSize)

        self.date_style = styles.ParagraphStyle(
            'DateStyle', parent=self.section_body_style,
            fontSize=self.section_body_style.fontSize-1,
            firstLineIndent=0, alignment=TA_CENTER,
            textColor=colors.Color(0, 0, 0, 0.6),
        )

        self.list_item_style = styles.ParagraphStyle(
            'ListItem', parent=self.section_body_style,
            firstLineIndent=0, leftIndent=self.indentation,
            spaceBefore=0, spaceAfter=1,
        )

    def get_resources(self) -> dict:
        qs = self.profile.cvuserresource_set.select_related('resource').all()
        return {r.resource.resource: r.link for r in qs}

    def get_soft_skills(self) -> list[Flowable]:

        caption_text = 'Soft skills'
        caption_outline_name = caption_text.lower().replace(' ', '_')

        return [
            flowables.AnchorFlowable(caption_outline_name),
            OutlineEntryFlowable(caption_outline_name, caption_text, 0),
            Paragraph(caption_text, style=self.section_heading_style),
            *Content2Paragraphs(self.profile.soft_skill, style=self.list_item_style, bulletText=flowables._bulletNames['rarrowhead']).paragraphs
        ]

    def get_summary_qualification(self) -> list[Flowable]:
        fld: Field = self.profile._meta.get_field('summary_qualification')
        body_style = styles.ParagraphStyle(
            'IndentedBodyStyle', parent=self.section_body_style, firstLineIndent=self.indentation
        )

        caption_text = fld.verbose_name.capitalize()
        caption_outline_name = caption_text.lower().replace(' ', '_')

        return [
            flowables.AnchorFlowable(caption_outline_name),
            OutlineEntryFlowable(caption_outline_name, caption_text, 0),
            Paragraph(caption_text, style=self.section_heading_style),
            Paragraph(f'{self.profile.summary_qualification}', style=body_style)
        ]

    def get_position(self) -> list[Flowable]:
        full_name = self.profile.user.get_full_name()
        return [
            Paragraph(
                f"{full_name}, {self.profile.position}",
                style=styles.ParagraphStyle(
                    'PositionHeading', parent=self.section_heading_style,
                    alignment=TA_CENTER,
                )
            ),
        ]

    def put_into_table(self,
                       col0_content, col1_content,
                       col0_width='60%', col1_width='40%',
                       *, debug=False, **kw) -> list[Flowable]:
        style = TableStyle(
            [
                ('LINEAFTER', (0, 0), (0, -1), .5, colors.darkorange),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
            ]
        )
        if debug:
            style.add('GRID', (0, 0), (-1, -1), 1, colors.black)

        for k in ('data', 'colWidths', 'style', 'debug'):
            kw.pop(k, None)

        tb = Table([[col0_content, col1_content]], [col0_width, col1_width], style=style, **kw)
        return [tb]

    def get_cover_letter(self) -> list[Flowable]:
        # TODO: draw on the last page
        res = []
        self.profile.cover_letter
        return res

    def date_dif_format(self, b: datetime.date, e: Optional[datetime.date]=None):
        date_fmt = "%b %Y"
        on_date_fmt = "%b %Y"
        estr, on_estr = 'Now', ''
        if e is None:
            e = datetime.date.today()
            on_estr = f' as of {e:{on_date_fmt}}'
        else:
            estr = f'{e:{date_fmt}}'
        rdif = relativedelta(e, b)

        dur = '/'.join([str(v)+k for k, v in {'y': rdif.years, 'm': rdif.months, 'd': rdif.days}.items() if v])+on_estr
        return f'{b:{date_fmt}}-{estr}', dur

    def get_employment_history(self, *, debug=False) -> list[Flowable]:
        # WORKPLACE
        # workplace = models.CharField(max_length=248)
        # begin = models.DateField(default=datetime.date.today)
        # end = models.DateField(null=True, default=None, blank=True)
        # WORKPLACE RESPONSIBILITY
        # role = models.CharField(max_length=48)
        # responsibility = models.TextField(max_length=1024)
        # begin = models.DateField(default=datetime.date.today)
        # end = models.DateField(null=True, default=None, blank=True)

        def get_responsibility_table(wpr: models.CVWorkplaceResponsibility, debug=False) -> Table:
            style = TableStyle(
                [
                    ('SPAN', (0, 0), (-1, 0)),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('ALIGN', (1, 1), (1, -1), 'CENTER'),
                    ('LINEBEFORE', (1, 1), (1, -1), 0.5, colors.darkorange),
                    ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.darkorange),

                ]
            )
            if debug:
                style.add('GRID', (0, 0), (-1, -1), 1, colors.red)

            drange, dur = self.date_dif_format(wpr.begin, wpr.end)
            data = [
                [Paragraph(wpr.role, style=self.sub_section_heading_style), ''],
                [Content2Paragraphs(wpr.responsibility, style=self.list_item_style).paragraphs, [
                    Paragraph(f'{drange}', style=self.date_style),
                    Paragraph(f'{dur}', style=self.date_style)
                ]]
            ]
            tb = Table(data, colWidths=['80%', '20%'], style=style, spaceAfter=2)
            return tb

        def get_workplace_table(wp: models.CVWorkplace, debug=False) -> list[Flowable]:
            prange, pdur = self.date_dif_format(wp.begin, wp.end)
            wprs = []
            for wpr in wp.cvworkplaceresponsibility_set.order_by('-begin').all():
                wprs.append(get_responsibility_table(wpr, debug=debug))

            workplace_text = wp.workplace
            workplace_outline_name = f"{caption_outline_name}#{workplace_text.lower().replace(' ', '_')}"

            data = [
                [
                    [Paragraph(prange, style=self.date_style), Paragraph(pdur, style=self.date_style)],
                    Paragraph(workplace_text, style=self.sub_section_heading_style)
                ],
                ['', wprs if wprs else Paragraph('<para align="center" backColor="darkorange">No responsibilities :(</para>')]
            ]
            style = TableStyle([
                ('SPAN', (0, 0), (0, -1)),
                ('VALIGN', (0, 0), (0, -1), 'TOP'),
                ('LINEBEFORE', (1, 0), (1, -1), .5, colors.darkorange),
                ('LINEBELOW', (1, 0), (1, 0), .5, colors.darkorange),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ])
            if debug:
                style.add('GRID', (0, 0), (-1, -1), 1, colors.darkorange)

            tb = Table(data, colWidths=['20%', '80%'], style=style, spaceBefore=2)
            return [flowables.AnchorFlowable(workplace_outline_name),
                    OutlineEntryFlowable(workplace_outline_name, workplace_text, 1),
                    tb]

        qs_work_places = models.CVWorkplace.objects.filter(profile=self.profile).prefetch_related('cvworkplaceresponsibility_set').\
            order_by('-begin').all()

        caption_text = 'Employment history'
        caption_outline_name = caption_text.lower().replace(' ', '_')

        res = [
            Paragraph(caption_text, style=self.section_heading_style),
        ]
        for i, wp in enumerate(qs_work_places):
            twp = get_workplace_table(wp, debug)
            if i == 0 and not res[0].style.keepWithNext:
                res[0] = KeepTogether([res[0], *twp])
            else:
                res.extend(twp)

        res[0:0] = [
            flowables.AnchorFlowable(caption_outline_name),
            OutlineEntryFlowable(caption_outline_name, caption_text, 0),
        ]

        return res

    def get_education(self, debug=False) -> list[Flowable]:
        # CVEducation
        #     begin = models.DateField(default=datetime.date.today)
        #     end = models.DateField(null=True, default=None, blank=True)
        #     institution = models.CharField(max_length=248)
        #     speciality = models.CharField(max_length=248)
        #     degree = models.CharField(max_length=24)
        #     complete = models.BooleanField(default=True)

        def get_education_table(ed: models.CVEducation, debug=False):

            def get_status(end: datetime.date, complete: int):
                # TODO: see how it fix
                # states = [
                #     ('refused', u'\u2BBF', 'red'), ('done', u'\u2611', 'green'),
                #     ('in progress', u'\u25F7', 'yellowgreen'),
                #     ('status is "done" but "end" still Now', u'\u26A0', 'orangered')
                # ]
                states = [
                    ('refused', '[-]', 'red'), ('done', '[+]', 'green'),
                    ('in progress', '[...]', 'darkorange'),
                    ('status is "done" but "end" still Now', '[!]', 'orangered')
                ]

                status = states[ed.complete]
                if ed.end is None:
                    if bool(ed.complete):
                        # probably error
                        status = states[3]
                    else:
                        status = states[2]
                elif datetime.date.today() < ed.end:
                    status = states[2]

                return [
                    Paragraph(f'<para color="{status[2]}" align="center">{status[1]}</para>'),
                    Paragraph(f'<para color="{status[2]}" align="center">{status[0]}</para>')
                ]

            def wrap_in_table(ed: models.CVEducation, debug):
                style = TableStyle([
                    ('SPAN', (1, 0), (1, -1)),
                    ('LINEBEFORE', (1, 0), (1, -1), 0.5, colors.darkorange),
                    ('VALIGN', (1, 0), (1, -1), 'CENTER'),
                    ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                    ('LINEBELOW', (0, 0), (0, 0), 0.5, colors.darkorange),
                    ('LINEBELOW', (1, -1), (1, -1), 0.5, colors.darkorange)
                ])
                if debug:
                    style.add('GRID', (0, 0), (-1, -1), 1, colors.red)

                data = [
                    [Paragraph(ed.institution, style=self.sub_section_heading_style), get_status(ed.end, ed.complete)],
                    [Paragraph(f'{ed.degree} of {ed.speciality}', style=self.section_body_style), '']
                ]

                return Table(data, style=style, colWidths=('80%', '20%'))

            style = TableStyle([
                ('LINEBEFORE', (1, 0), (1, -1), 0.5, colors.darkorange),
                ('LINEABOVE', (0, 0), (0, 0), 0.5, colors.darkorange),
                ('VALIGN', (0, 0), (-1, 0), 'TOP'),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ])
            if debug:
                style.add('GRID', (0, 0), (-1, -1), 1, colors.red)

            prange, pdur = self.date_dif_format(ed.begin, ed.end)
            tb = Table(
                [
                    [
                        [Paragraph(prange, style=self.date_style), Paragraph(pdur, style=self.date_style)],
                        wrap_in_table(ed, debug=debug)
                    ],
                ],
                colWidths=['20%', '80%'],
                style=style,
                spaceBefore=2
            )

            return tb

        eds = models.CVEducation.objects.filter(profile=self.profile).all()

        caption_text = 'Education'
        caption_outline_name = caption_text.lower().replace(' ', '_')

        res = [Paragraph(caption_text, style=self.section_heading_style)]
        for i, ed in enumerate(eds):
            ted = get_education_table(ed, debug=debug)
            if i == 0 and not res[0].style.keepWithNext:
                res[0] = KeepTogether([res[0], ted])
            else:
                res.append(ted)

        res[0:0] = [
            flowables.AnchorFlowable(caption_outline_name),
            OutlineEntryFlowable(caption_outline_name, caption_text, 0),
        ]

        return res

    def get_language(self, debug=False) -> list[Flowable]:
        caption_text = 'Languages'
        caption_outline_name = caption_text.lower().replace(' ', '_')

        res = [
            flowables.AnchorFlowable(caption_outline_name),
            OutlineEntryFlowable(caption_outline_name, caption_text, 0),
            Paragraph(caption_text, style=self.section_heading_style)
        ]
        for lang in self.profile.cvlanguage_set.all():
            res.append(LanguageFlowable(lang, width=0, debug=debug))

        return res

    def get_hobby(self) -> list[Flowable]:
        caption_text = 'Hobby'
        caption_outline_name = caption_text.lower().replace(' ', '_')
        res = [
            flowables.AnchorFlowable(caption_outline_name),
            OutlineEntryFlowable(caption_outline_name, caption_text, 0),
            Paragraph(caption_text, style=self.section_heading_style),
            *[
                Paragraph(hobby.description, style=self.list_item_style, bulletText=flowables._bulletNames['rarrowhead'])
                for hobby in self.profile.cvhobby_set.all()
            ]
        ]
        return res

    def get_project(self, debug=False) -> list[Flowable]:
        # CVProject
        #     title = models.CharField(max_length=248)
        #     prerequisite = models.CharField(max_length=248, blank=True)
        #     description = models.TextField(max_length=8*1024)
        #     result = models.CharField(max_length=248, blank=True)
        #     begin = models.DateField(default=datetime.date.today)
        #     end = models.DateField(null=True, default=None, blank=True)
        # CVProjectTechnology
        #     project = models.ForeignKey(CVProject, on_delete=models.CASCADE)
        #     technology = models.ForeignKey(CVTechnologies, on_delete=models.CASCADE)
        #     duration = models.DurationField(null=True, blank=True)
        #     notes = models.CharField(max_length=248, null=True, blank=True, default=None)
        # CVTechnologies
        #     technology = models.CharField(max_length=48)
        #     technology_type = models.CharField(
        #         max_length=10, choices=TechnologyTypes.choices, default=TECHNOLOGY_TYPES_DEFAULT_CHOICE
        #     )
        #     profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE, null=True, default=None, blank=True)
        #
        # >>> CVTechnologies.TechnologyTypes.PROGRAMMING_LANGUAGE.label
        # 'Programming language'
        ...

        # instead of
        # SELECT p.*, pt.*
        # FROM cv_cvproject p LEFT OUTER JOIN (SELECT pt.*, t.*
        # FROM cv_cvprojecttechnology pt INNER JOIN cv_cvtechnologies t on pt.technology_id = t.id
        # ) pt ON p.id = pt.project_id
        # WHERE p.profile_id = 8
        # ORDER BY p.id asc, pt.duration desc, pt.technology_type
        # better to split it on two steps
        # 1. projs = self.profile.cvproject_set.order_by('-begin').all()
        # 2. for each project
        #    proj.cvprojecttechnology_set.select_related('technology').order_by('-duration', 'technology__technology_type').all()

        def get_technologies(
                technologies: list[Union[dict, models.CVProjectTechnology]],
                technology_dates: tuple[datetime.date, datetime.date]
        ) -> list[Flowable]:

            if not technologies:
                return []

            style = TableStyle([
                ('ROWBACKGROUNDS', (1, 0), (-1, -1), [colors.lightgrey, None]),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LINEBEFORE', (1, 0), (1, -1), .5, colors.orange),
                ('LINEBELOW', (0, -1), (-1, -1), .5, colors.orange)
            ])
            if debug:
                style.add('GRID', (0, 0), (-1, -1), 1, colors.red)

            data, tech_type_prev = [], ''
            for i, proj_tech in enumerate(proj_techs):
                accessor = dict.__getitem__ if isinstance(proj_tech, dict) else getattr
                tech = accessor(accessor(proj_tech, 'technology'), 'technology')
                tech_type = accessor(accessor(proj_tech, 'technology'), 'technology_type')
                tech_type_label = models.CVTechnologies.TechnologyTypes(tech_type).label
                if tech_type_prev != tech_type:
                    style.add('LINEABOVE', (0, i), (-1, i), .5, colors.orange)
                else:
                    tech_type_label = ''

                tech_notes = accessor(proj_tech, 'notes')
                tech_notes = f' ({tech_notes})' if tech_notes else ''

                tech_duration = accessor(proj_tech, 'duration')
                tech_dates = [*technology_dates]
                if tech_duration:
                    if tech_duration.days < 1 and tech_duration.total_seconds() > 0.1:
                        tech_duration = datetime.timedelta(1)
                    tech_dates[1] = tech_dates[0] + tech_duration

                _, pdur = self.date_dif_format(*tech_dates)

                pstyle = styles.ParagraphStyle('TechnologiesParagraphStyle', parent=self.section_body_style,
                                               fontSize=self.section_body_style.fontSize-1.5,
                                               firstLineIndent=0, alignment=TA_LEFT)
                dstyle = styles.ParagraphStyle('TechnologiesDateStyle', parent=self.date_style,
                                      fontSize=self.section_body_style.fontSize - 1.5)

                data.append([
                    Paragraph(tech_type_label, style=pstyle),
                    Paragraph(f'{tech}{tech_notes}', style=pstyle),
                    Paragraph(pdur, style=dstyle)
                ])
                tech_type_prev = tech_type

            table = Table(data, colWidths=['25%', '50%', '25%'], style=style)

            return [table]

        def get_project(
                project: Union[dict, models.CVProject],
                technologies: list[Union[dict, models.CVProjectTechnology]]
        ):

            def parse_content(content) -> list[Paragraph]:
                return Content2Paragraphs(content).paragraphs

            if not project:
                return []

            accessor = dict.__getitem__ if isinstance(project, dict) else getattr
            project_begin, project_end = accessor(project, 'begin'), accessor(project, 'end')

            style = copy.copy(self.section_body_style)
            style.spaceBefore = 0
            style.spaceAfter = 2

            proj_parts = []
            for proj_attr, proj_attr_caption in {
                'prerequisite': 'prerequisites', 'description': 'description', 'result': 'results'
            }.items():
                proj_part = accessor(project, proj_attr)

                if proj_part:
                    proj_parts.append(Paragraph(f'<u color="orange" width=".5"><i>{proj_attr_caption.capitalize()}:</i></u>', style=style))
                    proj_parts.extend(parse_content(proj_part))

            tech_res = get_technologies(technologies, (project_begin, project_end))
            if tech_res:
                tech_res.insert(0, Paragraph('<para spaceBefore="9"><i>Used technologies:</i></para>', style=style))

            project_text = accessor(project, 'title')
            project_outline_name = f"{caption_text}#{project_text.lower().replace(' ', '_')}"

            data = [
                [Paragraph(p, style=self.date_style) for p in self.date_dif_format(project_begin, project_end) if p],
                [
                    flowables.AnchorFlowable(project_outline_name),
                    OutlineEntryFlowable(project_outline_name, project_text, 1),
                    Paragraph(project_text, style=self.sub_section_heading_style),
                    HRFlowable(width='100%', thickness=.5, color=colors.orange, spaceAfter=3),
                    *proj_parts,
                    *tech_res
                ]
            ]
            multi_column = utils.PaddedMultiCol(
                data, widths=['17%', '83%'],
                padding=[3, 6], draw_hooks=[utils.VerticalInnerBorders(width=.5, color=colors.orange)],
                debug=debug
            )

            return [multi_column]

        debug = False

        res = []

        caption_text = 'Projects'
        caption_outline_name = caption_text.lower().replace(' ', '_')

        projs = self.profile.cvproject_set.order_by('-begin').all()
        for proj in projs:
            proj_techs = proj.cvprojecttechnology_set.select_related('technology').order_by(F('duration').desc(), 'technology__technology_type').all()
            res.append(*get_project(proj, proj_techs))

        if res:
            res[0:0] = [
                flowables.AnchorFlowable(caption_outline_name),
                OutlineEntryFlowable(caption_outline_name, caption_text, 0),
                Paragraph(caption_text, style=self.section_heading_style)
            ]

        return res

    def get_skill_facts(self):
        table = SkillFactsTable(self.profile)
        grouped_table = SkillFactsGroupedTable(table._data)

        HR = HRFlowable(color=colors.orange, spaceBefore=3, spaceAfter=3)
        grouped_test_data = {}
        for data in table._data:
            grouped_test_data.setdefault(data['tech_type'], []).append([data['tech'], data['sum_duration']])

        _res_data = []
        for tech_type, tech_data in grouped_test_data.items():
            _res_data.append(SkillFactPieChart(data=tech_data, caption_text=models.CVTechnologies.TechnologyTypes(tech_type).label))

        pie_charts = BalancedColumns(
                functools.reduce(lambda x, y: x + [y, HR], (d for d in _res_data), []),
                nCols=3,
                vLinesStrokeWidth=1,
                vLinesStrokeColor=colors.orange,
                leftPadding=12
            )

        captions = ['Skill facts', 'Summary table', 'Tables grouped by type of technology', 'Charts']
        cap_outline_name0 = captions[0].lower().replace(' ', '_')
        out_line_flowables = []
        for i, cap_text in enumerate(captions):
            cap_outline_name = cap_text.lower().replace(' ', '_')
            if i > 0:
                cap_outline_name = f'{cap_outline_name0}#{cap_outline_name}'
            out_line_flowables.append([
                flowables.AnchorFlowable(cap_outline_name),
                OutlineEntryFlowable(cap_outline_name, cap_text, 0 if i == 0 else 1),
            ])

        return [
            *out_line_flowables[0],
            Paragraph(captions[0], style=self.section_heading_style),
            * out_line_flowables[1],
            Paragraph(captions[1], style=self.sub_section_heading_style),
            table,
            *out_line_flowables[2],
            Paragraph(captions[2], style=self.sub_section_heading_style),
            grouped_table,
            *out_line_flowables[3],
            Paragraph(captions[3], style=self.sub_section_heading_style),
            pie_charts
        ]

    def report(self):
        # photo_path = pathlib.Path(
        #     "/home/ox23/Desktop/Semyon Mamonov CV 2022/Profile photo/Soul-movie-soul22-chemistry.jpg"
        # )
        photo_path = self.profile.photo
        if photo_path:
            photo_path = self.profile.photo.path

        # TODO: Set to False on commit
        debug = False

        full_name = self.profile.user.get_full_name()
        doc = SimpleDocTemplate(
            self.file, pagesize=self.page_size, leftMargin=1.5 * units.cm, rightMargin=1.0 * units.cm,
            topMargin=1 * units.cm, bottomMargin=2 * units.cm,
            title=f"{full_name} - {self.profile.position}",
            subject=f"Curriculum vitae (CV)/Resume",
            author=full_name,
            creator="CV maker - http://semyon72.com/...",
            showBoundary=debug or self._debug
        )
        doc.build([
            PhotoResourceTable(photo_path, self.get_resources(), debug=debug or self._debug),
            * self.get_position(),
            # *[Paragraph('HKJHkhkj kh jkh') for _ in range(39)],
            utils.PaddedMultiCol(
                [self.get_summary_qualification(), self.get_soft_skills()], ['65%', '35%'],
                spaceBefore=12,
                padding=(6, 12),
                draw_hooks=[utils.VerticalInnerBorders(color=colors.orange, width=.5)],
                debug=debug or self._debug,
            ),
            *self.get_employment_history(), *self.get_education(debug=debug or self._debug),
            utils.PaddedMultiCol(
                [self.get_language(debug=debug or self._debug), self.get_hobby()], ['50%', '50%'],
                spaceBefore=12,
                padding=(6, 12),
                draw_hooks=[utils.VerticalInnerBorders(color=colors.orange, width=.5)],
                debug=debug or self._debug,
            ),
            *self.get_project(),
            *self.get_skill_facts(),
            ShowOutlineFlowable(),
            utils.PageOfPagesFlowable()
        ])
