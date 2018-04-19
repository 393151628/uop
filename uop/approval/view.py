# -*- coding: utf-8 -*-

import json

import uuid
import datetime
import requests
import random
from flask import request
from flask import current_app
from flask_restful import reqparse, Api, Resource
from uop.log import Log
from uop.approval import approval_blueprint
from uop import models
from uop.approval.errors import approval_errors
from uop.util import get_CRP_url
from config import configs, APP_ENV
from uop.permission.handler import api_permission_control
from uop.deployment.handler import attach_domain_ip,deploy_to_crp,deal_disconf_info
from uop.approval.handler import resource_reduce,deal_crp_data

approval_api = Api(approval_blueprint, errors=approval_errors)


# CPR_URL = current_app.config['CRP_URL']
# CPR_URL = configs[APP_ENV].CRP_URL
BASE_K8S_IMAGE = configs[APP_ENV].BASE_K8S_IMAGE
K8S_NGINX_PORT = configs[APP_ENV].K8S_NGINX_PORT
K8S_NGINX_IPS = configs[APP_ENV].K8S_NGINX_IPS


class ApprovalList(Resource):

    #@api_permission_control(request)
    def post(self):
        code = 200
        res = ""
        msg = {}
        try:
            parser = reqparse.RequestParser()

            parser.add_argument('resource_id', type=str)
            parser.add_argument('project_id', type=str)
            parser.add_argument('department', type=str)
            parser.add_argument('user_id', type=str)
            parser.add_argument('approval_info_list', type=list,location ="json")
            args = parser.parse_args()

            approval_info_list = args.approval_info_list
            for info in approval_info_list:
                approval_id = str(uuid.uuid1())
                resource_id = info.get("resource_id","")
                project_id = info.get("project_id","")
                department = info.get("department","")
                user_id = info.get("user_id","")
                create_date = datetime.datetime.now()
                # approve_uid
                # approve_date
                # annotations
                approval_status = "processing"
                models.Approval(approval_id=approval_id, resource_id=resource_id,
                                project_id=project_id, department=department,
                                user_id=user_id, create_date=create_date,
                                approval_status=approval_status).save()

                resource = models.ResourceModel.objects.get(res_id=resource_id)
                resource.approval_status = "processing"
                resource.save()
                code = 200
        except Exception as e:
            Log.logger.exception("[UOP] ApprovalList failed, Exception: %s", e.args)
            code = 500
            res = "Failed to add a approval"

        finally:
            ret = {
                "code": code,
                "result": {
                    "res": res,
                    "msg": msg
                }
            }

        return ret, code


