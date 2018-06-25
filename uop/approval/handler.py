# -*- coding: utf-8 -*-
from uop.models import ComputeIns
from uop.log import Log
import random
from uop.util import get_CRP_url
import requests
import json
from config import configs, APP_ENV
from uop.models import ConfigureNamedModel

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