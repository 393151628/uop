# -*- coding: utf-8 -*-
from flask import Blueprint

logs_blueprint = Blueprint('openapi_blueprint', __name__)

from . import handler, view