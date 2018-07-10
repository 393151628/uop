# -*- coding: utf-8 -*-


from uop.open_api import open_blueprint
from flask_restful import reqparse, Api, Resource

resources_api = Api(open_blueprint)

class ResourceOpenApi(Resource):

    def post(self):
        pass








































resources_api.add_resource(ResourceOpenApi, '/')