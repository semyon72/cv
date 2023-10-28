# IDE: PyCharm
# Project: cv
# Path: apps/cv/management/commands
# File: loaduserdata.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-09-28 (y-m-d) 8:11 AM
import argparse
import base64
import binascii
import datetime
import difflib
import functools
import hashlib
import itertools
import json
import pathlib
import string
import urllib.parse
from collections import UserDict, namedtuple
from typing import Union, TextIO, Optional, Tuple, Any, Callable, Mapping, Type
import getpass

import requests
from bs4 import BeautifulSoup, Tag, SoupStrainer
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.core.management import BaseCommand
from django.test.testcases import LiveServerThread, _StaticFilesHandler
from django.middleware import csrf
from django.urls import reverse
from rest_framework.fields import DurationField

from apps.cv import models
from apps.cv.compare import DataComparer, CompleteDataComparer


class LiveServer(LiveServerThread):
    """
    This launch a live HTTP server in a separate thread so that may use the real HTTP frameworks,
    such as Selenium, Requests for example, instead of the built-in dummy client.
    """

    def __init__(self, host, static_handler, connections_override=None, port=0):
        if not static_handler:
            static_handler = _StaticFilesHandler
        super().__init__(host, static_handler, connections_override, port)

    @property
    def live_server_url(self):
        return "http://%s:%s" % (self.host, self.port)

    def __enter__(self):
        self.daemon = True
        self.start()

        # Wait for the live server to be ready
        self.is_ready.wait()
        if self.error:
            raise self.error

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.terminate()


