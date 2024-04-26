# IDE: PyCharm
# Project: cv
# Path: apps/cv
# File: report.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-10-29 (y-m-d) 3:18 PM
import datetime
import functools
import itertools
import pathlib
import string
import tempfile


from . import utils
from dateutil.relativedelta import relativedelta
import PIL.Image as PILImage

from functools import cached_property
from io import BytesIO
from typing import Union, Optional, NamedTuple

from django.db.models import Model, F
from reportlab.graphics import shapes
from reportlab.graphics.charts.axes import AxisLineAnnotation, AxisLabelAnnotation
from reportlab.graphics.charts.barcharts import VerticalBarChart, HorizontalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.slidebox import SlideBox
from reportlab.graphics.charts.textlabels import Label
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import styles, colors, units
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfgen.textobject import PDFTextObject
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Flowable, Table, TableStyle, NullDraw, Image, ListFlowable, MultiCol,
    HRFlowable, KeepTogether
)
import reportlab.platypus.flowables as flowables

import reportlab.rl_config as rl_config
from django.db.models.fields import Field

from apps.cv import models
from . import utils


"""
Best examples for chart's gallery with source code 
https://www.reportlab.com/chartgallery/
"""

assert False, 'Implementation, which implies formatting using tables'\
              ' is not completed because it cannot split the one row long (tall) tables'


class ParagraphExp(Paragraph):

    def __init__(self, text, style: Optional[styles.ParagraphStyle] = None, bulletText=None,
                 frags=None, caseSensitive=1, encoding='utf8', **style_kwargs):
        self.__style_kwargs = style_kwargs
        super().__init__(text, style, bulletText, frags, caseSensitive, encoding)

    def _setup(self, text, style: styles.ParagraphStyle, bulletText, frags, cleaner):
        if self.__style_kwargs:
            style = styles.ParagraphStyle(type(self).__name__, parent=style, **self.__style_kwargs)
        del self.__style_kwargs
        return super()._setup(text, style, bulletText, frags, cleaner)


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
        if link.startswith(('http://', 'https://')):
            link = f"<a href=\"{link}\" color=\"blue\">{self._check_href_link(link)}</a>"
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
                        Paragraph('Communication resources:', style=styles.getSampleStyleSheet()['Heading3']),
                        self._resource_table
                    ]
                ]], style=style, colWidths=['33%', '67%']
            )
        return self.__result_table

    def drawOn(self, canvas, x, y, _sW=0):
        rt = self._get_result_table()
        rt.drawOn(canvas, x, y, _sW)

    def wrap(self, availWidth, availHeight):
        rt = self._get_result_table()
        return rt.wrap(availWidth, availHeight)


