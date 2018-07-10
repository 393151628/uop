# -*- coding: utf-8 -*-
from flask import Blueprint

open_blueprint = Blueprint('open_blueprint', __name__)

from . import handler, view