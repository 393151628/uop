# -*- coding: utf-8 -*-
'''
 Logic Layer
'''
import json
import requests
from flask import current_app
from uop.log import Log
from uop.models import ResourceModel
from uop.util import response_data
from config import configs, APP_ENV
from uop.item_info.handler import get_uid_token


CMDB2_URL = configs[APP_ENV].CMDB2_URL
CMDB2_VIEWS = configs[APP_ENV].CMDB2_VIEWS
__all__ = [
    "response_data_not_found", "cmdb_graph_search", "cmdb2_graph_search"
]

def response_data_not_found():

    res = {
        'code': 2015,
        'result': {
            'res': None,
            'msg': u'数据不存在'
        }
    }
    return res


# cmdb1.0 图搜素
def cmdb_graph_search(args):
    try:
        param_str = "?"
        res_id = args.res_id
        if args.reference_sequence:
            if param_str == "?":
                param_str += "reference_sequence=" + args.reference_sequence
            else:
                param_str += "&reference_sequence=" + args.reference_sequence
        if args.reference_type:
            for reference_type in args.reference_type:
                if param_str == "?":
                    param_str += "reference_type=" + reference_type
                else:
                    param_str += "&reference_type=" + reference_type
        if args.item_filter:
            for item_filter in args.item_filter:
                if param_str == "?":
                    param_str += "item_filter=" + item_filter
                else:
                    param_str += "&item_filter=" + item_filter
        if args.columns_filter:
            if param_str == "?":
                param_str += "columns_filter=" + args.columns_filter
            else:
                param_str += "&columns_filter=" + args.columns_filter
        if args.layer_count:
            if param_str == "?":
                param_str += "layer_count=" + args.layer_count
            else:
                param_str += "&layer_count=" + args.layer_count
        if args.total_count:
            if param_str == "?":
                param_str += "total_count=" + args.total_count
            else:
                param_str += "&total_count=" + args.total_count

        resource_instance = ResourceModel.objects.filter(res_id=res_id).first()
        cmdb_p_code = resource_instance.cmdb_p_code

        if cmdb_p_code is None:
            Log.logger.warning("The data of cmdb_p_code is not found for resource id " + res_id)
            return response_data_not_found(), 200
        else:
            CMDB_URL = current_app.config['CMDB_URL']
            CMDB_RELATION = CMDB_URL + 'cmdb/api/repo_relation/'
            if param_str == "?":
                # req_str = CMDB_RELATION + cmdb_p_code + '/'
                layer_and_total_count = '/?layer_count=10&total_count=200'
                reference_types = '&reference_type=dependent'
                reference_sequence = '&reference_sequence=[{\"child\": 3},{\"bond\": 2},{\"parent\": 5}]'
                item_filter = ''
                columns_filter = '&columns_filter={' + \
                                 '\"project_item\":[\"name\"],' + \
                                 '\"deploy_instance\":[\"name\"],' + \
                                 '\"app_cluster\":[\"name\"],' + \
                                 '\"mysql_cluster\":[\"mysql_cluster_wvip\",\"mysql_cluster_rvip\",\"port\"],' + \
                                 '\"mongodb_cluster\":[\"mongodb_cluster_ip1\",\"mongodb_cluster_ip2\",\"mongodb_cluster_ip3\",\"port\"],' + \
                                 '\"redis_cluster\":[\"redis_cluster_vip\",\"port\"],' + \
                                 '\"mysql_instance\":[\"ip_address\",\"port\",\"mysql_dbtype\"],' + \
                                 '\"mongodb_instance\":[\"ip_address\",\"port\",\"dbtype\"],' + \
                                 '\"redis_instance\":[\"ip_address\",\"port\",\"dbtype\"],' + \
                                 '\"virtual_server\":[\"ip_address\",\"hostname\"],' + \
                                 '\"docker\":[\"ip_address\",\"hostname\"],' + \
                                 '\"physical_server\":[\"ip_address\",\"device_type\"],' + \
                                 '\"rack\":[\"rack_number\"],' + \
                                 '\"idc_item\":[\"name\",\"idc_address\"]' + \
                                 '}'
                req_str = CMDB_RELATION + cmdb_p_code + layer_and_total_count + reference_types + reference_sequence + \
                          item_filter + columns_filter
            else:
                req_str = CMDB_RELATION + cmdb_p_code + param_str

            Log.logger.debug("The Request Body is: " + req_str)

            ci_relation_query = requests.get(req_str)
            # Log.logger.debug(ci_relation_query)
            # Log.logger.debug(ci_relation_query.content)
            ci_relation_query_decode = ci_relation_query.content.decode('unicode_escape')
            result = json.loads(ci_relation_query_decode)
            return result
    except Exception as e:
        Log.logger.error(str(e))
        return response_data_not_found()


# cmdb2.0 图搜素
def cmdb2_graph_search(args):
    url = CMDB2_URL + "cmdb/openapi/scene_graph/action/"
    uid, token = get_uid_token()
    view_num = args.view_num
    res_id = args.res_id
    data = {
        "uid": uid,
        "token": token,
        "sign": "",
        "data": {
            "id": "",
            "name": view_num,
            "entity": [
                {
                    "id": res_id,
                    "parameters": [{
                        "code": args.code if args.code else "baseInfo",
                        "value": args.value.decode(encoding="utf-8")
                    }]
                }
            ]
        }
    }
    data_str = json.dumps(data)
    try:
        Log.logger.error("cmdb2_graph_search data:{}".format(data))
        data = requests.post(url, data=data_str).json()["data"]
        if view_num == CMDB2_VIEWS["2"][0]: # B6,获取层级结构
            resources = ResourceModel.objects.filter(department=args.department)
            data = package_data(data, resources)
        result = response_data(200, "按照视图名称{}，未找到任何资源，请确认:\n1、是否CMDB中已定义该试图；\n2、该视图确实没有资源".format(view_num), data) if not data else response_data(200, "success", data)
    except Exception as exc:
        Log.logger.error("cmdb2_graph_search error:{}".format(str(exc)))
        result = response_data(200, str(exc), "")
    return result


def package_data(data, resources):
    assert(data, dict)
    result = []
    instance = data["instance"]
    relation = data["relation"]
    business = filter(lambda ins:ins["level_id"] == 2, instance)
    for b in business:
        node = {"title": b["name"], "id": b["instance_id"], "children": attach_data(resources, relation, b["instance_id"], instance, 3)}
        result.append(node)
    return result


def attach_data(resources, relation, id, instance, level):
    next_instance = filter(lambda ins: ins["level_id"] == level, instance)
    if level < 5:
        return [{"title": ni["name"], "id": ni["instance_id"], "children": attach_data(resources, relation, ni["instance_id"], instance, level + 1)} for ni in next_instance if
                ni["instance_id"] in [r["end_id"] for r in relation if r["start_id"] == id]]
    if level == 5:
        return attach_resource_env(next_instance, resources)


def attach_resource_env(next_instance, resources):
    children = {}
    if resources:
        for res in resources:
            children.setdefault(str(res.env), []).extend([{
                        "title": ni["name"],
                        "instance_id": ni["instance_id"],
                        "code": ni["code"],
                        "model_id": ni["entity_id"]
                    }for ni in next_instance if ni["instance_id"] in res.cmdb2_resource_id
            ])
    return children