class ApprovalInfo(Resource):

    #@api_permission_control(request)
    def put(self, res_id):
        code = 200
        res = ""
        msg = {}
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('approve_uid', type=str)
            parser.add_argument('agree', type=bool)
            parser.add_argument('annotations', type=str)
            parser.add_argument('docker_network_id', type=str)
            parser.add_argument('mysql_network_id', type=str)
            parser.add_argument('redis_network_id', type=str)
            parser.add_argument('mongodb_network_id', type=str)
            parser.add_argument('network_id', type=str)
            parser.add_argument('networkName', type=str)
            parser.add_argument('tenantName', type=str)
            parser.add_argument('lb_methods', type=str)
            parser.add_argument('namespace', type=str)
            parser.add_argument('host_mapping', type=list,location='json')
            args = parser.parse_args()

            docker_network_id = args.docker_network_id
            mysql_network_id = args.mysql_network_id
            redis_network_id = args.redis_network_id
            mongodb_network_id = args.mongodb_network_id
            networkName = args.networkName
            tenantName = args.tenantName
            lb_methods = args.lb_methods
            namespace = args.namespace
            host_mapping = args.host_mapping
            network_id = args.network_id
            if host_mapping is not None:
                host_mapping=json.dumps(host_mapping)
            network_id_dict={
                "docker":docker_network_id,
                "mysql":mysql_network_id,
                "redis":redis_network_id,
                "mongodb":mongodb_network_id
            }

            approvals = models.Approval.objects.filter(capacity_status="res",resource_id=res_id).order_by("-create_date")
            resource = models.ResourceModel.objects.get(res_id=res_id)
            resource_list = resource.resource_list
            compute_list = resource.compute_list
            if approvals:
                approval=approvals[0]
                approval.approve_uid = args.approve_uid
                approval.approve_date = datetime.datetime.now()
                approval.annotations = args.annotations

                if args.agree:
                    approval.approval_status = "success"
                    resource.approval_status = "success"
                else:
                    approval.approval_status = "failed"
                    resource.approval_status = "failed"
                    resource.reservation_status = "approval_fail"
                approval.save()
                if docker_network_id:
                    resource.docker_network_id = docker_network_id.strip()
                if mysql_network_id:
                    resource.mysql_network_id = mysql_network_id.strip()
                if redis_network_id:
                    resource.redis_network_id = redis_network_id.strip()
                if mongodb_network_id:
                    resource.mongodb_network_id = mongodb_network_id.strip()

                if compute_list:
                    for com in compute_list:
                        com.network_id = docker_network_id
                        com.networkName = networkName
                        com.tenantName = tenantName
                        com.lb_methods = lb_methods
                        com.namespace = namespace
                        com.host_mapping = host_mapping
                if resource_list:
                    for res_obj in resource_list:
                        if network_id:
                            res_obj.network_id = network_id
                        else:
                            res_obj.network_id = network_id_dict.get(res_obj.ins_type)
                resource.save()
                code = 200
            else:
                code = 410
                res = "A resource with that ID no longer exists"
        except Exception as e:
            code = 500
            res = "Failed to approve the resource. %s" %str(e)
        finally:
            ret = {
                "code": code,
                "result": {
                    "res": res,
                    "msg": msg
                }
            }

        return ret, code

    #@api_permission_control(request)
    def get(self, res_id):
        code = 200
        res = ""
        msg = {}
        try:
            approval = models.Approval.filter(capacity_status="res").objects.get(resource_id=res_id)

            if approval:
                msg["creator_id"] = approval.creator_id
                msg["create_date"] = str(approval.create_date)
                status = approval.approval_status
                msg["approval_status"] = status
                if status == "success" or status == "failed":
                    msg["approve_uid"] = approval.approve_uid
                    msg["approve_date"] = str(approval.approve_date)
                    msg["annotations"] = approval.annotations
                code = 200
            else:
                code = 410
                res = "A resource with that ID no longer exists"
        except Exception as e:
            code = 500
        finally:
            ret = {
                "code": code,
                "result": {
                    "res": res,
                    "msg": msg
                }
            }

        return ret, code


