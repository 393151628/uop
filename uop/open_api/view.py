# -*- coding: utf-8 -*-


from uop.open_api import open_blueprint
from flask_restful import reqparse, Api, Resource
from uop.open_api.handler import res_deploy,get_item_id
from uop.util import response_data,get_CRP_url
from uop.models import Deployment,ResourceModel

resources_api = Api(open_blueprint)


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
        project_name = args.project_name
        env = args.env
        # tag = time.time().__str__()[2:10]
        # resource_name = "{project_name}-{env}-{tag}".format(project_name=project_name,env=env,tag=tag)
        # setattr(args, 'resource_name', resource_name)
        i_code, i_msg, cmdb2_project_id, module_id, business_id,project_name,module_name,business_name = get_item_id(project_name)
        if i_code == 200:
            setattr(args, 'cmdb2_project_id', cmdb2_project_id)
            setattr(args, 'module_id', module_id)
            setattr(args, 'business_id', business_id)
            setattr(args, 'module_name', module_name)
            setattr(args, 'business_name', business_name)
            res_deploy(args)
            data = "success"
            msg = "success"
            setattr(args, 'crp_url', crp_url)
        else:
            data = "failed"
            code = i_code
            msg = i_msg
        ret = response_data(code,msg,data)
        return ret,code


    def get(self):
        code = 200
        msg = ''
        data = {}
        pod_info = []
        parser = reqparse.RequestParser()
        parser.add_argument('deploy_name', type=str, location='json')
        parser.add_argument('resource_name', type=str, location='json')
        args = parser.parse_args()
        deploy_name = args.deploy_name
        resource_name = args.resource_name
        try:

            deploys = Deployment.objects.filter(deploy_name=deploy_name,resource_name=resource_name)
            if deploys:
                deploy = deploys[0]
                deploy_result = deploy.deploy_result
                deployment_name = deploy.resource_name
                deploy_time = deploy.created_time
                if deploy_result == "deploy_success":
                    deployment_status = "available"
                    resource_id = deploy.resource_id
                    resource = ResourceModel.objects.get(res_id=resource_id)
                    os_ins_ip_list = resource.os_ins_ip_list
                    for os_ins in os_ins_ip_list:
                        res = {}
                        res["pod_name"] = os_ins.os_ins_id
                        res["node_name"] = os_ins.physical_server
                        res["pod_ip"] = os_ins.ip
                        res["pod_status"] = "running"
                        pod_info.append(res)
                else:
                    deployment_status = "unavailable"
            else:
                deployment_status = "unavailable"
                deployment_name = ""
                deploy_time = ""
            data["deployment_name"] = deployment_name
            data["deployment_status"] = deployment_status
            data["deploy_time"] = deploy_time
            data["pod_info"] = pod_info
        except Exception as e:
            code = 500
            msg = "Get deployment info error {e}".format(e=str(e))
            data = "Error"
        ret = response_data(code, msg, data)
        return ret, code


resources_api.add_resource(ResourceOpenApi, '/resource')