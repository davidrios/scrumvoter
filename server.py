import asyncio
from datetime import datetime
from configparser import SafeConfigParser
from os import path
from pathlib import Path

import aiopg
import pytz
from aiohttp import web
from mako.lookup import TemplateLookup
from pyjade.ext.mako import preprocessor as mako_preprocessor
from psycopg2.extras import DictCursor

MY_DIR = path.dirname(__file__)
TEMPLATES_DIR = path.join(MY_DIR, 'templates')
jade_lookup = TemplateLookup(directories=[TEMPLATES_DIR], input_encoding='utf8', strict_undefined=True, preprocessor=mako_preprocessor)
templates_path = Path(TEMPLATES_DIR)
for template in templates_path.rglob('*.jade'):
    jade_lookup.get_template(str(template.relative_to(TEMPLATES_DIR)))


def jade_response(templatename, **kwargs):
    mytemplate = jade_lookup.get_template(templatename)
    response = web.Response()
    response.content_type = 'text/html'
    response.charset = 'utf-8'
    response.text = mytemplate.render_unicode(**kwargs)
    return response


class ResultObject(object):
    def __init__(self, result):
        self._result = result

    def __getattr__(self, name):
        if self._result is None:
            return None
        return self._result[name]


class ScrumVoter(object):
    def __init__(self, loop, pool):
        self._loop = loop
        self._pool = pool

    @asyncio.coroutine
    def sprint_edit(self, request):
        item_id = request.match_info.get('id')
        item = None
        if item_id is not None:
            with (yield from self._pool.cursor()) as cursor:
                yield from cursor.execute('select * from sprints where id = %s', item_id)
                item = yield from cursor.fetchone()

        if request.method == 'POST':
            yield from request.post()
            if item_id is None:
                qr = 'insert into sprints values (default, %(name)s, %(sprint_date)s) returning id'
            else:
                qr = 'update sprints set name=%(name)s, sprint_date=%(sprint_date)s where id = %(id)s returning id'
            with (yield from self._pool.cursor()) as cursor:
                params = dict(request.POST)
                params['id'] = item_id
                yield from cursor.execute(qr, params)
                item_id = (yield from cursor.fetchone())[0]

            raise web.HTTPSeeOther('/sprint/edit/{}'.format(item_id))

        result_item = ResultObject(item)
        if result_item.sprint_date is None:
            result_item.sprint_date = datetime.now()

        return jade_response('sprint_edit.jade', item=result_item)

    @asyncio.coroutine
    def index(self, request):
        with (yield from self._pool.cursor()) as cursor:
            yield from cursor.execute('select * from sprints order by sprint_date desc')
            sprints = yield from cursor.fetchall()
        return jade_response('index.jade', sprints=[ResultObject(i) for i in sprints])


@asyncio.coroutine
def init(loop):
    config = SafeConfigParser()
    config.read([path.join(MY_DIR, 'config.ini')])

    pool = yield from aiopg.create_pool(maxsize=50, cursor_factory=DictCursor, **dict(config.items('db')))
    sv = ScrumVoter(loop, pool)
    webapp = web.Application(loop=loop)
    webapp.router.add_route('GET', '/', sv.index)
    webapp.router.add_route('*', '/sprint/new', sv.sprint_edit)
    webapp.router.add_route('*', '/sprint/edit/{id}', sv.sprint_edit)
    webapp.router.add_static('/static', path.join(MY_DIR, 'static'))

    srv = yield from loop.create_server(webapp.make_handler(), '0.0.0.0', 8095)
    print("Server started at http://0.0.0.0:8095")
    return srv


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init(loop))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