class Reservation(Resource):
    """
    预留审批
    """

    #@api_permission_control(request)
    def post(self):
        """
        预留审批通过，往crp发送数据
        :return:
        """
        code = 200
        res = ""
        msg = {}
        parser = reqparse.RequestParser()
        parser.add_argument('resource_id', type=str)
        parser.add_argument('compute_list', type=list, location='json')
        args = parser.parse_args()
        resource_id = args.resource_id
        try:
            resource = models.ResourceModel.objects.get(res_id=resource_id)
        except Exception as e:
            Log.logger.error(str(e))
            code = 410
            res = "Failed to find the rsource"
            ret = {
                "code": code,
                "result": {
                    "res": res,
                    "msg": msg
                }
            }
            return ret, code
        set_flag = "res"
        data = deal_crp_data(resource,set_flag)
        Log.logger.info("Data args is %s",data)
        data_str = json.dumps(data)
        headers = {'Content-Type': 'application/json'}
        try:
            CPR_URL = get_CRP_url(data['env'])
            msg = requests.post(CPR_URL + "api/resource/sets", data=data_str, headers=headers)
        except Exception as e:
            res = "failed to connect CRP service."
            code = 500
            ret = {
                "code": code,
                "result": {
                    "res": res
                }
            }
            return ret, code
        if msg.status_code != 202:
            code = msg.status_code
            res = "Failed to reserve resource."
        else:
            resource.reservation_status = "reserving"
            resource.save()
            code = 200
            res = "Success in reserving resource."
        ret = {
            "code": code,
            "result": {
                "res": res
            }
        }
        return ret, code


    def put(self):
        """
        其他资源编辑审批通过，往crp发送数据
        :return:
        """
        code = 200
        res = ""
        msg = {}
        parser = reqparse.RequestParser()
        parser.add_argument('resource_id', type=str)
        args = parser.parse_args()
        resource_id = args.resource_id
        try:
            resource = models.ResourceModel.objects.get(res_id=resource_id)
        except Exception as e:
            Log.logger.error(str(e))
            code = 410
            res = "Failed to find the rsource"
            ret = {
                "code": code,
                "result": {
                    "res": res,
                    "msg": msg
                }
            }
            return ret, code
        #其他资源的修改
        vid_list = resource.vid_list
        number = vid_list.__str__()
        try:
            if number > 0:
                #对已经预留好的资源进程修改
                resource_list = resource.resource_list
                for res in resource_list:
                    quantity = res.quantity
                if number < quantity: #扩容
                    quantity = quantity - number
                    set_flag = "increase"
                    data=deal_crp_data(resource,set_flag,quantity)
                    data_str = json.dumps(data)
                    CPR_URL = get_CRP_url(data['env'])
                    headers = {'Content-Type': 'application/json'}
                    msg = requests.post(CPR_URL + "api/resource/sets", data=data_str, headers=headers)
                elif number > quantity: #缩容
                    ips=[]
                    quantity = number - quantity
                    for os_ins in resource.os_ins_ip_list:
                        ip = os_ins.ip
                        ips.append(ip)
                    msg=resource_reduce(resource,quantity,ips)
                else:#既不扩容也不缩容
                    set_flag = "res"
                    quantity = "0"
                    data = deal_crp_data(resource, set_flag, quantity)
                    data_str = json.dumps(data)
                    CPR_URL = get_CRP_url(data['env'])
                    headers = {'Content-Type': 'application/json'}
                    msg = requests.post(CPR_URL + "api/resource/sets", data=data_str, headers=headers)
        except Exception as e:
            res = "UOP put resource failed.{}".format(str(e))
            code = 500
            ret = {
                "code": code,
                "result": {
                    "res": res
                }
            }
            return ret, code
        if msg.status_code != 202:
            code = msg.status_code
            res = "Failed to reserve resource."
        else:
            resource.reservation_status = "reserving"
            resource.save()
            code = 200
            res = "Success in reserving resource."
        ret = {
            "code": code,
            "result": {
                "res": res
            }
        }
        return ret, code



class ReservationAPI(Resource):
    """
    预留失败时，重新预留往crp发送数据
    """

    #@api_permission_control(request)
    def put(self, res_id):
        code =200
        res = ""
        msg = {}
        try:
            resource = models.ResourceModel.objects.get(res_id=res_id)
        except Exception as e:
            code = 410
            res = "Failed to find the rsource"
            ret = {
                "code": code,
                "result": {
                    "res": res,
                    "msg": msg
                }
            }
            return ret, code
        set_flag = "res"
        data = deal_crp_data(resource,set_flag)
        data_str = json.dumps(data)
        headers = {'Content-Type': 'application/json'}
        try:
            CPR_URL = get_CRP_url(data['env'])
            msg = requests.post(CPR_URL + "api/resource/sets", data=data_str, headers=headers)
        except Exception as e:
            res = "failed to connect CRP service."
            code = 500
            ret = {
                "code": code,
                "result": {
                    "res": res
                }
            }
            return ret, code
        if msg.status_code != 202:
            resource.reservation_status = "unreserved"
            resource.save()
            code = msg.status_code
            res = "Failed to reserve resource."
        else:
            resource.reservation_status = "reserving"
            resource.save()
            code = 200
            res = "Success in reserving resource."
        ret = {
            "code": code,
            "result": {
                "res": res
            }
        }
        return ret, code



