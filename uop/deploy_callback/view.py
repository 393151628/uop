# -*- coding: utf-8 -*-
import json
from flask import current_app,request
from flask_restful import reqparse, abort, Api, Resource, fields, marshal_with
from uop.deploy_callback import deploy_cb_blueprint
from uop.log import Log
from uop.deploy_callback.errors import deploy_cb_errors
from uop.deploy_callback.handler import get_deploy_status, create_status_record
from uop.models import Deployment, ResourceModel, StatusRecord
from uop.resources.handler import updata_deployment_info
from uop.util import get_CRP_url
from uop.permission.handler import api_permission_control
import requests
import datetime
import sys

reload(sys)
sys.setdefaultencoding('utf-8')

deploy_cb_api = Api(deploy_cb_blueprint, errors=deploy_cb_errors)

deploy_type_dict = {
    "deploy": "部署",
    "rollback": "回滚",
    "increase": "扩容",
    "reduce": "缩容"
}

mapping_msg_info = {
    'docker' : '容器云应用',
    'kvm' : '虚拟化云应用',
    'mysql':'mysql数据库',
    'mongodb':'mongodb数据库',
}


class DeployCallback(Resource):
    # @api_permission_control(request)
    @classmethod
    def put(cls, deploy_id):
        try:
            dep = Deployment.objects.get(deploy_id=deploy_id)
        except Exception as e:
            Log.logger.error("###Deployment error:{}".format(e.args))
            code = 500
            ret = {
                'code': code,
                'result': {
                    'res': 'fail',
                    'msg': "Deployment find error."
                }
            }
            return ret
        if not len(dep):
            code = 200
            ret = {
                'code': code,
                'result': {
                    'res': 'success',
                    'msg': "Deployment not find."
                }
            }
            return ret
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('result', type=str)
            parser.add_argument('ip', type=str)
            parser.add_argument('res_type', type=str)
            parser.add_argument('msg', type=str)
            parser.add_argument('vm_state', type=str)
            parser.add_argument('cluster_name', type=str)
            parser.add_argument('end_flag', type=bool)
            parser.add_argument('deploy_type', type=str)
            parser.add_argument('unique_flag', type=str)
            parser.add_argument('cloud', type=str)
            parser.add_argument('deploy_name', type=str)
            parser.add_argument('deploy_name', type=str)
            parser.add_argument('o_domain', type=str)
            parser.add_argument('o_port', type=str)
            parser.add_argument('domain_flag', type=str)
            parser.add_argument('war_url', type=str)
            args = parser.parse_args()
            Log.logger.info("args parser info:{}".format(args))
        except Exception as e:
            Log.logger.error("###parser error:{}".format(e.args))
            return
        dep.deploy_result = args.result
        ip = args.ip
        res_type = args.res_type
        msg = args.msg
        vm_state = args.vm_state
        cluster_name = args.cluster_name
        end_flag = args.end_flag
        deploy_type = args.deploy_type
        unique_flag = args.unique_flag
        cloud = args.cloud
        deploy_name=args.deploy_name
        o_domain = args.o_domain
        o_port = args.o_port
        domain_flag= args.domain_flag
        war_url = args.war_url
        resource_id = dep.resource_id
        status_record = StatusRecord()
        status_record.res_id = resource_id
        status_record.deploy_id = deploy_id
        status_record.s_type = "%s_%s" % (deploy_type, res_type)
        status_record.set_flag = "res"
        status_record.created_time = datetime.datetime.now()
        resource = ResourceModel.objects.get(res_id=resource_id)
        if cloud == "2":
            if dep.deploy_result == "success":
                dep.deploy_result = "%s_success" % deploy_type
                status_record.unique_flag = unique_flag
                status_record.msg = "%s %s成功\n" % (mapping_msg_info.get(res_type,res_type),deploy_type_dict.get(deploy_type,deploy_type))
            else:
                dep.deploy_result = "%s_fail" % deploy_type
                status_record.unique_flag = unique_flag
                status_record.msg ="%s %s失败,错误日志为%s\n" % (mapping_msg_info.get(res_type,res_type),deploy_type_dict.get(deploy_type,deploy_type),msg)
            status_record.save()
        else:
            if dep.deploy_result == "success":
                if res_type == "docker":
                    dep.deploy_result = "%s_docker_success" % deploy_type
                    status_record.status = "%s_docker_success" % deploy_type
                    status_record.unique_flag = unique_flag
                    status_record.msg = "%s_docker:%s %s成功，状态为%s，所属集群为%s,%s" % (
                    deploy_type, ip, deploy_type_dict.get(deploy_type,deploy_type), vm_state, cluster_name,msg)
                else:
                    dep.deploy_result = "%s_success" % deploy_type
                    status_record.unique_flag = unique_flag
                    status_record.msg = "%s %s成功" % (mapping_msg_info.get(res_type,res_type),deploy_type_dict.get(deploy_type,deploy_type))
            elif dep.deploy_result == "fail":
                if res_type == "docker":
                    dep.deploy_result = "%s_docker_fail" % deploy_type
                    status_record.status = "%s_docker_fail" % deploy_type
                    status_record.unique_flag = unique_flag
                    status_record.msg = "%s_docker:%s %s失败，状态为%s，所属集群为%s，错误日志为：%s" % (
                    deploy_type, ip, deploy_type_dict.get(deploy_type,deploy_type), vm_state, cluster_name, msg)
                else:
                    status_record.status = "deploy_%s_fail" % res_type
                    status_record.msg = "deploy_%s:部署失败，错误日志为：%s" % (res_type, msg)
                    status_record.unique_flag = unique_flag
            status_record.save()
            res_status, count = get_deploy_status(deploy_id, deploy_type, res_type,unique_flag)
            if res_status == True and end_flag == True:
                dep.deploy_result = "%s_success" % deploy_type
                create_status_record(resource_id, deploy_id, deploy_type, "%s成功\n" % deploy_type_dict.get(deploy_type,deploy_type),
                                     "%s_success" % deploy_type, "res")

            elif res_status == False and end_flag == True:
                dep.deploy_result = "%s_fail" % deploy_type
                create_status_record(resource_id, deploy_id, deploy_type, "%s失败\n" % deploy_type_dict.get(deploy_type,deploy_type),
                                     "%s_fail" % deploy_type, "res")
        # 如果回滚成功，修改部署版本
        if  args.result == "success" and deploy_type == "rollback":
            resource.deploy_name = deploy_name
        # 如果部署失败修改domain和port
        if dep.deploy_result == "deploy_fail" and domain_flag == "True" :
            compute_list = resource.compute_list
            for compute in compute_list:
                compute.domain = o_domain
                compute.port = o_port
        #如果k8s应用部署成功，修改resource和statusvm表
        if cloud == "2" and args.result == "success" and res_type in ["docker","kvm"]:
            resource_name = dep.resource_name
            env = dep.environment
            url = get_CRP_url(env)
            updata_deployment_info(resource_name,env,url)
        if deploy_type == "deploy" and args.result == "success" and  war_url:
            new_app_image = []
            compute_list = resource.compute_list
            app_image = eval(dep.app_image)
            for app in app_image:
                app["git_res_url"] = war_url
                new_app_image.append(app)
                dep.app_image = str(new_app_image)
            for compute in compute_list:
                compute.git_res_url = war_url
        resource.save()
        dep.save()
        try:
            p_code = ResourceModel.objects.get(res_id=resource_id).cmdb_p_code
            # 修改cmdb部署状态信息
            CMDB_URL = current_app.config['CMDB_URL']
            if CMDB_URL:
                deployment_url = CMDB_URL + "cmdb/api/repo/%s/" % p_code
                Log.logger.info('deploy status: {}, {}'.format(dep.deploy_result, p_code))
                data = {
                    'property_list': [
                        {
                            "type": "string",
                            "name": "部署状态",
                            "value": dep.deploy_result
                        }
                    ]
                }
                req = requests.put(deployment_url, data=json.dumps(data))
        except Exception as e:
            code = 500
            ret = {
                'code': code,
                'result': {
                    'res': 'failed',
                    'msg': "Deployment update failed."
                }
            }
            return ret

        code = 200
        ret = {
            'code': code,
            'result': {
                'res': 'success',
                'msg': "Deployment update success."
            }
        }
        return ret, code


