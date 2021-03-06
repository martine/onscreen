#!/usr/bin/python

import cgi
import os
import hashlib
from django.utils import simplejson as json
import sys
from datetime import datetime, timedelta

import web

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext.webapp import template

DISPLAY_N_RECENT = 5
CYCLE_TIME_SECONDS = 30
ENTRIES_NEWER_THAN_HOURS = 6

class Entry(db.Model):
    owner = db.UserProperty(required=True)
    date = db.DateTimeProperty(auto_now_add=True)
    image = db.BlobProperty()
    url = db.StringProperty()

class State(db.Model):
    slot = db.IntegerProperty()
    since = db.DateTimeProperty()


def get_current_entry():
    now = datetime.now()
    query = Entry.gql(' WHERE date > :date ORDER BY date DESC',
                      date=now - timedelta(hours=ENTRIES_NEWER_THAN_HOURS))
    entries = query.fetch(DISPLAY_N_RECENT)

    if not entries:
        return None

    state = State.gql('').get()
    if not state:
        state = State(slot=0, since=now)
        state.put()
    else:
        # If the newest image was uploaded recently, keep it up for 15 minutes.
        if entries[0].date > now - timedelta(minutes=15):
            if state.slot != 0:
                state.slot = 0
                state.since = now
                state.put()
        else:
            # No recent image -- We're in the "cycling" state.  See if
            # it's time to cycle.
            if (now - state.since > timedelta(seconds=CYCLE_TIME_SECONDS)
                or state.slot >= len(entries)):                # entry expired?
                state.slot = (state.slot + 1) % min(len(entries), DISPLAY_N_RECENT)
                state.since = now
                state.put()

    return entries[state.slot]


def current_json():
    entry = get_current_entry()
    if entry:
        data = {
            'owner': entry.owner.nickname(),
            'id': entry.key().id()
            }

        if entry.url:
            data['url'] = entry.url
        elif entry.image:
            data['image'] = '/image/%d' % entry.key().id()
        return json.dumps(data)
    else:
        return "{}"


def check_user(func):
    """Decorator that verifies the user is allowed to see any pages"""
    def f(path, *args, **kwargs):
        ok = False
        user = users.get_current_user()
        if user:
            _, domain = user.email().split('@')
            if domain in ('google.com', 'example.com'):
                ok = True
        if not ok:
            query = os.environ.get('QUERY_STRING', '')
            hex = hashlib.sha1(query).hexdigest()
            if hex == 'a0772fcc7ffe0e18236513c20f2eb25f8cdcf32a':
                ok = True
        if not ok:
            raise web.Special(302, users.create_login_url(path))
        return func(path, *args, **kwargs)
    return f


def new(path):
    user = users.get_current_user()

    method = os.environ['REQUEST_METHOD']
    if method == 'GET':
        if not user:
            raise web.Special(302, users.create_login_url(path))
        else:
            print template.render('templates/new.tmpl', {})
    elif method == 'POST':
        if not user:
            raise web.Error(400, 'must login')
        form = cgi.FieldStorage()
        image = form['image'].value
        if image:
            print 'accepted %d bytes of image' % len(image)
            entry = Entry(owner=user, image=image)
            entry.put()
        elif 'url' in form:
            print 'accepted url'
            entry = Entry(owner=user, url=form['url'].value)
            entry.put()
        else:
            raise web.Error(400, 'no image/url included')

@check_user
def handle_request(path):
    if path == '/':
        print template.render('templates/frontpage.tmpl', {})
    elif path == '/cycle':
        print template.render('templates/image.tmpl',
                              { 'json': current_json(),
                                'query': os.environ.get('QUERY_STRING', ''),
                                'cycle': 1 })
    elif path == '/new':
        return new(path)
    elif path.startswith('/image/'):
        id = int(path[len('/image/'):])
        entry = Entry.get_by_id(id)
        if not entry:
            raise web.Error(404)
        print entry.image
        return {}
    elif path == '/json':
        print current_json()
        return {'Content-Type': 'application/json'}
    else:
        raise web.Error(404)

web.run(handle_request)