class CVLoader:
    pk_field_name = DataComparer.pk_field_name
    data_comparer_class: Type[CompleteDataComparer] = CompleteDataComparer

    def __init__(self, server_url, session: requests.Session, command: BaseCommand, data_comparer_class: Optional[DataComparer] = None) -> None:
        self.session = session
        self.command = command
        self.server_url = server_url
        if isinstance(data_comparer_class, type) and issubclass(data_comparer_class, CompleteDataComparer):
            self.data_comparer_class = data_comparer_class

    def _respond_msg(self, response: requests.Response, msg_prefix, style: str = 'ERROR'):
        """
            style is string from django.utils.termcolors.PALETTES[xxx_PALETTE] as
            "ERROR", "SUCCESS", "WARNING", "NOTICE" etc
        """
        msg = f'{msg_prefix} [{response.request.method}->{response.request.url}] is responded ' \
              f'[{response.status_code}]: "{response.text}" \n' \
              f'\tdata:{response.request.body}'

        method = getattr(self.command.style, style)
        self.command.stdout.write(method(msg))

    def report_if_response_is_not_ok(self, response: requests.Response, msg_prefix):
        if not response.ok:
            self._respond_msg(response, msg_prefix, 'ERROR')

    def _load_independent_part(self, load_data: list, report_msg_prefix: str, view_name: Union[str, callable],
                               post_hook: callable = None, put_hook: callable = None):
        """
            view_name - It can be a `callable` that takes the name of action and must return a `view name` for that action
            post_hook(data) - prepared data for updating
            post_hook(sdata, data) - prepared data for updating, `sdata` is the source data that was returned by the server

            These hooks must return either modified or no `data`
        """
        url_lc = f'{self.server_url}{reverse(view_name("list_create") if callable(view_name) else view_name)}'
        response = self.session.get(url_lc)
        self.report_if_response_is_not_ok(response, report_msg_prefix)

        stored_data = response.json()
        dc = self.data_comparer_class(stored_data, load_data)
        for u in dc.prepare_to_update():
            uid = u.pop(dc.pk_field_name, None)
            if uid is None:
                response = self.session.post(url_lc, json=post_hook(u) if callable(post_hook) else u)
            else:
                url_rud = f'{self.server_url}{reverse(view_name("put") if callable(view_name) else view_name, args=[uid])}'
                u[dc.pk_field_name] = uid
                response = self.session.put(
                    url_rud,
                    json=put_hook([s for s in dc.s if s[self.pk_field_name] == uid][0], u) if callable(put_hook) else u
                )

            self.report_if_response_is_not_ok(response, report_msg_prefix)

    def load_profile(self, load_data):
        msg_prefix = 'The Profile'

        profile_url = f"{self.server_url}{reverse('cv:profile')}"
        response = self.session.get(profile_url)
        action = self.session.put
        if response.status_code == requests.codes.not_found:
            action = self.session.post
        elif not response.ok:
            self._respond_msg(response, msg_prefix, 'ERROR')
            return

        # A check, is `photo` base64_encoded
        photo = load_data.get('photo')
        if photo:
            # Photo 200*200 => 40 000 Bytes at least.
            # If compressed (jpg) then It can be smaller but I am sure a photo less 8K is impossible.
            if len(photo) <= 8*1024:
                # possible, it represents a path to image file
                photo_path = pathlib.Path(photo)
                if photo_path.is_file():
                    # OK
                    with open(photo_path, 'rb') as f:
                        photo = base64.b64encode(f.read()).decode()
            else:
                # it may already represent a `base64_encoded` image
                try:
                    base64.b64decode(photo, validate=True)
                except binascii.Error as exc:
                    msg = f'{msg_prefix} contains `photo` that looks like a base64 encoded image file.' \
                          f' base64.b64decode ERROR: {exc}'
                    self.command.stdout.write(self.command.style.ERROR(msg))
                    return

        load_data['photo'] = photo
        act_response = action(profile_url, json=load_data)
        self.report_if_response_is_not_ok(act_response, msg_prefix)

    def load_education(self, load_data):
        self._load_independent_part(load_data, 'The Education', "cv:education")

    def load_hobby(self, load_data):
        self._load_independent_part(load_data, 'The Hobby', "cv:hobby")

    def load_language(self, load_data):
        self._load_independent_part(load_data, 'The Language', "cv:language")

    def load_workplace(self, load_data):
        self._load_independent_part(load_data, 'The Workplace', "cv:workplace")

    def load_project(self, load_data):
        self._load_independent_part(load_data, 'The Project', "cv:project")

    def _check_date_in_range(self, begin: Union[str, datetime.date], end: Union[str, datetime.date, None],
                             begin_inner: Union[str, datetime.date], end_inner: Union[str, datetime.date, None]) -> bool:
        to_date = datetime.date.fromisoformat
        b, e, b_inner, e_inner = (to_date(_) if isinstance(_, str) else _ for _ in (begin, end, begin_inner, end_inner))
        return b <= b_inner and (e is None or (e_inner is not None and e_inner <= e))

    def load_workplace_project(self):
        to_date = datetime.date.fromisoformat

        def get_projects_for(projects: list, begin: datetime.date, end: Optional[datetime.date], exclude_pids: list):
            """
            Groups the `projects` by `workplace` dates
            """
            res = []

            for pi, p in enumerate(projects):
                if pi in exclude_pids:
                    continue

                if self._check_date_in_range(begin, end, p['begin'], p['end']):
                    exclude_pids.append(pi)
                    res.append(p)
            return res

        def get_workplace_project_to_post(wpps: list[tuple[int, int]], workplace: dict, projects: list[dict]):
            """
            Returns a list of `tuple(workplace.pk, project.pk)`
            There is a side effect to achive optimisation,
            if `wpps` contains `tuple(workplace.pk, project.pk)` it will be removed right after processing.
            """
            pkn = self.pk_field_name
            all_possible = [(w[pkn], p[pkn]) for w, p in itertools.product((workplace,), projects)]

            ci = len(wpps)-1
            while wpps and ci >= 0:
                p4wp = wpps[ci]
                try:
                    all_possible.remove(p4wp)
                except ValueError:
                    pass
                else:
                    # must remove from p4wps
                    del wpps[ci]
                ci -= 1

            return all_possible

        # get workplaces
        url = f'{self.server_url}{reverse("cv:workplace")}'
        wp_response = self.session.get(url)
        self.report_if_response_is_not_ok(wp_response, 'The Workplaces')
        if not wp_response.ok:
            return
        wps = wp_response.json()

        # get projects
        url = f'{self.server_url}{reverse("cv:project")}'
        proj_response = self.session.get(url)
        self.report_if_response_is_not_ok(proj_response, 'The Workplaces')
        ps = proj_response.json()
        if not proj_response.ok:
            return

        # get a `workplace-projects` relationships
        url = f'{self.server_url}{reverse("cv:workplace-project")}'
        wpps_response = self.session.get(url)
        self.report_if_response_is_not_ok(wpps_response, 'The Workplace relationship to the Project')
        wpps: dict[tuple[int, int], dict] = {
            (wpps['workplace'][self.pk_field_name], wpps['project'][self.pk_field_name]): wpps for wpps in wpps_response.json()
        }
        wpps_list = [*wpps.keys()]
        if not wpps_response.ok:
            return

        matched_pids = []
        for wpi, wp in enumerate(wps):
            ps4wp = get_projects_for(
                ps, to_date(wp['begin']), None if wp['end'] is None else to_date(wp['end']), matched_pids
            )
            # if ps4wp is empty -> Attension (no matches for wp)
            if not ps4wp:
                self.command.stdout.write(
                    self.command.style.WARNING(f'The Workplace has no any related project \n\t {wp}')
                )
            else:
                # Add the workplace relationship to the project if it does not exist
                to_add = get_workplace_project_to_post(wpps_list, wp, ps4wp)
                for wrkp_pk, proj_pk in to_add:
                    response = self.session.post(url, json={'workplace': wrkp_pk, 'project': proj_pk})
                    self.report_if_response_is_not_ok(response, 'The Workplace relationship to the Project')

        # if matched_pids does not contain all indexes from ps -> Attension (ps has not matched to any wp)
        for pi in (pi for pi, p in enumerate(ps) if pi not in matched_pids):
            self.command.stdout.write(
                self.command.style.WARNING(f'The Project has no any related workplace \n\t {ps[pi]}')
            )

        # if wpps still have some elements - Possible, Integrity was violated (extra rows in WorkplaceProject)
        if wpps_list:
            for wpps_list_key in wpps_list:
                self.command.stdout.write(
                    self.command.style.WARNING(f'The WorkplaceProject relationship has extra rows. Possible, Integrity was violated \n\t {wpps[wpps_list_key]}')
                )

    def load_workplace_responsibility(self, load_data):

        wp_response = self.session.get(f'{self.server_url}{reverse("cv:workplace")}')
        if not wp_response.ok:
            self._respond_msg(wp_response, 'The Workplace', 'ERROR')
            return

        wps = wp_response.json()

        def get_wp_by_date_range(wps, b, e):
            for wp in wps:
                if self._check_date_in_range(wp['begin'], wp['end'], b, e):
                    return wp

        def post_hook(data):
            wp = get_wp_by_date_range(wps, data['begin'], data['end'])
            if wp is not None:
                data['workplace'] = wp[self.pk_field_name]
            return data

        def put_hook(sdata, data):
            data['workplace'] = sdata['workplace'][self.pk_field_name]
            return data

        self._load_independent_part(
            load_data, 'The Workplace responsibilities', "cv:workplace-responsibility",
            post_hook=post_hook, put_hook=put_hook
        )

    def create_resource_dictionary(self):
        """
        It will load the following resources directly through the model:
            "Email", "Skype", "Git", "Site", "Tel", "Telegram"
        but only if `settings.DEBUG` is `True` and `CVResources` has no entries (empty)
        """
        default_resources = ("Email", "Skype", "Git", "Site", "Tel", "Telegram")

        model = models.CVResources
        if settings.DEBUG and model.objects.all().count() == 0:
            model.objects.bulk_create(model(resource=r.lower()) for r in default_resources)
            if model.objects.all().count() != len(default_resources):
                self.command.stdout.write(self.command.style.ERROR(f'Can not load resources {default_resources}'))

    def load_resource(self, load_data):

        class ResourceDataComparer(CompleteDataComparer):

            def _prepare_update_dict(self, u: dict) -> dict:
                u = super()._prepare_update_dict(u)
                ures = u['resource'].lower()
                u['resource'] = res_dict.get(ures, {self.pk_field_name: ures}).get(self.pk_field_name, ures)
                return u

        msg_prefix = 'The Resource'
        res_dict_response = self.session.get(f"{self.server_url}{reverse('cv:resource-lc')}")
        self.report_if_response_is_not_ok(res_dict_response, f'{msg_prefix} (dictionary)')
        if not res_dict_response.ok:
            return

        res_dict: dict[str, dict] = {r['resource'].lower(): r for r in res_dict_response.json()}

        try:
            self.data_comparer_class = ResourceDataComparer
            self._load_independent_part(load_data, msg_prefix, 'cv:user-resource')
        finally:
            self.data_comparer_class = type(self).data_comparer_class

    def load_technology_dictionary(self, load_data):
        # TO_THINK: `technology_dictionary` by essence has only one vary field of small length - `technology`.
        # And it is probably better to use an internal `DataComparer`
        # like `ProjectTechnologyDataComparer` in `load_project_technology` with a narrowed ratio range

        msg_prefix = 'The Technology (dictionary)'

        def view_name(action):
            if action == 'put':
                return 'cv:technology-rud'
            return 'cv:technology-lc'

        def extend_technology(load_data):
            for tech in load_data:
                techs = tech['technology']
                if isinstance(techs, list):
                    for t in techs:
                        yield tech.copy() | {'technology': t.strip()}
                else:
                    tech.setdefault('technology', '').strip()
                    yield tech

        self._load_independent_part([*extend_technology(load_data)], msg_prefix, view_name)

    def load_project_technology(self, load_data):
        # TO_THINK: `project_technology` by essence has only one field that varies - `notes`. All others are keys.
        # And it might be better not to use internal `ProjectTechnologyDataComparer` with narrowed ratio range.

        msg_prefix = 'The Project technologies'

        class ProjectTechnologyDataComparer(CompleteDataComparer):

            def get_proj_by_date_range(itself, projects, at: Union[str, datetime.date, None]):
                for proj in projects:
                    if self._check_date_in_range(proj['begin'], proj['end'], at, at):
                        return proj

            def _get_project(itself, pid: Union[str, int]):
                proj = None
                if not isinstance(pid, (str, int)):
                    self.command.stdout.write(self.command.style.ERROR(
                        f'{msg_prefix}: `project` must be either str or int type.'
                        f' Where str is "yyyy-mm-dd" or "null" that points to a project [`begin` ... `end`] range.'
                        f' Or int that represents a `id` (PK) of project. The used value: {pid}'
                    ))
                elif isinstance(pid, str):
                    proj = itself.get_proj_by_date_range(projects, pid)
                elif isinstance(pid, int):
                    proj = [proj for proj in projects if proj[itself.pk_field_name] == pid]
                    proj = None if len(proj) == 0 else proj[0]
                return proj

            def _get_duration(itself, proj, duration: Optional[str]) -> Optional[str]:
                # if duration is `null` or does not specified then we will calculate it prom project
                # !!! duration can be `null` if project still in process
                to_date = datetime.date.fromisoformat
                if duration is None and proj['end'] is not None:
                    duration = DurationField().to_representation(to_date(proj['end']) - to_date(proj['begin']))
                return duration

            def _prepare_stored_dict(itself, s: dict) -> dict:
                s = super()._prepare_stored_dict(s)
                return s

            def _prepare_update_dict(itself, u: dict) -> dict:
                u = super()._prepare_update_dict(u)

                # get project's `id`
                u_proj = u.get('project')
                proj = itself._get_project(u_proj)
                if proj is not None:
                    u['project'] = proj.get(itself.pk_field_name)
                    u['duration'] = itself._get_duration(proj, u.get('duration'))
                    u['technology'] = technology_map.get(u.get('technology', '').lower(), {}).get(itself.pk_field_name)
                else:
                    self.command.stdout.write(self.command.style.ERROR(
                        f'{msg_prefix}: `project` was not found for {u_proj}'
                    ))

                return u

        projs_response = self.session.get(f'{self.server_url}{reverse("cv:project")}')
        if not projs_response.ok:
            self._respond_msg(projs_response, 'The Project', 'ERROR')
            return

        projects = projs_response.json()

        techs_response = self.session.get(f'{self.server_url}{reverse("cv:technology-lc")}')
        if not techs_response.ok:
            self._respond_msg(projs_response, 'The Technology', 'ERROR')
            return

        technology_map = {tech['technology'].lower(): tech for tech in techs_response.json()}

        def extend_technology(load_data):
            for proj_tech in load_data:
                techs = proj_tech['technology']
                if isinstance(techs, list):
                    for tech in techs:
                        d = {'technology': tech}
                        if isinstance(tech, list):
                            d = {'technology': tech[0], 'notes': tech[1]}
                        yield proj_tech.copy() | d
                else:
                    yield proj_tech

        try:
            self.data_comparer_class = ProjectTechnologyDataComparer
            load_data = list(extend_technology(load_data))
            self._load_independent_part(load_data, msg_prefix, 'cv:project-technology')
        finally:
            del self.data_comparer_class