class CapacityInfoAPI(Resource):
    #@api_permission_control(request)
    def put(self):
        code = 0
        res = ""
        msg = {}
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('approval_id', type=str)
            parser.add_argument('approve_uid', type=str)
            parser.add_argument('agree', type=bool)
            parser.add_argument('approve_suggestion', type=str)
            parser.add_argument('docker_network_id', type=str)
            args = parser.parse_args()
            approval_id = args.approval_id
            approval = models.Approval.objects.get(approval_id=approval_id)
            deployment = models.Deployment.objects.get(deploy_id=approval_id)
            deployment.approve_suggestion = args.approve_suggestion
            # deploy_name=deployment.deploy_name
            if approval:
                approval.approve_uid = args.approve_uid
                approval.approve_date = datetime.datetime.now()
                approval.annotations = args.approve_suggestion
                docker_network_id = args.docker_network_id
                #更新nova docker 的network_id
                resource = models.ResourceModel.objects.get(res_id=approval.resource_id)
                # resource.deploy_name = deploy_name
                compute_list = resource.compute_list
                if compute_list:
                    for com in compute_list:
                        com.network_id = docker_network_id
                        com.save()
                resource.save()
                if args.agree:
                    approval.approval_status = "%s_success" % (approval.capacity_status)
                    compute_list = resource.compute_list
                    for compute_ in compute_list:
                        capacity_list = compute_.capacity_list
                        for capacity_ in capacity_list:
                            if capacity_.capacity_id == approval_id:
                                capacity_.network_id = docker_network_id.strip()
                    deployment.approve_status = "%s_success" % (approval.capacity_status)
                    if approval.capacity_status == "increase":
                        deployment.deploy_result = "increasing"
                    elif approval.capacity_status == "reduce":
                        deployment.deploy_result = "reducing"
                    # 管理员审批通过后修改resource表deploy_name,更新当前版本
                    deploy_name = deployment.deploy_name
                    resource = models.ResourceModel.objects.get(res_id=approval.resource_id)
                    resource.deploy_name = deploy_name
                    resource.save()
                else:
                    approval.approval_status = "%s_failed" % (approval.capacity_status)
                    deployment.approve_status = "%s_failed" % (approval.capacity_status)
                    if approval.capacity_status == "increase":
                        deployment.deploy_result = "not_increased"
                    elif approval.capacity_status == "reduce":
                        deployment.deploy_result = "not_reduced"
                approval.save()
                deployment.save()
                code = 200
            else:
                code = 410
                res = "A resource with that ID no longer exists"
        except Exception as e:
            code = 500
            res = "Failed to approve the resource."
        finally:
            ret = {
                "code": code,
                "result": {
                    "res": res,
                    "msg": msg
                }
            }

        return ret, code


