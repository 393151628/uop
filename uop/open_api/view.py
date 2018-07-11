# -*- coding: utf-8 -*-


from uop.open_api import open_blueprint
from flask_restful import reqparse, Api, Resource
from uop.open_api.handler import res_deploy

resources_api = Api(open_blueprint)
from uop.util import response_data,get_CRP_url

class ResourceOpenApi(Resource):

    def post(self):
        code = 200
        parser = reqparse.RequestParser()
        parser.add_argument('resource_name', type=str)
        parser.add_argument('project_name', type=str)
        parser.add_argument('module_name', type=str)
        parser.add_argument('business_name', type=str)
        parser.add_argument('cmdb2_project_id', type=str)
        parser.add_argument('cmdb2_module_id', type=str)
        parser.add_argument('department', type=str)
        parser.add_argument('user_name', type=str)
        parser.add_argument('user_id', type=str)
        parser.add_argument('env', type=str)
        parser.add_argument('formStatus', type=str)
        parser.add_argument('approval_status', type=str)
        parser.add_argument('resource_list', type=list, location='json')
        parser.add_argument('compute_list', type=list, location='json')
        parser.add_argument('cloud', type=str)
        parser.add_argument('resource_type', type=str)
        parser.add_argument('domain', type=str)

        parser.add_argument('lb_methods', type=str)
        parser.add_argument('namespace', type=str)
        parser.add_argument('host_mapping', type=list, location='json')
        parser.add_argument('network_id', type=str)
        parser.add_argument('scheduler_zone', type=str)
        parser.add_argument('agree', type=bool, default=True)
        parser.add_argument('annotations', type=str,default="")

        parser.add_argument('action', type=str,location='json',default="admin_approve_allow" )
        parser.add_argument('deploy_name', type=str, required=True,location='json')
        parser.add_argument('initiator', type=str, location='json',default="")
        parser.add_argument('release_notes', type=str, location='json',default="")
        parser.add_argument('mysql_exe_mode', type=str, location='json',default="")
        parser.add_argument('mysql_context', type=str, location='json',default="")
        parser.add_argument('redis_exe_mode', type=str, location='json',default="")
        parser.add_argument('redis_context', type=str, location='json',default="")
        parser.add_argument('mongodb_exe_mode', type=str, location='json',default="")
        parser.add_argument('mongodb_context', type=str, location='json',default="")
        parser.add_argument('approve_suggestion', type=str, location='json',default="")
        parser.add_argument('apply_status', type=str, location='json',default="success")
        parser.add_argument('approve_status', type=str, location='json',default="success")
        parser.add_argument('disconf', type=list, location='json',default=[])
        parser.add_argument('database_password', type=str, location='json',default="")
        parser.add_argument('domain_ip', type=str, location='json', default="")
        parser.add_argument('certificate', type=str, location='json', default="")
        parser.add_argument('named_url', type=str, location='json', default="")
        args = parser.parse_args()
        crp_url = get_CRP_url(args.env)
        setattr(args, 'crp_url', crp_url)
        res_deploy(args)
        data = "success"
        msg = "success"
        ret = response_data(code,msg,data)
        return ret,code








































resources_api.add_resource(ResourceOpenApi, '/resource')