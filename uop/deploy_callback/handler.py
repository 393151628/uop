# -*- coding: utf-8 -*-
import json
from flask import request, current_app
from flask import redirect
from flask import jsonify
import uuid
import logging
from flask_restful import reqparse, abort, Api, Resource, fields, marshal_with
from uop.deploy_callback import deploy_cb_blueprint
from uop.deploy_callback.errors import deploy_cb_errors
from uop.models import Deployment, ResourceModel,StatusRecord
import requests
import datetime
import sys
reload(sys)
sys.setdefaultencoding('utf-8')


deploy_cb_api = Api(deploy_cb_blueprint, errors=deploy_cb_errors)



class DeployCallback(Resource):
    @classmethod
    def put(cls, deploy_id):
        try:
            dep = Deployment.objects.get(deploy_id=deploy_id)
        except Exception as e:
            logging.error("###Deployment error:{}".format(e.args))
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
            parser.add_argument('err_msg', type=str)
            parser.add_argument('vm_state', type=str)
            parser.add_argument('cluster_name', type=str)
            parser.add_argument('end_flag', type=bool)
            args = parser.parse_args()
        except Exception as e:
            logging.error("###parser error:{}".format(e.args))
            return
        dep.deploy_result = args.result
        ip=args.ip
        res_type=args.res_type
        err_msg = args.err_msg
        vm_state=args.vm_state
        cluster_name = args.cluster_name
        end_flag = args.end_flag
        resource_id = dep.resource_id
        status_record = StatusRecord()
        status_record.res_id = resource_id
        status_record.deploy_id = deploy_id
        status_record.s_type="deploy_docker"
        status_record.created_time=datetime.datetime.now()
        if dep.deploy_result == "success":
            dep.deploy_result="deploy_docker_success"
            status_record.status="deploy_docker_success"
            status_record.msg="deploy_docker:%s部署成功，状态为%s，所属集群为%s,健康检查状态为UP" % (ip,vm_state,cluster_name)
        elif dep.deploy_result == "fail":
            if res_type == "docker":
                dep.deploy_result="deploy_docker_fail"
                status_record.status="deploy_docker_fail"
                status_record.msg="deploy_docker:%s部署失败，状态为%s，所属集群为%s，错误日志为：%s" % (ip,vm_state,cluster_name,err_msg)
            elif res_type == "mongodb":
                dep.deploy_result = "deploy_mongodb_fail"
                status_record.status = "deploy_mongodb_fail"
                status_record.msg = "deploy_mongodb:部署失败，错误日志为：%s" % err_msg
            elif res_type == "mysql":
                dep.deploy_result = "deploy_mysql_fail"
                status_record.status = "deploy_mysql_fail"
                status_record.msg = "deploy_mysql:部署失败，错误日志为：%s" % err_msg
        status_record.save()
        res_status,count = get_deploy_status(deploy_id)
        #if not res_status and quantity == count:
        #    dep.deploy_result = "deploy_fail"
        #    create_status_record(resource_id,deploy_id,"deploy","部署失败","deploy_fail")
        if res_status == True and end_flag == True:
            dep.deploy_result = "deploy_success"
            create_status_record(resource_id,deploy_id,"deploy","部署成功","deploy_success")
        elif res_status == False and end_flag == True:
            dep.deploy_result = "deploy_fail"
            create_status_record(resource_id, deploy_id, "deploy", "部署失败", "deploy_fail")
        dep.save()


            
        try:
            p_code = ResourceModel.objects.get(res_id=resource_id).cmdb_p_code
            # 修改cmdb部署状态信息
            CMDB_URL = current_app.config['CMDB_URL']
            deployment_url = CMDB_URL + "cmdb/api/repo/%s/"  % p_code
            logging.info('deploy status: {}, {}'.format(dep.deploy_result, p_code))
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
        return ret


