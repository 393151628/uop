# -*- coding: utf-8 -*-
from uop.models import ComputeIns
from uop.log import Log
import random
import uuid
import datetime
from uop.util import get_CRP_url
import requests
import json
from config import configs, APP_ENV
from uop.models import ConfigureNamedModel
from uop import models
from uop.res_callback.handler import send_email_res

BASE_K8S_IMAGE = configs[APP_ENV].BASE_K8S_IMAGE


def resource_reduce(resource,number,ips):
    reduce_list = []
    for os_ins in resource.os_ins_ip_list:
        if os_ins.ip in ips:
            reduce_list.append(os_ins)
    reduce_list = random.sample(reduce_list, number)
    os_inst_id_list = []
    reduce_list = [eval(reduce_.to_json()) for reduce_ in reduce_list]
    for os_ip_dict in reduce_list:
        os_inst_id = os_ip_dict["os_ins_id"]
        os_inst_id_list.append(os_inst_id)
    crp_data = {
        "resource_id": resource.res_id,
        "resource_name": resource.resource_name,
        "os_ins_ip_list": reduce_list,
        "resource_type": resource.resource_type,
        "cloud": resource.cloud,
        "set_flag": 'reduce',
        'syswin_project': 'uop'
    }
    env_ = get_CRP_url(resource.env)
    crp_url = '%s%s' % (env_, 'api/resource/deletes')
    crp_data = json.dumps(crp_data)
    msg = requests.delete(crp_url, data=crp_data)
    return  msg

def deal_crp_data(resource,set_flag):

    data = dict()
    data['set_flag'] = set_flag
    data['unit_id'] = resource.project_id
    data['unit_name'] = resource.project
    data["project_id"] = resource.cmdb2_project_id
    data["module_id"] = resource.cmdb2_module_id
    data['unit_des'] = ''
    data['user_id'] = resource.user_id
    data['username'] = resource.user_name
    data['department'] = resource.department
    data['created_time'] = str(resource.created_date)
    data['resource_id'] = resource.res_id
    data['resource_name'] = resource.resource_name
    data['domain'] = resource.domain
    data['env'] = resource.env
    data['docker_network_id'] = resource.docker_network_id
    data['mysql_network_id'] = resource.mysql_network_id
    data['redis_network_id'] = resource.redis_network_id
    data['mongodb_network_id'] = resource.mongodb_network_id
    data['mongodb_network_id'] = resource.mongodb_network_id
    data['cloud'] = resource.cloud
    data['resource_type'] = resource.resource_type
    data['syswin_project'] = 'uop'
    data['project_name'] = resource.project_name
    # data['cmdb_repo_id'] = item_info.item_id
    named_url_list = []
    rets = ConfigureNamedModel.objects.filter(env=resource.env).order_by("-create_time")
    for ret in rets:
        named_url_list.append(ret.url)
    data["named_url_list"] = named_url_list
    resource_list = resource.resource_list
    compute_list = resource.compute_list
    if resource_list:
        res = []
        for db_res in resource_list:
            res_type = db_res.ins_type
            res.append(
                {
                    "instance_name": db_res.ins_name,
                    "instance_id": db_res.ins_id,
                    "instance_type": res_type,
                    "cpu": db_res.cpu,
                    "mem": db_res.mem,
                    "disk": db_res.disk,
                    "quantity": db_res.quantity,
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
    if compute_list:
        com = []
        for db_com in compute_list:
            meta = json.dumps(db_com.docker_meta)
            deploy_source = db_com.deploy_source
            host_env = db_com.host_env
            url = db_com.url
            ready_probe_path = db_com.ready_probe_path
            if host_env == "docker" and deploy_source == "image" and not ready_probe_path:
                url = BASE_K8S_IMAGE
            com.append(
                {
                    "instance_name": db_com.ins_name,
                    "instance_id": db_com.ins_id,
                    "cpu": db_com.cpu,
                    "mem": db_com.mem,
                    "image_url": url,
                    "quantity": db_com.quantity,
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
                    "availability_zone": db_com.availability_zone,
                    "image_id": db_com.image_id,
                    "flavor": db_com.flavor_id,
                    "pom_path": db_com.pom_path,
                    "branch": db_com.branch,
                    "git_res_url":db_com.git_res_url,
                    "scheduler_zone":db_com.scheduler_zone,
                }
            )
        data['compute_list'] = com
    return data


def approval_list_post(approval_info_list):
    code = 200
    res = ""
    msg = {}
    try:
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

def approval_info_post(args,res_id):
    code = 200
    res = ""
    msg = {}
    try:
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
            approval.annotations = args.annotations if args.annotations else ""

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

def reservation_post(args):
    code = 200
    res = ""
    msg = {}
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
