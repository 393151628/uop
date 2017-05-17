# -*- coding: utf-8 -*-
from flask import Flask
from flask_restful import Resource, Api
from config import configs
from models import db
from uop.user import user_blueprint
from uop.item_info import iteminfo_blueprint


def create_app(config_name):
    app = Flask(__name__)

    app.config.from_object(configs[config_name])
    db.init_app(app)

    # blueprint
    app.register_blueprint(user_blueprint, url_prefix='/api/user')
    app.register_blueprint(iteminfo_blueprint,url_prefix='/api/iteminfo')
    return app