class CapacityReservation(Resource):

    #@api_permission_control(request)
    def post(self):
        code = 200
        res = ""
        msg = {}
        parser = reqparse.RequestParser()
        parser.add_argument('resource_id', type=str)
        parser.add_argument('approval_id', type=str)
        parser.add_argument('compute_list', type=list, location='json')
        args = parser.parse_args()
        resource_id = args.resource_id
        approval_id = args.approval_id
        try:
            resource = models.ResourceModel.objects.get(res_id=resource_id)
            #item_info = models.ItemInformation.objects.get(item_name=resource.project)
            approval = models.Approval.objects.get(approval_id=approval_id)
        except Exception as e:
            Log.logger.error(str(e))
            code = 410
            res = "Failed to find the rsource"
            ret = {
                "code": code,
                "result": {
                    "res": res,
                    "msg": msg
                }
            }
            return ret, code

        data = dict()
        data['unit_id'] = resource.project_id
        # data['network_id'] = resource.network_id.strip()
        data['unit_name'] = resource.project
        data['unit_des'] = ''
        data['user_id'] = resource.user_id
        data['username'] = resource.user_name
        data['department'] = resource.department
        data['created_time'] = str(resource.created_date)
        data['resource_id'] = resource.res_id
        data['resource_name'] = resource.resource_name
        data['domain'] = resource.domain
        data['project_id'] = resource.cmdb2_project_id
        data['module_id'] = resource.cmdb2_module_id
        data['department_id'] = resource.department_id
        data['env'] = resource.env
        data['docker_network_id'] = resource.docker_network_id
        data['mysql_network_id'] = resource.mysql_network_id
        data['redis_network_id'] = resource.redis_network_id
        data['mongodb_network_id'] = resource.mongodb_network_id
        data['cmdb_repo_id'] = resource.cmdb_p_code
        data['cloud'] = resource.cloud
        data['resource_type'] = resource.resource_type
        data['set_flag'] = approval.capacity_status
        data['syswin_project'] = 'uop'
        data['project_name'] = resource.project_name
        resource_list = resource.resource_list
        compute_list = resource.compute_list
        resource_type = resource.resource_type
        number = 0
        if resource_list:
            res = []
            for db_res in resource_list:
                res.append(
                    {
                        "instance_name": db_res.ins_name,
                        "instance_id": db_res.ins_id,
                        "instance_type": db_res.ins_type,
                        "cpu": db_res.cpu,
                        "mem": db_res.mem,
                        "disk": db_res.disk,
                        "quantity": 0,
                        "version": db_res.version,
                        "volume_size": db_res.volume_size,
                        "image_id": db_res.image_id,
                        "network_id": db_res.network_id,
                        "flavor": db_res.flavor_id,
                    }
                )
            data['resource_list'] = res
        ips = []
        if compute_list:
            com = []
            for db_com in compute_list:
                # for i in range(0, db_com.quantity):
                meta = json.dumps(db_com.docker_meta) if db_com.docker_meta else ""
                deploy_source = db_com.deploy_source
                host_env = db_com.host_env
                url = db_com.url
                ready_probe_path = db_com.ready_probe_path
                if host_env == "docker" and deploy_source == "image" and  not ready_probe_path:
                    url = BASE_K8S_IMAGE
                capacity_list = db_com.capacity_list
                for capacity_ in capacity_list:
                    if capacity_.capacity_id == approval_id:
                        if resource.cloud == "2" and resource_type == "app":
                            number = capacity_.end_number
                        else:
                            number = abs(capacity_.begin_number - capacity_.end_number)
                        com.append(
                            {
                                "instance_name": db_com.ins_name,
                                "instance_id": db_com.ins_id,
                                "cpu": db_com.cpu,
                                "mem": db_com.mem,
                                "image_url": url,
                                "quantity": number,
                                "domain": db_com.domain,
                                "port": db_com.port,
                                "domain_ip": db_com.domain_ip,
                                "meta": meta,
                                "health_check": db_com.health_check,
                                "network_id": db_com.network_id,
                                "networkName": db_com.networkName,
                                "tenantName": db_com.tenantName,
                                "host_env":db_com.host_env,
                                "language_env": db_com.language_env,
                                "deploy_source": db_com.deploy_source,
                                "database_config": db_com.database_config,
                                "lb_methods": db_com.lb_methods,
                                "namespace": db_com.namespace,
                                "ready_probe_path": db_com.ready_probe_path,
                                "domain_path": db_com.domain_path,
                                "host_mapping":db_com.host_mapping,
                            })
                        ips.extend([ip for ip in db_com.ips])

            data['compute_list'] = com

        data_str = json.dumps(data)
        headers = {'Content-Type': 'application/json'}
        try:
            cloud = resource.cloud
            if cloud == '2' and resource_type == "app":
                CPR_URL = get_CRP_url(data['env'])
                msg = requests.post(CPR_URL + "api/resource/sets", data=data_str, headers=headers)
            else:
                if approval.capacity_status == 'increase':
                    CPR_URL = get_CRP_url(data['env'])
                    msg = requests.post(CPR_URL + "api/resource/sets", data=data_str, headers=headers)
                elif approval.capacity_status == 'reduce':
                    msg=resource_reduce(resource,number,ips)
                    # reduce_list = []
                    # for os_ins in resource.os_ins_ip_list:
                    #     if os_ins.ip in ips:
                    #         reduce_list.append(os_ins)
                    # reduce_list = random.sample(reduce_list, number)
                    # os_inst_id_list = []
                    # reduce_list = [eval(reduce_.to_json()) for reduce_ in reduce_list]
                    # for os_ip_dict in reduce_list:
                    #     os_inst_id = os_ip_dict["os_ins_id"]
                    #     os_inst_id_list.append(os_inst_id)
                    # crp_data = {
                    #     "resource_id": resource.res_id,
                    #     "resource_name": resource_name,
                    #     "os_ins_ip_list": reduce_list,
                    #     "resource_type": resource_type,
                    #     "cloud": cloud,
                    #     "set_flag": 'reduce',
                    #     'syswin_project': 'uop'
                    # }
                    # env_ = get_CRP_url(resource.env)
                    # crp_url = '%s%s' % (env_, 'api/resource/deletes')
                    # crp_data = json.dumps(crp_data)
                    # msg = requests.delete(crp_url, data=crp_data)
        except Exception as e:
            res = "failed to connect CRP service."
            code = 500
            ret = {
                "code": code,
                "result": {
                    "res": res
                }
            }
            return ret, code
        if msg.status_code != 202:
            code = msg.status_code
            res = "Failed to reserve resource."
        else:
            resource.reservation_status = "reserving"
            resource.save()
            code = 200
            res = "Success in reserving resource."
        ret = {
            "code": code,
            "result": {
                "res": res
            }
        }
        return ret, code


