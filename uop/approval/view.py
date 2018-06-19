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
from uop.deployment.handler import attach_domain_ip, deploy_to_crp, deal_disconf_info
from uop.approval.handler import resource_reduce, deal_crp_data
from uop.res_callback.handler import send_email_res

approval_api = Api(approval_blueprint, errors=approval_errors)


# CPR_URL = current_app.config['CRP_URL']
# CPR_URL = configs[APP_ENV].CRP_URL
BASE_K8S_IMAGE = configs[APP_ENV].BASE_K8S_IMAGE
K8S_NGINX_PORT = configs[APP_ENV].K8S_NGINX_PORT
K8S_NGINX_IPS = configs[APP_ENV].K8S_NGINX_IPS


class ApprovalList(Resource):

    # @api_permission_control(request)
    def post(self):
        code = 200
        res = ""
        msg = {}
        try:
            parser = reqparse.RequestParser()
            parser.add_argument(
                'approval_info_list',
                type=list,
                location="json")
            args = parser.parse_args()

            approval_info_list = args.approval_info_list
            for info in approval_info_list:
                approval_id = str(uuid.uuid1())
                resource_id = info.get("resource_id", "")
                project_id = info.get("project_id", "")
                department = info.get("department", "")
                user_id = info.get("user_id", "")
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
                os_ins_ip_list = resource.os_ins_ip_list
                if os_ins_ip_list:
                    approval_status = "config_processing"
                else:
                    approval_status = "processing"
                resource.approval_status = approval_status
                resource.reservation_status = approval_status
                resource.save()
                code = 200
                # async send email
                os_ins_ip_list = resource.os_ins_ip_list
                if not os_ins_ip_list:
                    send_email_res(resource_id, '200')
        except Exception as e:
            Log.logger.exception(
                "[UOP] ApprovalList failed, Exception: %s", e.args)
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

    # @api_permission_control(request)
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
            parser.add_argument('host_mapping', type=list, location='json')
            parser.add_argument('scheduler_zone', type=str)
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
            scheduler_zone = args.scheduler_zone
            if host_mapping is not None:
                host_mapping = json.dumps(host_mapping)
            network_id_dict = {
                "docker": docker_network_id,
                "mysql": mysql_network_id,
                "redis": redis_network_id,
                "mongodb": mongodb_network_id
            }

            approvals = models.Approval.objects.filter(
                capacity_status="res", resource_id=res_id).order_by("-create_date")
            resource = models.ResourceModel.objects.get(res_id=res_id)
            resource_list = resource.resource_list
            compute_list = resource.compute_list
            if approvals:
                approval = approvals[0]
                approval.approve_uid = args.approve_uid
                approval.approve_date = datetime.datetime.now()
                approval.annotations = args.annotations

                if args.agree:
                    approval.approval_status = "success"
                    resource.approval_status = "success"
                else:
                    approval.approval_status = "failed"
                    resource.approval_status = "failed"
                    os_ins_ip_list = resource.os_ins_ip_list
                    if os_ins_ip_list:
                        resource.reservation_status = "approval_config_fail"
                    else:
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
                        com.scheduler_zone = scheduler_zone
                if resource_list:
                    for res_obj in resource_list:
                        if network_id:
                            res_obj.network_id = network_id
                        else:
                            res_obj.network_id = network_id_dict.get(
                                res_obj.ins_type)
                resource.save()
                code = 200
            else:
                code = 410
                res = "A resource with that ID no longer exists"
        except Exception as e:
            code = 500
            res = "Failed to approve the resource. %s" % str(e)
        finally:
            ret = {
                "code": code,
                "result": {
                    "res": res,
                    "msg": msg
                }
            }

        return ret, code

    # @api_permission_control(request)
    def get(self, res_id):
        code = 200
        res = ""
        msg = {}
        try:
            approval = models.Approval.filter(
                capacity_status="res").objects.get(
                resource_id=res_id)

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

    # @api_permission_control(request)
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
        os_ins_ip_list = resource.os_ins_ip_list
        # 说明是对已有资源配置的审批
        headers = {'Content-Type': 'application/json'}
        if os_ins_ip_list:
            flavor = None
            volume_size = None
            volume_exp_size = None
            os_ins_ip_list = [eval(os_ins.to_json())
                              for os_ins in os_ins_ip_list]
            resource_list = resource.resource_list
            resource_id = resource.res_id
            resource_type = resource.resource_type
            if resource_list:
                flavor = resource_list[0].flavor_id
                volume_size = resource_list[0].volume_size
                volume_exp_size = resource_list[0].volume_exp_size
            data = dict()
            data["set_flag"] = "config"
            data["os_ins_ip_list"] = os_ins_ip_list
            data["flavor"] = flavor if flavor else ''
            data["cloud"] = resource.cloud
            data["volume_size"] = volume_size if volume_size else 0
            data["volume_exp_size"] = volume_exp_size if volume_exp_size else 0
            data["syswin_project"] = "uop"
            data["resource_id"] = resource_id
            data["resource_type"] = resource_type
            data['env'] = resource.env
            data_str = json.dumps(data)
        else:
            set_flag = "res"
            data = deal_crp_data(resource, set_flag)
            data_str = json.dumps(data)
        try:
            Log.logger.info("Data args is %s", data)
            CPR_URL = get_CRP_url(data['env'])
            if os_ins_ip_list:
                msg = requests.put(
                    CPR_URL + "api/resource/sets",
                    data=data_str,
                    headers=headers)
            else:
                msg = requests.post(
                    CPR_URL + "api/resource/sets",
                    data=data_str,
                    headers=headers)
            code = 200
            res = "Success in reserving or configing resource."
        except Exception as e:
            res = "failed to connect CRP service.{}".format(str(e))
            code = 500
            ret = {
                "code": code,
                "result": {
                    "res": res
                }
            }
            return ret, code
        if msg.status_code != 202:
            if os_ins_ip_list:
                resource.reservation_status = "config_fail"
            else:
                resource.reservation_status = "set_fail"
        else:
            if os_ins_ip_list:
                resource.reservation_status = "configing"
            else:
                resource.reservation_status = "reserving"
        resource.save()
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
        # 其他资源的修改
        vid_list = resource.vid_list
        number = vid_list.__str__()
        try:
            if number > 0:
                # 对已经预留好的资源进程修改
                resource_list = resource.resource_list
                for res in resource_list:
                    quantity = res.quantity
                if number < quantity:  # 扩容
                    quantity = quantity - number
                    set_flag = "increase"
                    data = deal_crp_data(resource, set_flag, quantity)
                    data_str = json.dumps(data)
                    CPR_URL = get_CRP_url(data['env'])
                    headers = {'Content-Type': 'application/json'}
                    msg = requests.post(
                        CPR_URL + "api/resource/sets",
                        data=data_str,
                        headers=headers)
                elif number > quantity:  # 缩容
                    ips = []
                    quantity = number - quantity
                    for os_ins in resource.os_ins_ip_list:
                        ip = os_ins.ip
                        ips.append(ip)
                    msg = resource_reduce(resource, quantity, ips)
                else:  # 既不扩容也不缩容
                    set_flag = "res"
                    quantity = "0"
                    data = deal_crp_data(resource, set_flag, quantity)
                    data_str = json.dumps(data)
                    CPR_URL = get_CRP_url(data['env'])
                    headers = {'Content-Type': 'application/json'}
                    msg = requests.post(
                        CPR_URL + "api/resource/sets",
                        data=data_str,
                        headers=headers)
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

    # @api_permission_control(request)
    def put(self, res_id):
        code = 200
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
        data = deal_crp_data(resource, set_flag)
        data_str = json.dumps(data)
        headers = {'Content-Type': 'application/json'}
        try:
            CPR_URL = get_CRP_url(data['env'])
            msg = requests.post(
                CPR_URL +
                "api/resource/sets",
                data=data_str,
                headers=headers)
        except Exception as e:
            res = "failed to connect CRP service.{}".format(str(e))
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
            resource.reservation_status = "set_fail"
            resource.save()
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
    # @api_permission_control(request)
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
                # 更新nova docker 的network_id
                resource = models.ResourceModel.objects.get(
                    res_id=approval.resource_id)
                # resource.deploy_name = deploy_name
                compute_list = resource.compute_list
                if compute_list:
                    for com in compute_list:
                        com.network_id = docker_network_id
                        com.save()
                resource.save()
                if args.agree:
                    approval.approval_status = "%s_success" % (
                        approval.capacity_status)
                    compute_list = resource.compute_list
                    for compute_ in compute_list:
                        capacity_list = compute_.capacity_list
                        for capacity_ in capacity_list:
                            if capacity_.capacity_id == approval_id:
                                capacity_.network_id = docker_network_id.strip()
                    deployment.approve_status = "%s_success" % (
                        approval.capacity_status)
                    # 管理员审批通过后修改resource表deploy_name,更新当前版本
                    deploy_name = deployment.deploy_name
                    resource = models.ResourceModel.objects.get(
                        res_id=approval.resource_id)
                    resource.deploy_name = deploy_name
                    resource.updated_date = datetime.datetime.now()
                    resource.save()
                else:
                    approval.approval_status = "%s_failed" % (
                        approval.capacity_status)
                    deployment.approve_status = "%s_failed" % (
                        approval.capacity_status)
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

    # @api_permission_control(request)
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
            deployment = models.Deployment.objects.get(deploy_id=approval_id)
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
        named_url_list = []
        rets = models.ConfigureNamedModel.objects.filter(env=resource.env).order_by("-create_time")
        for ret in rets:
            named_url_list.append(ret.url)
        data["named_url_list"] = named_url_list
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
                        "volume_exp_size": db_res.volume_exp_size,
                        "image2_id": db_res.image2_id,
                        "flavor2": db_res.flavor2_id,
                        "availability_zone": db_res.availability_zone,
                        "port":db_res.port,
                    }
                )
            data['resource_list'] = res
        ips = []
        if compute_list:
            com = []
            for db_com in compute_list:
                # for i in range(0, db_com.quantity):
                meta = json.dumps(
                    db_com.docker_meta) if db_com.docker_meta else ""
                url = db_com.url
                capacity_list = db_com.capacity_list
                for capacity_ in capacity_list:
                    if capacity_.capacity_id == approval_id:
                        if resource.cloud == "2" and resource_type == "app":
                            number = capacity_.end_number
                        else:
                            number = abs(
                                capacity_.begin_number - capacity_.end_number)
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
                                "host_env": db_com.host_env,
                                "language_env": db_com.language_env,
                                "deploy_source": db_com.deploy_source,
                                "database_config": db_com.database_config,
                                "lb_methods": db_com.lb_methods,
                                "namespace": db_com.namespace,
                                "ready_probe_path": db_com.ready_probe_path,
                                "domain_path": db_com.domain_path,
                                "host_mapping": db_com.host_mapping,
                                "availability_zone":db_com.availability_zone,
                                "image_id": db_com.image_id,
                                "flavor_id": db_com.flavor_id,
                                "pom_path" : db_com.pom_path,
                                "branch" : db_com.branch,
                                "git_res_url": db_com.git_res_url,
                                "scheduler_zone": db_com.scheduler_zone,
                            })
                        ips.extend([ip for ip in db_com.ips])

            data['compute_list'] = com

        data_str = json.dumps(data)
        headers = {'Content-Type': 'application/json'}
        try:
            cloud = resource.cloud
            if cloud == '2' and resource_type == "app":
                CPR_URL = get_CRP_url(data['env'])
                msg = requests.post(
                    CPR_URL + "api/resource/sets",
                    data=data_str,
                    headers=headers)
            else:
                if approval.capacity_status == 'increase':
                    CPR_URL = get_CRP_url(data['env'])
                    msg = requests.post(
                        CPR_URL + "api/resource/sets",
                        data=data_str,
                        headers=headers)
                elif approval.capacity_status == 'reduce':
                    msg = resource_reduce(resource, number, ips)
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
            res = "Failed to capacity resource."
            if approval.capacity_status == "increase":
                deployment.deploy_result = "increase_fail"
            elif approval.capacity_status == "reduce":
                deployment.deploy_result = "reduce_fail"
        else:
            code = 200
            res = "Success in capacity resource."
            if approval.capacity_status == "increase":
                deployment.deploy_result = "increasing"
            elif approval.capacity_status == "reduce":
                deployment.deploy_result = "reducing"
        resource.save()
        deployment.save()
        ret = {
            "code": code,
            "result": {
                "res": res
            }
        }
        return ret, code