class Command(BaseCommand):
    help = "Adds/modify data for registered user"
    login_url = reverse('login')
    profile_url = reverse('cv:profile')
    sessionid_cookie_key = 'sessionid'
    csrf_secret_cookie_key = 'csrftoken'
    csrf_token_header_key = 'X-CSRFToken'

    def __init__(self, stdout=None, stderr=None, no_color=False, force_color=False):
        super().__init__(stdout, stderr, no_color, force_color)
        self.session = requests.Session()

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("username", type=str)
        # getpass
        # https://stackoverflow.com/a/28610617
        # https://gist.github.com/namnv609/f462c194e80ed4048cd2
        parser.add_argument("password", type=str)
        parser.add_argument("file", type=str)
        parser.add_argument("host", nargs="?", type=str, default='localhost')
        parser.add_argument("port", nargs="?", type=int, default=0)

    def _extract_login_form(self, content: Union[str, TextIO]) -> Optional[Tag]:
        soup = BeautifulSoup(content, 'lxml', parse_only=SoupStrainer('form'))
        login_form = soup.find('form', action=lambda a: urllib.parse.urlsplit(a).path == self.login_url)

        return login_form

    def _extract_login_data(self, content: Union[str, TextIO]) -> dict:
        login_form = self._extract_login_form(content)
        form_dict = {}
        if not login_form:
            return form_dict

        # Parse fields
        for fi in login_form.find_all('input'):
            name = fi.attrs.get('name')
            if name:
                form_dict[name] = fi.attrs.get('value')
        # return dict with data to request
        # like {username: , password: , csrf:}
        return form_dict

    def _is_bad_login(self, response: requests.Response) -> Optional[str]:
        # Check header for content-type
        req_path = urllib.parse.urlsplit(response.request.url).path
        resp_content_type = response.headers['content-type'].split(';')[0]
        if response.request.method == 'POST' and req_path == self.login_url and resp_content_type == 'text/html':
            # Probably error of logging

            # ensure the response contains login form
            login_form = self._extract_login_form(response.text)
            if login_form:
                # error. Response contains login form with error message
                result = 'Probably, login was wrong'
                # try to find real message. It can be one of AuthenticationForm.error_messages (2)
                soup = BeautifulSoup(response.text, 'lxml')
                error_str = soup.body.find(
                    string=[(v % {'username': 'username'}) for v in AuthenticationForm.error_messages.values()]
                )
                if error_str:
                    result = str(error_str)
                return result

    def login(self, live_server_url: str, parser_options):
        """
            Do the real User logging
            Returns: requests.Session of logged user or None

            test user: test_user/!2#4%6&8
        """
        server_login_url = f"{live_server_url}{self.login_url}"
        login_resp = self.session.get(server_login_url)
        if requests.codes.OK != login_resp.status_code:
            raise ValueError(f'Login form request error: status[{login_resp.status_code}], url[{login_resp.url}]')

        # parse login form
        login_form_data = self._extract_login_data(login_resp.text)
        # fill login form - username & password
        login_form_data |= {
            'username': parser_options['username'],
            'password': parser_options['password'],
            'next': reverse('cv:profile')
        }
        # POST login form
        login_resp = self.session.post(server_login_url, data=login_form_data, allow_redirects=False)

        # Potentially, exists the 3 signs of success:
        #   session_id is set;
        #   redirected to success url;
        #   JSON data is returned.
        # otherwise - login form will returned with error message
        if login_resp.cookies.get(self.sessionid_cookie_key):
            # login is success
            # csrf_secret = login_resp.cookies.get(self.csrf_secret_cookie_key)
            csrf_secret = self.session.cookies[self.csrf_secret_cookie_key]
            assert csrf_secret, "Can't get csrf token from cookie. " \
                                "Probably, CSRF_USE_SESSIONS is True " \
                                "https://docs.djangoproject.com/en/4.2/ref/settings/#csrf-use-sessions"

            # https://docs.djangoproject.com/en/4.2/ref/settings/#csrf-cookie-masked
            csrfmiddlewaretoken = csrf_secret if settings.CSRF_COOKIE_MASKED else csrf._mask_cipher_secret(csrf_secret)
            self.session.headers.update({'X-CSRFToken': csrfmiddlewaretoken})

            if login_resp.is_redirect:
                while login_resp.next:
                    login_resp = self.session.send(login_resp.next)

            # We should create (if not exists) profile before redirect on profile url
            if requests.codes.not_found == login_resp.status_code:
                # profile does not exist
                profile_response = self.session.post(f"{live_server_url}{self.profile_url}", json={})
                if profile_response.status_code != requests.codes.created:
                    raise ValueError(
                        f'Bad profile creation: status[{profile_response.status_code}], url[{profile_response.url}]'
                    )
        else:
            # login is unsuccessful and login_resp should contain login form again
            # self._is_bad_login(login_resp) tests the login form on error message
            err_message = self._is_bad_login(login_resp)
            self.stdout.write(
                self.style.ERROR('login failed [%s]: "%s"' % (login_resp.status_code, err_message))
            )
            exit(1)

    def handle(self, *args, **parser_options):
        # run local server to interact with API

        with LiveServer(host=parser_options['host'], static_handler=None, port=parser_options['port']) as server:
            live_server_url = server.live_server_url  # 'http://127.0.0.1:8000'

            self.login(live_server_url, parser_options)

            # load JSON file
            json_file_path = pathlib.Path(parser_options['file'])
            if not json_file_path.exists() or not json_file_path.is_file():
                self.stdout.write(self.style.ERROR(f'File does not exist: "{json_file_path}"'))
                exit(1)

            with open(json_file_path, 'r') as f:
                try:
                    # for chunk in json.JSONEncoder().iterencode(bigobject):
                    #     mysocket.write(chunk)
                    data = json.load(f)
                except json.JSONDecodeError as exc:
                    self.stdout.write(self.style.ERROR(f'File "{json_file_path}" has errors "{exc}"'))
                    exit(1)

            loader = CVLoader(live_server_url, self.session, self)
            loader.load_profile(data.get('profile', {}))
            loader.load_education(data.get('education', []))
            loader.load_hobby(data.get('hobby', []))
            loader.load_language(data.get('language', []))
            loader.load_workplace(data.get('workplace', []))
            loader.load_project(data.get('project', []))
            loader.load_workplace_project()
            loader.load_workplace_responsibility(data.get('workplace_responsibility', []))

            loader.create_resource_dictionary()  # It almost is hard-coded for now
            loader.load_resource(data.get('resource', []))

            loader.load_technology_dictionary(data.get('technology', []))
            loader.load_project_technology(data.get('project-technology', []))