class RollBackInfoAPI(Resource):

    # 审批过后更新审批表的信息
    #@api_permission_control(request)
    def put(self):
        code = 200
        res = ""
        msg = {}
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('deploy_id', type=str)
            parser.add_argument('approve_uid', type=str)
            parser.add_argument('agree', type=bool)
            parser.add_argument('approve_suggestion', type=str)
            args = parser.parse_args()
            deploy_id = args.deploy_id
            approvals = models.Approval.objects.filter(approval_id=deploy_id).order_by('-create_date')
            deployment = models.Deployment.objects.get(deploy_id=deploy_id)
            deployment.approve_suggestion = args.approve_suggestion
            if approvals:
                approval = approvals[0]
                approval.approve_uid = args.approve_uid
                approval.approve_date = datetime.datetime.now()
                approval.annotations = args.approve_suggestion
                if args.agree:
                    approval.approval_status = "rollback_success"
                    deployment.approve_status = "rollback_success"
                    # 审批通过状态改为回滚中
                    deployment.deploy_result = "rollbacking"
                else:
                    approval.approval_status = "rollback_fail"
                    deployment.approve_status = "rollback_fail"
                    # 审批不通过状态修改
                    deployment.deploy_result = "not_rollbacked"
                approval.save()
                deployment.save()
                code = 200
            else:
                code = 410
                res = "A resource with that ID no longer exists"
        except Exception as e:
            code = 500
            res = "Failed to approve the rollback %s." % e
        finally:
            ret = {
                "code": code,
                "result": {
                    "res": res,
                    "msg": msg
                }
            }

        return ret, code


