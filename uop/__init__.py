# -*- coding: utf-8 -*-

from flask import Flask, redirect
from flask_restful import Resource, Api
from flask_apscheduler import APScheduler

from config import configs
from models import db
from uop.log import logger_setting, Log
from uop.auth import auth_blueprint
from uop.res_callback import res_callback_blueprint
from uop.item_info import iteminfo_blueprint
from uop.deployment import deployment_blueprint
from uop.resources import resources_blueprint
from uop.approval import approval_blueprint
from uop.deploy_callback import deploy_cb_blueprint
from uop.resource_view import resource_view_blueprint
from uop.disconf import disconf_blueprint
from uop.configure import configure_blueprint
from uop.pool import pool_blueprint
from uop.permission import perm_blueprint
class Config(object):
    JOBS = [
        # {
        #     'id': 'delete_res_handler',
        #     'func': 'uop.scheduler_util:delete_res_handler',
        #     #'args': (1, 2),
        #     'trigger': 'interval',
        #     'seconds': 60
        # },
        {
            'id': 'flush_crp_to_cmdb',
            'func': 'uop.scheduler_util:flush_crp_to_cmdb',
            # 'args': (1, 2),
            'trigger': 'interval',
            'seconds': 60 * 5
        }
    ]

    SCHEDULER_API_ENABLED = True


def create_app(config_name):
    app = Flask(__name__)

    app.config.from_object(configs[config_name])

    db.init_app(app)
    app.config.from_object(Config())

    scheduler = APScheduler()
    # it is also possible to enable the API directly
    # scheduler.api_enabled = True
    scheduler.init_app(app)
    scheduler.start()

    logger_setting(app)

    @app.route('/docs')
    def docs():
        return redirect('/static/docs/index.html')

    # blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/api/auth')
    app.register_blueprint(res_callback_blueprint, url_prefix='/api/res_callback')
    app.register_blueprint(iteminfo_blueprint,url_prefix='/api/iteminfo')
    app.register_blueprint(deployment_blueprint, url_prefix='/api/deployment')
    app.register_blueprint(resources_blueprint, url_prefix='/api/resource')
    app.register_blueprint(approval_blueprint, url_prefix='/api/approval')
    app.register_blueprint(deploy_cb_blueprint, url_prefix='/api/dep_result')
    app.register_blueprint(resource_view_blueprint, url_prefix='/api/resource_view')
    app.register_blueprint(disconf_blueprint, url_prefix='/api/disconf')
    app.register_blueprint(configure_blueprint, url_prefix='/api/configure')
    app.register_blueprint(pool_blueprint, url_prefix='/api/pool')
    app.register_blueprint(perm_blueprint, url_prefix='/api/permission')

    return app