class RollBackInfoAPI(Resource):

    # 审批过后更新审批表的信息
    # @api_permission_control(request)
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
            approvals = models.Approval.objects.filter(
                approval_id=deploy_id).order_by('-create_date')
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
    # @api_permission_control(request)
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
            deploy_name = deploy_name.strip().split('@')[0]
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
                    "msg": str(e)
                }
            }
            return res, 400
        else:
            return results, 200

    # 将回滚的数据发送到crp
    # @api_permission_control(request)
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
        try:
            resource = models.ResourceModel.objects.get(res_id=resource_id)
            compute_list = resource.compute_list
            deploy = models.Deployment.objects.get(deploy_id=deploy_id)
            app_image = eval(deploy.app_image)
            for app in app_image:
                for compute in compute_list:
                    if app.get("ins_id") == compute.ins_id:
                        compute.url = app.get("url")
                        compute.git_res_url = app.get("git_res_url")
            environment = deploy.environment
            database_password = deploy.database_password
            resource.updated_date = datetime.datetime.now()
            resource.save()
            # 获取disconf信息
            disconf_server_info = deal_disconf_info(deploy)
            # 将computer信息如IP，更新到数据库
            app_image = eval(deploy.app_image)
            for app in app_image:
                app["domain_ip"] = None
            cmdb_url = current_app.config['CMDB_URL']
            appinfo = attach_domain_ip(app_image, resource, cmdb_url)
            # 推送到crp
            deploy.approve_status = 'success'
            deploy_type = "rollback"
            err_msg, result = deploy_to_crp(deploy,
                                            environment,
                                            database_password,
                                            appinfo, disconf_server_info, deploy_type, deploy_name)
            if err_msg:
                deploy.deploy_result = 'rollback_fail'
            # 更新状态
            deploy.deploy_result = 'rollbacking'
            deploy.approve_status = 'rollback_success'
            deploy.save()
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