class RollBackReservation(Resource):
    # 获取回滚的详情
    #@api_permission_control(request)
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('deploy_id', type=str, location='args')
        args = parser.parse_args()
        deploy_id = args.deploy_id
        try:
            results = {}
            deployment = models.Deployment.objects.get(deploy_id=deploy_id)
            resource_id = deployment.resource_id
            resource = models.ResourceModel.objects.get(res_id=resource_id)
            deploy_name = deployment.deploy_name
            deploy_name=deploy_name.strip().split('@')[0]
            resource_id = deployment.resource_id
            resource_name = deployment.resource_name
            project_id = deployment.project_id
            project_name = deployment.project_name
            environment = deployment.environment
            release_notes = deployment.release_notes
            app_image = eval(deployment.app_image)
            approve_suggestion = deployment.approve_suggestion
            compute_list = resource.compute_list
            for compute in compute_list:
                for app in app_image:
                    if app["ins_id"] == compute["ins_id"]:
                        app["ips"] = compute["ips"]
                        app["domain_ip"] = compute["domain_ip"]
                        app["quantity"] = compute["quantity"]
            results["resource_id"] = resource_id
            results["deploy_name"] = deploy_name
            results["resource_name"] = resource_name
            results["project_id"] = project_id
            results["project_name"] = project_name
            results["environment"] = environment
            results["release_notes"] = release_notes
            results["compute_list"] = app_image
            results["approve_suggestion"] = approve_suggestion
        except Exception as e:
            res = {
                "code": 400,
                "result": {
                    "res": "failed",
                    "msg": e.args
                }
            }
            return res, 400
        else:
            return results, 200

    # 将回滚的数据发送到crp
    #@api_permission_control(request)
    def post(self):
        code = 200
        res = ""
        msg = {}
        parser = reqparse.RequestParser()
        parser.add_argument('resource_id', type=str)
        parser.add_argument('deploy_id', type=str)
        parser.add_argument('compute_list', type=list, location='json')
        parser.add_argument('deploy_name', type=str)
        args = parser.parse_args()
        resource_id = args.resource_id
        deploy_id = args.deploy_id
        deploy_name = args.deploy_name
        compute_list = args.compute_list
        data = {}
        try:
            resource = models.ResourceModel.objects.get(res_id=resource_id)
            deploy = models.Deployment.objects.get(deploy_id=deploy_id)
            environment = deploy.environment
            database_password = deploy.database_password
            cloud = resource.cloud
            resource_type = resource.resource_type
            # 获取disconf信息
            disconf_server_info = deal_disconf_info(deploy)
            # 将computer信息如IP，更新到数据库
            app_image = eval(deploy.app_image)
            for app in app_image:
                app["domain_ip"] = None
            cmdb_url = current_app.config['CMDB_URL']
            appinfo = attach_domain_ip(app_image, resource, cmdb_url)
            if cloud == '2' and resource_type == "app":
                appinfo = [dict(app, nginx_port=K8S_NGINX_PORT, ips=K8S_NGINX_IPS) for app in appinfo]
            ##推送到crp
            deploy.approve_status = 'success'
            deploy_type = "rollback"
            err_msg, result = deploy_to_crp(deploy,
                                            environment,
                                            database_password,
                                            appinfo, disconf_server_info, deploy_type)
            if err_msg:
                deploy.deploy_result = 'rollback_fail'
            # 更新状态
            deploy.deploy_result = 'rollbacking'
            deploy.save()
            # env = resource.env
            # cloud = resource.cloud
            # resource_name=resource.resource_name
            # res_compute_list = resource.compute_list
            # project_name = resource.project_name
            # for res_compute in res_compute_list:
            #     for compute in compute_list:
            #         if res_compute["ins_id"] == compute["ins_id"]:
            #             res_compute["url"] = compute["url"]
            #             res_compute["port"] = compute["port"]
            #             res_compute["domain"] = compute["domain"]
            #             res_compute["domain_path"] = compute["domain_path"]
            #             res_compute["database_config"] = compute["database_config"]
            # resource.save()
            # # ----------
            # appinfo = []
            # docker_list = []
            # for compute in compute_list:
            #     domain_ip = compute.get('domain_ip')
            #     if domain_ip:
            #         appinfo.append(compute)
            #     docker_list.append(
            #         {
            #             'url': compute.get("url"),
            #             'ins_name': compute.get("ins_name"),
            #             'ip': compute.get("ips"),
            #             'health_check': compute.get("health_check",0),
            #             'host_env': compute.get("host_env"),
            #             'language_env': compute.get("language_env"),
            #             'deploy_source': compute.get("deploy_source"),
            #             'database_config': compute.get("database_config")
            #         }
            #     )
            # data["appinfo"] = appinfo
            # data['docker'] = docker_list
            # data["mysql"] = []
            # data["mongodb"] = []
            # data["dns"] = []
            # data["disconf_server_info"] =[]
            # data["deploy_id"] = deploy_id
            # data["deploy_type"] = "rollback"
            # data["cloud"] = cloud
            # data["resource_name"] = resource_name
            # data["deploy_name"] = deploy_name
            # data["project_name"] = project_name
            # data["environment"] = env
            # CPR_URL = get_CRP_url(env)
            # url = CPR_URL + "api/deploy/deploys"
            # headers = {
            #     'Content-Type': 'application/json',
            # }
            # data_str = json.dumps(data)
            # Log.logger.debug("Data args is " + str(data))
            # result = requests.post(url=url, headers=headers, data=data_str)
            # Log.logger.debug("Result is " + str(result))
        except Exception as e:
            code = 500
            res = "Failed the rollback post data to crp. %s" % e
        finally:
            ret = {
                "code": code,
                "result": {
                    "res": res,
                    "msg": msg
                }
            }
        return ret, code


approval_api.add_resource(ApprovalList, '/approvals')
approval_api.add_resource(ApprovalInfo, '/approvals/<string:res_id>')
approval_api.add_resource(Reservation, '/reservation')
approval_api.add_resource(ReservationAPI, '/reservation/<string:res_id>')
approval_api.add_resource(CapacityInfoAPI, '/capacity/approvals')
approval_api.add_resource(CapacityReservation, '/capacity/reservation')
approval_api.add_resource(RollBackInfoAPI, '/rollback/approvals')
approval_api.add_resource(RollBackReservation, '/rollback/reservation')
