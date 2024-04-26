# IDE: PyCharm
# Project: cv
# Path: apps/cv_ui/templatetags
# File: cv_ui_extras.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2024-01-19 (y-m-d) 10:15 AM

import functools
from inspect import getfullargspec

from django import template
from django.template.library import parse_bits

register = template.Library()


class Add2ContextNode(template.Node):

    def __init__(self, tag: str, nodelist: template.NodeList, var_name: str):
        self.tag = tag
        self.var_name = var_name
        self.nodelist = nodelist

        # used for second implementation
        # self.var_name_values = {}

    def render(self, context: template.Context):
        _tag = f'__{self.tag}'
        cleaned_content = ' '.join(l.strip() for l in self.nodelist.render(context).splitlines())
        parser = template.base.Parser(template.base.Lexer(f'{{% {_tag} {cleaned_content} %}}').tokenize())

        bits = parser.tokens[0].split_contents()[1:]
        params, varargs, varkw, defaults, kwonly, kwonly_defaults, _ = getfullargspec(lambda *args, **kwargs: '')
        args, kwargs = parse_bits(
            parser, bits, params, varargs, varkw, defaults, kwonly, kwonly_defaults, None, _tag
        )
        context[self.var_name] = {str(k): v.resolve({}) for k, v in kwargs.items()}
        return ""

    # Second implementation

    # def __add2context(self, *args, **kwargs):
    #     self.var_name_values = kwargs
    #     return ''
    #

    # def render(self, context: template.Context):
    #     _tag = f'__{self.tag}'
    #     block_content = ' '.join(l.strip() for l in self.nodelist.render(context).splitlines())
    #     register.simple_tag(functools.partial(self.__add2context, self), name=_tag)
    #     template.Template(f'{{% load {self.__module__.split(".")[-1]} %}}\n {{% {_tag} {block_content} %}}').render(template.Context({}))
    #     del register.tags[_tag]
    #     context[self.var_name] = self.var_name_values
    #     return ""


@register.tag
def add2context(parser: template.base.Parser, token: template.base.Token):
    contents: str = token.contents
    words = contents.split()
    if not (len(words) == 3 and words[1].lower() == 'as' and words[2].isidentifier()):
        raise template.TemplateSyntaxError(
            f'{words[0]} tag requires syntax {{% {words[0]} as valid_variable_name %}}'
        )

    nodelist = parser.parse(("endadd2context",))
    parser.delete_first_token()
    return Add2ContextNode(words[0], nodelist, words[2])


@register.filter
def snake2cap(value):
    return str(value).replace('_', ' ').capitalize()