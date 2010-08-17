#!/usr/bin/python

import os
import sys
import cStringIO
import cgitb
cgitb.enable()

class Error(Exception):
    def __init__(self, code, text=None):
        self.code = code
        self.text = text
Special = Error

def run(f):
    path = os.environ['PATH_INFO']
    try:
        headers = None
        try:
            orig_stdout = sys.stdout
            sys.stdout = cStringIO.StringIO()
            headers = f(path)
            output = sys.stdout.getvalue()
            sys.stdout.close()
        finally:
            sys.stdout = orig_stdout
        if len(output) == 0:
            raise web.Error(500, 'no output')
        print 'Status: 200 OK'
        if headers is None:
            headers = {
                'Content-Type': 'text/html',
                }
        if 'Content-Length' not in headers:
            headers['Content-Length'] = str(len(output))
        for key, val in headers.iteritems():
            print '%s: %s' % (key, val)
        print
        print output
    except Error, e:
        status_text = {
            302: 'Redirect',
            400: 'Bad Request',
            404: 'Not Found',
            500: 'Internal Server Error'
            }[e.code]
        print "Status: %d %s" % (e.code, status_text)
        if e.code == 302:
            print "Location:", e.text
            return

        print "Content-Type: text/plain"
        print
        if e.text:
            print status_text + ':', e.text
        else:
            print status_text