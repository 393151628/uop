# -*- coding: utf-8 -*-

import logging

from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.options import define, options
import os
from config import APP_ENV

define('port', type=int, default=5000)
# deploy or debug
define('mode', default='debug')

# dev, test, prod
define('deploy', default='dev')
options.parse_command_line()
os.system('rm -rf config.py')
os.system('rm -rf conf')
os.system('ln -s conf.d/%s  conf '%(options.deploy))
os.system('ln -s conf/config.py  config.py')

from uop import create_app

def main():
    if options.mode.lower() == "debug":
        from tornado import autoreload
        autoreload.start()
 
    #APP_ENV = 'development'
    #if options.deploy.lower() == 'test':
    #    APP_ENV = 'testing'
    #elif options.deploy.lower() == 'prod':
    #    # TODO:
    #    pass

    app = create_app(APP_ENV)
    # app.run(host='0.0.0.0', debug=True)
    http_server = HTTPServer(WSGIContainer(app))
    http_server.listen(options.port)
    logging.warn("[UOP] UOP is running on: localhost:%d", options.port)
    IOLoop.instance().start()

if __name__ == '__main__':
    main()