class LanguageFlowable(Flowable):
    """
        data are dictionary such as
        {'English': 'B2', 'Ukrainian': 'Native', Spanish': 'upper-intermediate'}
    """

    language_available_levels: list[tuple[str, str]] = [
        ('Z', 'Zero'), ('A1', 'Beginner'), ('A2', 'Elementary'),
        ('B1', 'Pre-Intermediate'), ('B2', 'Intermediate'), ('C1', 'Upper-Intermediate'),
        ('C2', 'Advanced'), ('N', 'Native')
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
            firstLineIndent=0
        )

    def get_resources(self) -> dict:
        qs = self.profile.cvuserresource_set.select_related('resource').all()
        return {r.resource.resource: r.link for r in qs}

    def get_soft_skills(self) -> list[Flowable]:
        return [
            Paragraph('Soft skills', style=self.section_heading_style),
            *[
                Paragraph(line, style=self.list_item_style, bulletText=flowables._bulletNames['rarrowhead']) for line in self.profile.soft_skill.splitlines()
            ]
            # ListFlowable(
            #     [Paragraph(line, style=self.list_item_style) for line in self.profile.soft_skill.splitlines()],
            #     start=flowables._bulletNames['rarrowhead'],
            #     bulletType='bullet',
            #     bulletFontName=self.list_item_style.fontName,
            #     bulletFontSize=self.list_item_style.fontSize,
            # )
        ]

    def get_summary_qualification(self) -> list[Flowable]:
        fld: Field = self.profile._meta.get_field('summary_qualification')
        body_style = styles.ParagraphStyle(
            'IndentedBodyStyle', parent=self.section_body_style, firstLineIndent=self.indentation
        )
        return [
            Paragraph(fld.verbose_name.capitalize(), style=self.section_heading_style),
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

            presp = ListFlowable(
                [Paragraph(line) for line in wpr.responsibility.splitlines()],
                start=flowables._bulletNames['squarelrs'],
                bulletType='bullet', bulletFontName=self.list_item_style.fontName,
                bulletFontSize=self.list_item_style.fontSize,
                leftIndent=self.indentation,
            )

            drange, dur = self.date_dif_format(wpr.begin, wpr.end)
            data = [
                [Paragraph(wpr.role, style=self.sub_section_heading_style), ''],
                [presp, [
                    Paragraph(f'{drange}', style=self.date_style),
                    Paragraph(f'{dur}', style=self.date_style)
                ]]
            ]
            tb = Table(data, colWidths=['80%', '20%'], style=style, spaceAfter=2)
            return tb

        def get_workplace_table(wp: models.CVWorkplace, debug=False) -> Table:
            prange, pdur = self.date_dif_format(wp.begin, wp.end)
            wprs = []
            for wpr in wp.cvworkplaceresponsibility_set.order_by('-begin').all():
                wprs.append(get_responsibility_table(wpr, debug=debug))

            data = [
                [
                    [Paragraph(prange, style=self.date_style), Paragraph(pdur, style=self.date_style)],
                    Paragraph(wp.workplace, style=self.sub_section_heading_style)
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
            return tb

        qs_work_places = models.CVWorkplace.objects.filter(profile=self.profile).prefetch_related('cvworkplaceresponsibility_set').\
            order_by('-begin').all()

        res = [Paragraph('Employment history', style=self.section_heading_style)]
        for i, wp in enumerate(qs_work_places):
            twp = get_workplace_table(wp, debug)
            if i == 0 and not res[0].style.keepWithNext:
                res[0] = KeepTogether([res[0], twp])
            else:
                res.append(twp)
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
        res = [Paragraph('Education', style=self.section_heading_style)]
        for i, ed in enumerate(eds):
            ted = get_education_table(ed, debug=debug)
            if i == 0 and not res[0].style.keepWithNext:
                res[0] = KeepTogether([res[0], ted])
            else:
                res.append(ted)

        return res

    # def _language_avaible_levels(self) -> list[tuple[str, str]]:
    #     return [('Z', 'Zero'), ('A1', 'Beginner'), ('A2', 'Elementary'),
    #             ('B1', 'Pre-Intermediate'), ('B2', 'Intermediate'), ('C1', 'Upper-Intermediate'),
    #             ('C2', 'Advanced'), ('N', 'Native')]
    #
    # def _language_process_raw_data(self, data: list[dict, object], level_k='level', lang_k='lang') -> tuple[dict[str, int], list[str]]:
    #     """
    #         data is a list of dictionaries such as
    #             [
    #                 {'lang': 'English', 'level': 'B2'},
    #                 {'lang': 'Ukrainian', 'level': 'Native'},
    #                 {'lang': 'Spanish', 'level': 'upper-intermediate'},
    #             ]
    #         or a list of objects, each of which has attributes with identical names
    #
    #         returns 2-tuple
    #         * [0] is {'English': 4, 'Ukrainian': 7, Spanish': 5}
    #         * [1] is ['warning1', 'warning2', ... ]
    #     """
    #     res, warnings = {}, []
    #     avail_lvls = [v.lower() for v in itertools.chain(*self._language_avaible_levels())]
    #     for di, lang in enumerate(data):
    #         if di == 0:
    #             if isinstance(lang, dict):
    #                 accessor = dict.__getitem__
    #             else:
    #                 accessor = getattr
    #         level = accessor(lang, level_k)
    #         try:
    #             i = avail_lvls.index(level.lower())
    #         except ValueError:
    #             # add error message on pdf
    #             if not warnings:
    #                 warnings.append(f'Available levels are: {avail_lvls}')
    #             warnings.append(f'Unknown level "{level}"')
    #         else:
    #             res[accessor(lang, lang_k)] = i // 2
    #
    #     return res, warnings
    #
    # def _get_language_barchart(self, data: dict[str, int], scale: float = 1.0, debug=True) -> Drawing:
    #     d = Drawing(0, 0)
    #     if debug:
    #         d._showBoundary = True
    #
    #     values = self._language_avaible_levels()
    #     categories = [*data.keys()]
    #
    #     bc = VerticalBarChart()
    #     bc.data = [[*data.values()]]
    #
    #     bc.bars.strokeWidth = .5
    #     bc.valueAxis.valueMin = 0
    #     bc.valueAxis.valueMax = len(values)-1
    #     bc.valueAxis.valueStep = 1
    #
    #     bc.valueAxis.labelTextFormat = [f'{lvl} ({lvl_desc})' for lvl, lvl_desc in values]
    #     bc.valueAxis.labels.textAnchor = 'end'
    #     bc.valueAxis.labels.fontSize -= 2
    #     bc.valueAxis.labels.dx -= 2
    #     bc.valueAxis.labels.dy += 1
    #
    #     minx, miny, maxx, maxy = bc.valueAxis.draw().getBounds()
    #     vAW, vAH = maxx - minx, maxy-miny
    #     bc.x = vAW + 6
    #
    #     bc.categoryAxis.categoryNames = categories
    #     bc.categoryAxis.labels.boxAnchor = 'w'
    #     bc.categoryAxis.labels.angle = 90
    #     bc.categoryAxis.labels.dy = 6
    #     bc.categoryAxis.labels.boxFillColor = colors.HexColor('#FFEDCC')
    #     bc.categoryAxis.labels.boxStrokeColor = colors.lightgrey
    #     bc.categoryAxis.labels.topPadding = 1
    #     bc.categoryAxis.labels.bottomPadding = 1
    #     bc.categoryAxis.labels.leftPadding = 3
    #     bc.categoryAxis.labels.rightPadding = 3
    #
    #     # calc barWidth to encapsulate category's text and proper alignment its
    #     maxLW90 = 0
    #     for i, cat in enumerate(sorted(categories, key=len, reverse=True)):
    #         l = bc.categoryAxis.labels[i]
    #         l.setText(cat)
    #         l.textAnchor = 'start'
    #         l.computeSize()
    #         if i == 0:
    #             l_width = l._width
    #         l.width = l_width
    #
    #         if l._height > maxLW90:
    #             maxLW90 = l._height
    #
    #     bc.barWidth = maxLW90 + 6
    #     bc.width = bc.barWidth * len(categories) + bc.groupSpacing * len(categories)
    #     bc.height = vAH + 20
    #     bc.bars[0].fillColor = colors.orange
    #
    #     d.width = bc.x + bc.width + 6
    #     d.height = bc.height + 24
    #     d.vAlign = 'CENTER'
    #
    #     if scale != 1.0:
    #         d.scale(scale, scale)
    #         d.width *= scale
    #         d.height *= scale
    #
    #     d.add(bc, 'Languages')
    #     return d
    #
    # def get_language(self, debug=True):
    #     # CVLanguage
    #     #     lang = models.CharField(max_length=24)
    #     #     level = models.CharField(max_length=24)
    #     #     notes = models.CharField(max_length=248)
    #     res = [Paragraph('Languages', style=self.section_heading_style)]
    #
    #     data, warn = self._language_process_raw_data(self.profile.cvlanguage_set.all())
    #     if warn:
    #         res.append(Paragraph(f'<para color="green">{warn[0]}</para>'))
    #         res.extend([Paragraph(f'<para color="red">{w}</para>') for w in warn[1:]])
    #
    #     d = self._get_language_barchart(data, debug=debug)
    #
    #     d.height += 50
    #
    #     d.add(Label(x=10, y=50, _text='Hello World. '*10, fontName='Times-Roman', fontSize=10))
    #     d.add(Label(x=10, y=20, _text='bla ' * 30, fontName='Times-Roman', fontSize=12))
    #
    #     res.append(d)
    #     return res

    def get_language(self, debug=False) -> list[Flowable]:
        res = [Paragraph('Languages', style=self.section_heading_style)]
        for lang in self.profile.cvlanguage_set.all():
            res.append(LanguageFlowable(lang, width=0, debug=debug))
        return res

    def get_hobby(self) -> list[Flowable]:
        res = [
            Paragraph('Hobby', style=self.section_heading_style),
            ListFlowable(
                [Paragraph(hobby.description, style=self.list_item_style) for hobby in self.profile.cvhobby_set.all()],
                bulletType='bullet',
                start=flowables._bulletNames['rarrowhead'],
                bulletFontName=self.list_item_style.fontName,
                bulletFontSize=self.list_item_style.fontSize,
            )
        ]
        return res

    def get_project(self) -> list[Flowable]:
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

        res = []
        projs = self.profile.cvproject_set.order_by('-begin').all()
        for proj in projs:
            proj_techs = proj.cvprojecttechnology_set.select_related('technology').order_by(F('duration').desc(), 'technology__technology_type').all()
            for proj_tech in proj_techs:
                tech = proj_tech.technology.technology
                tech_type = proj_tech.technology.technology_type
                tech_type_label = models.CVTechnologies.TechnologyTypes(tech_type).label
            pass

        return res

    def get_skill_facts(self):
        return []

    def report(self):
        # photo_path = pathlib.Path(
        #     "/home/ox23/Desktop/Semyon Mamonov CV 2022/Profile photo/Soul-movie-soul22-chemistry.jpg"
        # )
        photo_path = self.profile.photo
        if photo_path:
            photo_path = self.profile.photo.path

        # TODO: set to False on commit
        debug = False

        full_name = self.profile.user.get_full_name()
        doc = SimpleDocTemplate(
            self.file, pagesize=self.page_size, leftMargin=1.5 * units.cm, rightMargin=1.0 * units.cm,
            topMargin=1 * units.cm, bottomMargin=2 * units.cm,
            title=f"{full_name} - {self.profile.position}", author=full_name,
            creator="CV maker - http://semyon72.com/...",
            showBoundary=debug or self._debug
        )
        doc.build([
            PhotoResourceTable(photo_path, self.get_resources(), debug=debug or self._debug),
            *self.get_position(),
            *self.put_into_table(
                self.get_summary_qualification(), self.get_soft_skills(),
                '65%', '35%', spaceBefore=12,
                debug=debug or self._debug
            ),
            *self.get_employment_history(), *self.get_education(debug=debug or self._debug),
            *self.put_into_table(
                self.get_language(debug=debug or self._debug), self.get_hobby(),
                '50%', '50%', spaceBefore=12,
                debug=debug or self._debug
            ),
            *self.get_project(),
            *self.get_skill_facts(),
        ])