class DeployStatusProviderCallBack(Resource):
    # @api_permission_control(request)
    @classmethod
    def post(cls):
        try:
            code = 200
            parser = reqparse.RequestParser()
            parser.add_argument('deploy_msg', type=str)
            parser.add_argument('deploy_id', type=str)
            parser.add_argument('deploy_type', type=str)
            parser.add_argument('set_flag', type=str)
            args = parser.parse_args()
            deploy_id = args.deploy_id
            deploy_type = args.deploy_type
            deploy_msg = args.deploy_msg
            set_flag = args.set_flag
            dep = Deployment.objects.get(deploy_id=deploy_id)
            if dep:
                resource_id = dep.resource_id
                status_record = StatusRecord()
                status_record.deploy_id = deploy_id
                status_record.s_type = deploy_type
                status_record.res_id = resource_id
                status_record.set_flag = set_flag
                status_record.status = '%s_success' % (deploy_type)
                status_record.msg = '%s部署完成' % (deploy_type)
                if deploy_msg:
                    status_record.msg = '%s' % (deploy_msg)
                status_record.created_time = datetime.datetime.now()
                status_record.save()
                if deploy_type in ["increase", "reduce"]:
                    dep.deploy_result = status_record.status
                    dep.save()
            else:
                ret = {
                    "code": code,
                    "result": {
                        "res": 'success',
                        "msg": "Deployment not find."
                    }
                }
                return ret, code
        except Exception as e:
            Log.logger.error("[UOP] Deploy Status callback failed, Excepton: %s" % str(e.args))
            code = 500
            ret = {
                'code': code,
                'result': {
                    'res': 'fail',
                    'msg': "Deploy find error."
                }
            }
            return ret, code

        res = {
            "code": code,
            "result": {
                "res": "success",
                "msg": "deploy info save success"
            }
        }
        return res, code

    # @api_permission_control(request)
    @classmethod
    def get(cls):
        code = 200
        parser = reqparse.RequestParser()
        parser.add_argument('deploy_id', location='args')
        parser.add_argument('res_id', location='args')
        args = parser.parse_args()
        deploy_id = args.deploy_id
        resource_id = args.res_id
        try:
            data = {}
            dep_msg_list = []
            dep_status_records = StatusRecord.objects.filter(deploy_id=deploy_id).order_by('created_time')
            if dep_status_records:
                for sr in dep_status_records:
                    s_msg = sr.created_time.strftime('%Y-%m-%d %H:%M:%S') + ':' + sr.msg
                    dep_msg_list.append(s_msg)
            data["deploy"] = dep_msg_list
        except Exception as e:
            Log.logger.error("[UOP] Get deploy  callback msg failed, Excepton: %s" % str(e.args))
            code = 500
            ret = {
                'code': code,
                'result': {
                    'res': 'fail',
                    'msg': "Deploy find error.",
                    'data': data,
                }
            }
            return ret, code

        res = {
            "code": code,
            "result": {
                "res": "success",
                "msg": "get msg success",
                'data': data,
            }
        }
        return res, code



deploy_cb_api.add_resource(DeployCallback, '/<string:deploy_id>/')
deploy_cb_api.add_resource(DeployStatusProviderCallBack, '/status')