class DeployStatusProviderCallBack(Resource):
    @classmethod
    def post(cls):
        try:
            code = 2002
            parser = reqparse.RequestParser()
            parser.add_argument('deploy_msg', type=bool, location='json')
            parser.add_argument('deploy_id', type=str)
            parser.add_argument('deploy_type', type=str)
            args = parser.parse_args()
            deploy_id = args.deploy_id
            deploy_type = args.deploy_type
            deploy_msg = args.deploy_msg
            dep = Deployment.objects.get(deploy_id=deploy_id)
            if dep:
                resource_id=dep.resource_id
                status_record = StatusRecord()
                status_record.deploy_id = deploy_id
                status_record.s_type=deploy_type
                status_record.res_id = resource_id
                status_record.status = '%s_success'%(deploy_type)
                status_record.msg='%s部署完成'%(deploy_type)
                if deploy_msg:
                    status_record.msg = '%s%s' % (deploy_type,deploy_msg)
                status_record.created_time=datetime.datetime.now()
                status_record.save()
                dep.deploy_result=status_record.status
                dep.save()
            else:
                ret = {
                    "code": code,
                    "result": {
                        "res": 'success',
                        "msg": "Deployment not find."
                        }
                    }
                return ret,code 
        except Exception as e:
            logging.exception("[UOP] Deploy Status callback failed, Excepton: %s", e.args)
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
        return res, 200
    @classmethod
    def get(cls):
        code = 2002
        parser = reqparse.RequestParser()
        parser.add_argument('deploy_id',location='args')
        parser.add_argument('res_id', location='args')
        args = parser.parse_args()
        deploy_id=args.deploy_id
        resource_id = args.res_id
        try:
            data={}
            dep_msg_list=[]
            dep_status_records = StatusRecord.objects.filter(deploy_id=deploy_id).order_by('created_time')
            set_status_records = StatusRecord.objects.filter(res_id=resource_id,set_flag="increate").order_by('created_time')
            del_status_records = StatusRecord.objects.filter(res_id=resource_id, set_flag="reduce").order_by('created_time')
            if set_status_records:
                for sr in set_status_records:
                    s_msg=sr.created_time.strftime('%Y-%m-%d %H:%M:%S') +':'+ sr.msg
                    dep_msg_list.append(s_msg)
            if del_status_records:
                for sr in del_status_records:
                    s_msg=sr.created_time.strftime('%Y-%m-%d %H:%M:%S') +':'+ sr.msg
                    dep_msg_list.append(s_msg)
            if dep_status_records:
                for sr in dep_status_records:
                    s_msg=sr.created_time.strftime('%Y-%m-%d %H:%M:%S') +':'+ sr.msg
                    dep_msg_list.append(s_msg)
            data["deploy"]=dep_msg_list
        except Exception as e:
            logging.exception("[UOP] Get deploy  callback msg failed, Excepton: %s", e.args)
            code = 500
            ret = {
                'code': code,
                'result': {
                    'res': 'fail',
                    'msg': "Deploy find error.",
                    'data':data,
                }
            }
            return ret, code

        res = {
            "code": code,
            "result": {
                "res": "success",
                "msg": "get msg success",
                'data':data,
            }
        }
        return res, 200   

def get_deploy_status(deploy_id): 
    try:
        docker_status_list=[]
        status_records = StatusRecord.objects.filter(deploy_id=deploy_id).order_by('created_time')
        for sr in status_records:
            if sr.s_type=="deploy_docker":
                docker_status_list.append(sr.status)
        if "deploy_docker_fail" in docker_status_list or "deploy_mongodb_fail" in docker_status_list or "deploy_mysql_fail" in docker_status_list:
            return False,len(docker_status_list)
        else:
            return True,len(docker_status_list) 
    except Exception as e:
        logging.exception("[UOP] get_deploy_status failed, Excepton: %s", e.args)
     
def create_status_record(resource_id,deploy_id,s_type,msg,status):
    try:
        status_record = StatusRecord()
        status_record.res_id = resource_id
        status_record.deploy_id = deploy_id
        status_record.s_type=s_type
        status_record.created_time=datetime.datetime.now()
        status_record.msg=msg
        status_record.status=status
        status_record.save()
    except Exception as e:
        logging.exception("[UOP] create_status_record failed, Excepton: %s", e.args)
        


deploy_cb_api.add_resource(DeployCallback, '/<string:deploy_id>/')
deploy_cb_api.add_resource(DeployStatusProviderCallBack, '/status')
