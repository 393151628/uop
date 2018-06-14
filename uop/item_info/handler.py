# -*- coding: utf-8 -*-
'''
 Logic Layer
'''
import json
import requests
import os
import traceback
import time
from uop.log import Log
from uop.util import TimeToolkit, response_data,async
from config import configs, APP_ENV
from datetime import datetime
from uop.models import Cmdb, Token, ModelCache, ResourceModel, Statusvm, ItemInformation
from uop.res_callback.handler import get_relations, format_data_cmdb, judge_value_format, get_scene_graph
import base64
import uuid

curdir = os.path.dirname(os.path.abspath(__file__))
__all__ = [
    "get_uid_token", "Aquery", "get_entity",
    "subgrath_data", "package_data", "get_entity_from_file",
    "fix_instance", "delete_instance"
]


CMDB2_URL = configs[APP_ENV].CMDB2_URL
CMDB2_USER = configs[APP_ENV].CMDB2_OPEN_USER
# CMDB2_VIEWS = entity[1]
# filters = entity[0]
CMDB2_VIEWS = configs[APP_ENV].CMDB2_VIEWS
filters = configs[APP_ENV].CMDB2_ENTITY
code_id = configs[APP_ENV].UOPCODE_CMDB2

resource = {
    "tomcat": filters.get("tomcat"),
    "mysql": filters.get("mysql"),
    "redis": filters.get("redis"),
    "mongodb": filters.get("mongodb"),
}


#临时从本地文件读取数据
def get_data_from_file(td):
    '''
    临时从文本里获取数据
    :param td:
    :return:
    '''
    with open(curdir + "/json.txt", "rb") as fp:
        whole_data = json.load(fp)["data"]
    instance_id = td["data"]["instance"]["instance_id"]
    model_id = int(td["data"]["instance"]["model_id"])
    # Log.logger.info("whole_data:{},{}\n, instance_id:{}".format(whole_data, type(whole_data), instance_id))
    data = [wd for wd in whole_data if str(wd["parent_id"]) == str(instance_id)]
    data = data[0] if data else {"instance": [], "model_id": model_id + 1} #假数据中只需+1
    # data.update(property=id_property[int(model_id + 1)])
    return data


#临时将数据写入本地文件
def push_data_to_file(parent_id, model_id, property):
    '''
    向文本里写数据
    :param property:
    [
    {   "name" : "实例中文名",
        ""
    }
    ]
    :return:
    '''
    try:
        with open(curdir + "/json.txt", "rb") as fp:
            whole_data = json.load(fp)["data"]
        # Log.logger.info("whole_data:{}\nparent_id:{}\nproperty:{},{}".format(whole_data, parent_id, property, type(property)))
        data = [p for p in property if str(p["code"]) == "name"][0]
        node = [wd for wd in whole_data if str(wd["parent_id"]) == str(parent_id)]
        if node:
            node = node[0]
            node_id_list = [int(n["instance_id"]) for n in node["instance"]]
            new_id = str(max(node_id_list) + 1)
        else:
            node = {
                "parent_id": int(parent_id),
                "model_id": int(model_id),
                "instance":[],
            }
            new_id = str(model_id) + '1'
        new_instance = {
            "name": data["value"],
            "instance_id": new_id
        }
        node["instance"].append(new_instance)
        for k, v in enumerate(whole_data):
            if str(v["parent_id"]) == str(parent_id):
                whole_data[k] = node
                break
        else:
            whole_data.append(node)
        # Log.logger.info("node:{},type:{}".format(node, type(node)))
        # Log.logger.info("new whole_data: {}".format(whole_data))
        with open(curdir + "/json.txt", "w") as fp:
            json.dump({"data": whole_data}, fp)
    except Exception as exc:
        Log.logger.error("push_data_to_file: {}".format(str(exc)))
    return node


# 获取uid，token,并缓存
def get_uid_token(flush=False):
    cmdb_info = Cmdb.objects.filter(username=CMDB2_USER)
    tu = Token.objects.all()
    username, password, uid, token = "", "","", ""
    for ci in cmdb_info:
        username = ci.username
        password = base64.b64decode(ci.password)
    for one in tu:
        uid, token = one.uid, one.token
    if uid and token and not flush:
        return uid, token
    url = CMDB2_URL + "cmdb/openapi/login/"
    data = {
        "username": username,
        "password": password,
        "sign": "",
        "timestamp": TimeToolkit.local2utctime(datetime.now())
    }
    data_str = json.dumps(data)
    try:
        # Log.logger.info("login data:{}".format(data))
        ret = requests.post(url, data=data_str, timeout=5)
        # Log.logger.info(ret.json())
        if ret.json()["code"] == 0:
            uid, token = ret.json()["data"]["uid"], ret.json()["data"]["token"]
            one = Token.objects.filter(uid=uid)
            if one:
                Token.objects(uid=uid).update_one(token=token, token_date=TimeToolkit.local2utctimestamp(datetime.now()))
            else:
                tu = Token(uid=uid, token=token, token_date=TimeToolkit.local2utctimestamp(datetime.now()))
                tu.save()
    except Exception as exc:
        Log.logger.error("get uid from CMDB2.0 error:{}".format(str(exc)))
    return uid, token


# 将实体信息数据导入文件
def push_entity_to_file(data):
    entity_list = []
    try:
        for d in data:
            for dc in d.get("children", []):
                if not dc.get("children"):
                    entity_list.append({
                        "code": dc.get("code",""),
                        "name": dc.get("name",""),
                        "id": dc.get("id",""),
                        "property": dc.get("parameters",[])
                    })
                else:
                    processs_chidren_final(entity_list, dc.get("children"))
        model = ModelCache(entity=json.dumps(entity_list),
                         cache_date=TimeToolkit.local2utctimestamp(datetime.now()))
        model.save()
    except Exception as exc:
        Log.logger.error("push_entity_to_file error:{} ".format(str(exc)))
    # Log.logger.info("push_entity_to_file entity_list:{} ".format(entity_list))
    return {"entity": entity_list}


def processs_chidren_final(entity_list, children):
    # entity_list = copy.deepcopy(entity_list)
    # Log.logger.info("in processs_chidren_final")
    for c in children:
        if not c.get("children"):
            entity_list.append({
                "code": c.get("code", ""),
                "name": c.get("name", ""),
                "id": c.get("id", ""),
                "property": c.get("parameters", [])
            })
        else:
            processs_chidren_final(entity_list, c.get("chidren"))


def get_entity_from_file(data):

    sort_key = ["Person", "department", "yewu", "Module", "project"]
    sort_key.extend(list(set(filters.keys()) ^ set(sort_key)))
    assert(isinstance(filters, dict))
    whole_entity = get_entity(data)["entity"]
    Log.logger.info("------------------------- the filters is {}".format(filters))

    compare_entity = map(lambda  x:{"id": x["id"], "name": x["name"], "code": x["code"], "property": x["property"]}, whole_entity)

    single_entity = filter(lambda x: x["id"] in filters.values(), compare_entity)

    if len(single_entity) == len(filters.keys()): # 缓存的实体id没问题，直接补充字段返回
        single_entity = map(lambda x:{'id': x["id"], "name": x["name"], "code": x["code"], "property": x["property"]}, single_entity)
        single_entity = list(
            (lambda item, key:((filter(lambda x: x["code"] == k, item)[0] for k in key)))(single_entity, sort_key)
        ) # 排个序
    else:
        single_entity = u"CMDB2.0 基础模型数据有变，联系管理员解决"
    # Log.logger.info("Single entity is {}:".format(single_entity))
    return single_entity


# A类视图查询
def Aquery(args):
    '''
    A 类视图 查询
    :param data:
    :return:
    '''
    history = {
        "8a3022563add40dbb0130b38": "DevDefaultBusiness",
        "a03ff39ce13140e499f2344d": "SitDefaultBusiness"
    }
    name, code, uid, token, instance_id, model_id, self_model_id = \
        args.name, args.code, args.uid, args.token, args.instance_id, args.model_id, args.self_model_id
    if APP_ENV in ["development", "testing"]: # 走uop
        '''
        instance_id 对应Iteminformation的item_id, 如果不传默认查询所有业务
        '''
        Log.logger.info("APP ENV IS {}".format(APP_ENV))
        get_model_id = lambda codes, v:[c[0] for c in codes.items() if c[1] == v][0]
        if instance_id == "uop" or not instance_id:
            if self_model_id == filters.get("Person") or model_id == filters.get("department"): # 兼容CMDB2.0查部门的接口，返回部门的id，这里返回uop
                return response_data(200, "success", {"instance": [
                    {
                        "instance_id": "uop", "name": "", "property": []
                    }
                ]})
            business = ItemInformation.objects.filter(item_code="business").order_by("-create_date")
            instances = []
            if business:
                for b in business:
                    # Log.logger.info("###### in ItemInformation.get")
                    rname = b.item_name
                    tmp = dict(instance_id=b.item_id, cmdb2_project_id=b.cmdb2_project_id, model_id=get_model_id(code_id, "business"), name=rname, property=[{
                                "code": "baseInfo",
                                "name": u"名称",
                                "value": rname

                            }])
                    instances.append(tmp)
                return response_data(200, "success", {"instance": instances})
            else:
                return response_data(200, "success", {"instance": []})
        else: # 从uop里查数据

            next_instances = ItemInformation.objects.filter(item_relation=instance_id, item_code=code_id[model_id]).\
                order_by("-create_date")
            instances = []
            Log.logger.info("NEXT INSTANCE IS {}".format(next_instances))
            if next_instances:
                for ni in next_instances:
                    # Log.logger.info("###### in ItemInformation.get")
                    rname = ni.item_name
                    try:
                        project_status = ni.project_status
                        Chinese_name = ni.Chinese_name
                        version = ni.version
                        OPS = ni.OPS
                        DEV = ni.DEV
                        tmp = dict(
                                    instance_id=ni.item_id,
                                    model_id=model_id,
                                    name=rname,
                                    cmdb2_project_id=ni.cmdb2_project_id if ni.cmdb2_project_id else ni.item_id,
                                    property=[
                                        {
                                           "code": "baseInfo",
                                           "name": u"名称",
                                           "value": rname
                                        },
                                        {
                                            "code": "status",
                                            "name": u"工程状态",
                                            "value": project_status
                                        },
                                        {
                                            "code": "Chinese_name",
                                            "name": u"中文名",
                                            "value": Chinese_name
                                        },
                                        {
                                            "code": "version",
                                            "name": u"版本号",
                                            "value": version
                                        },
                                        {
                                            "code": "OPS",
                                            "name": u"运维负责人",
                                            "value": OPS
                                        },
                                        {
                                            "code": "DEV",
                                            "name": u"业务负责人",
                                            "value": DEV
                                        }
                                    ])
                    except Exception as e:
                        msg = traceback.format_exc()
                        Log.logger.info("========={}".format(msg))
                    instances.append(tmp)
                return response_data(200, "success", {"instance": instances})
            else:
                return response_data(200, "success", {"instance": []})

    else: # 其他环境暂时走CMDB2
        url_list = CMDB2_URL + "cmdb/openapi/instance/list/"
        url_instance = CMDB2_URL + "cmdb/openapi/query/instance/"  # 如果传instance_id，调用这个直接拿到下一层数据
        if not uid or not token:
            uid, token = get_uid_token()
        if instance_id in history.keys():
            res = Statusvm.objects.filter(business_name=history[instance_id])
            if res:
                instances = []
                name = set()
                for r in res:
                    # Log.logger.info("###### in res")
                    rname = r.module_name
                    if rname not in name:
                        tmp = dict(instance_id=str(len(instances)) + "@@", model_id=1, name=rname, property=[{
                                "code": "baseInfo",
                                "name": u"名称",
                                "value": rname

                        }])
                        instances.append(tmp)
                        name.add(rname)
                return response_data(200, "success", {"instance": instances})
            else:
                # Log.logger.info("$$$$$$ not in res")
                return response_data(200, "success", {"instance": []})

        if "@@" in instance_id:
            res = Statusvm.objects.filter(module_name=instance_id.split("@@")[1])
            if res:
                instances = []
                name = set()
                for r in res:
                    Log.logger.info("###### in res")
                    rname = r.project_name
                    if rname not in name:
                        tmp = dict(instance_id=str(len(instances)) + "@@", model_id=1, name=rname, property=[{

                            "code": "baseInfo",
                            "name": u"名称",
                            "value": rname

                        }])
                        instances.append(tmp)
                        name.add(rname)
                return response_data(200, "success", {"instance": instances})
            pass
        data_list =  {
            "uid": uid,
            "token": token,
            "sign":"",
            "data":{
                "instance":[{
                    "instance_id":"",
                    "name": name #工号
                }],
                "entity":{
                    "model_id": self_model_id
                }
            }
        }
        data_instance = {
            "uid": uid,
            "token": token,
            "sign": "",
            "data": {
                "instance": {
                    "model_id": self_model_id ,
                    "instance_id": instance_id
                }
            }
        }
        data_list_str = json.dumps(data_list)
        data_instance_str = json.dumps(data_instance)
        try:
            if instance_id:
                # Log.logger.info("url_instance request data:{}".format(data_instance))
                ret = requests.post(url_instance, data=data_instance_str, timeout=5)
                # Log.logger.info("url_instance return:{}".format(ret.json()))
                if ret.json()["code"] == -1:
                    return response_data(500, u"请求参数错误，查看instance_id是否和model_id对应", "")
                else:
                    data = analyze_data(ret.json()["data"], model_id)
            else:
                # Log.logger.info("url_list request data:{}".format(data_list))
                ret = requests.post(url_list, data=data_list_str, timeout=5)
                # Log.logger.info("url_list return:{}".format(ret.json()))
                data = analyze_data(ret.json()["data"], model_id, flag=True)
        except Exception as exc:
            Log.logger.error("Aquery error:{}".format(str(exc)))
            data = str(exc)
        data.update({"uid": uid, "token": token})
        result = response_data(200, "success", data)
        return result


#从B类视图中解析出A类数据
def analyze_data(data, entity_id, flag=False):
    ret = {
        "instance":[]
    }
    if flag: # list接口的数据
        instance = map(lambda x: {"instance_id": x.get("id"), "cmdb2_project_id": x.get("id"), "name": x.get("name"), "property": x.get("parameters")}, data) # 拿到名字为name的用户的实例id，理论上只有一个
    else: # instance接口的数据
        fd = filter(lambda x: x.get("entity_id") == entity_id, data)
        if fd:
            fd = fd[0] # 理论上一层下只有一个实体id
            instance = list(dequeued_list(fd["instance"], lambda x: x.get("id"), fd["entity_id"])) # 根据实例id去重
        else: # 没有entity_id 时，给出所有的资源信息
            fds = filter(lambda x: x.get("entity_id") in resource.values(), data)
            if fds:
                instance = []
                for fd in fds:
                    one = list(dequeued_list(fd["instance"], lambda x: x.get("id"), fd["entity_id"]))  # 根据实例id去重
                    instance.extend(one)
            else:
                instance = []
    ret["instance"] = instance
    return ret


# 列表字典按键去重
def dequeued_list(item, key, entity_id):
    assert(isinstance(item, list))
    unique = set()
    get_view_num = lambda x: x[0] if x else ""
    for i, v in enumerate(item):
        if key(v) not in unique:
            unique.add(key(v))
            new = {
                "instance_id": v.get("id"),
                "cmdb2_project_id": v.get("id"),
                "name": v.get("name"),
                "property": v.get("parameters"),
                "model_id": entity_id,
                "view_num": get_view_num([view[0] for index, view in CMDB2_VIEWS.items() if view[2] == entity_id])
            }
            yield new


# 获取所有模型实体的id及属性信息存到文件
def get_entity(data):
    '''
    [
    {
        "id": 实体id
        "name": 实体名
        "code": 实体英文名
        "parameters":[
            {
                'id': 属性id
                'name': 属性名
                'code': 属性编码
                'value_type': 属性类型
            }
        ]
    }
    ]
    :param req_data:
    :return:
    '''
    url = CMDB2_URL + "cmdb/openapi/entity/group/"
    uid, token = data.get("uid"), data.get("token")
    if not uid and not token:
        uid, token = get_uid_token()
    req_data = {
        "uid": uid,
        "token": token,
        "sign": "",
        "data": {
            "name":"",
            "code":"",
            "id":""
        }
    }
    data_str = json.dumps(req_data)
    entity_info = {}
    try:
        modules = ModelCache.objects.first()
        entity_info = {
            "entity": []
        }
        if modules:
            Log.logger.info(" modules is exist....")
            entity_info["entity"] = json.loads(modules.entity)
        else:
            ret = requests.post(url, data=data_str, timeout=5).json()
            if ret["code"] != 0:
                req_data["uid"], req_data["code"] = get_uid_token(True)
                data_str = json.dumps(req_data)
                ret = requests.post(url, data=data_str, timeout=5).json()
            entity_info = push_entity_to_file(ret.get("data"))
    except Exception as exc:
        Log.logger.error("get entity info from CMDB2.0 error: {}".format(exc))
    return entity_info


# 插入子图
#@async
def subgrath_data(args):
    '''
    插入子图数据，并返回图结果
    :param args:
    :return:
    '''

    history = {
        "8a3022563add40dbb0130b38": "DevDefaultBusiness",
        "a03ff39ce13140e499f2344d": "SitDefaultBusiness"
    }

    next_model_id, last_model_id, property, uid, token, last_instance_id = \
        args.next_model_id, args.last_model_id, args.property, args.uid, args.token, args.last_instance_id
    if last_instance_id in history.keys():
        return response_data(200, "success", u"此业务用于存储历史数据，不能新建模块")
    #####
    get_pro = lambda k, pro: [p["value"] for p in pro if p["code"] == k][0]
    # Log.logger.info("The get_pro value is {}".format(get_pro))
    newid = str(uuid.uuid1())
    try:
        if next_model_id in code_id.keys():
            name = get_pro("baseInfo", property)
            flag = ItemInformation.objects.filter(item_name=name,item_relation=last_instance_id)
            if flag:
                return response_data(500, u"名为{}的已存在{}".format(name, code_id[next_model_id]), "fail")
            if len(property) == 4:
                ii = ItemInformation(item_id=newid,
                                     item_code=code_id[next_model_id],
                                     item_depart=get_pro("department", property),
                                     user=get_pro("user", property),
                                     item_relation=last_instance_id,
                                     user_id=get_pro("user_id", property),
                                     item_name=get_pro("baseInfo", property))
            else:
                ii = ItemInformation(item_id=newid,
                                     item_code=code_id[next_model_id],
                                     item_depart=get_pro("department", property),
                                     user=get_pro("user", property),
                                     item_relation=last_instance_id,
                                     user_id=get_pro("user_id", property),
                                     item_name=get_pro("baseInfo", property),

                                     project_status=get_pro("status", property),
                                     Chinese_name=get_pro("Chinese_name", property),
                                     version=get_pro("version", property),
                                     OPS=get_pro("OPS", property),
                                     DEV=get_pro("DEV", property)
                                     )
            # Log.logger.info("The code_id value is {}".format(code_id))
            ii.save()
            # Log.logger.info("Save stop.")
        else:
            Log.logger.error(u"检查配置文件的实体信息，业务模块工程的实体id有变化")

    except Exception as exc:
        Log.logger.error("Save ItemInformation error:{}".format(str(exc)))
        return response_data(200, "success", str(exc))
    #####
    Log.logger.info("Start save to cmdb2 {}".format(args))
    exchange_project_item_id = newid
    to_Cmdb2(args, exchange_project_item_id) # 将CMDB2.0产生的id，返存到Iteminformation保存，后期不用CMDB2可以省去

    return response_data(200, "success", [])

@async
def to_Cmdb2(args, exchange_project_item_id=False):
    next_model_id, last_model_id, property, uid, token, last_instance_id = \
        args.next_model_id, args.last_model_id, args.property, args.uid, args.token, args.last_instance_id
    url = CMDB2_URL + "cmdb/openapi/graph/"
    format_data, graph_data = {}, {}
    data = get_relations(CMDB2_VIEWS["3"][0])
    if not uid and not token:
        data["uid"], data["token"] = get_uid_token()
    Log.logger.info("The uid and token is {}, {}".format(data["uid"], data["token"]))
    models_list = data["entity"]
    if isinstance(models_list, str):
        return models_list
    try:
        model = filter(lambda x:x["entity_id"] == next_model_id, models_list)[0]
    except Exception as e:
        _, entity = get_scene_graph(CMDB2_VIEWS["3"][0])
        model = filter(lambda x:x["entity_id"] == next_model_id, entity)[0]
    # Log.logger.info("The model is {}".format(model))
    item = {}
    nouse = map(lambda pro: item.setdefault(pro["code"], pro["value"]), property)
    up_level = {
        "model_id": last_model_id,
        "instance_id": last_instance_id
    }
    if next_model_id == filters["yewu"]:# 要创建业务，默认放到  UOP临时部 下面
        up_level["instance_id"] = "0accd2ca0ed243e5914bf672" # uop临时部
    i, r = format_data_cmdb(data["relations"], item, model, {}, 0, up_level)
    Log.logger.info("The i, r is {}".format(i, r))
    data.pop("relations")
    data.pop("entity")
    data["data"] = {
        "instance": [i],
        "relation": r
    }
    data_str = json.dumps(data)
    ret = []
    Log.logger.info("The data_str is {}".format(data_str))
    try:
        Log.logger.info("graph_data request: {}".format(data))
        ret = requests.post(url, data=data_str, timeout=5).json()
        Log.logger.info("graph_data result: {}".format(ret))
        if ret["code"] == 0 and exchange_project_item_id:
            Log.logger.info("Instance is {}".format(ret["data"]["instance"]))
            instances = ret["data"]["instance"]
            cmdb2_project_id = [ins["instance_id"] for ins in instances][0]
            project = ItemInformation.objects.filter(item_id=exchange_project_item_id)
            if project:
                for pro in project:
                    pro.cmdb2_project_id = cmdb2_project_id
                    # Log.logger.info("Project item id is {}, project is {}".format(cmdb2_project_id, project))
                    pro.save()
                Log.logger.info(u"替换project的item_id成功：{}--->{}".format(exchange_project_item_id, cmdb2_project_id))
        # Log.logger.info("graph_data result: {}".format(ret))
    except Exception as exc:
        ret = []
        Log.logger.error("graph_data: {}".format(str(exc)))


# 组装业务工程模块接口数据
def package_data(ret, ut):
    '''
    传给前端的数据格式
    "uid": 1,
    "token": wtf,
    "module_id":123, #实体id
    "instance":[
        {
        "name":u"toon基础",
        "instance_id":123-1 #实例id
        },
        {
        "name":u"企通",
        "instance_id":123-2
        },
    ],
    ]
    '''
    # data = {
    #     "uid": 1,
    #     "token": 'wtf',
    #     "parent_id":2,
    #     "entity_id":3, #实体id
    #     "instance":[
    #         {
    #             "name":u"toon基础",
    #             "instance_id":'1231' #实例id
    #         },
    #         {
    #             "name":u"企通",
    #             "instance_id":'1232'
    #         },
    #         {
    #             "name": u"政通",
    #             "instance_id": '1233'
    #         },
    #         {
    #             "name": u"食尚",
    #             "instance_id": '1234'
    #         },
    #     ],
    # }
    ret.update(ut)
    ret.pop("data")
    return ret


def fix_instance(args):
    # start_time = time.time()
    url = CMDB2_URL + "cmdb/openapi/graph/"
    model_id, instance_id, item, uid, token = \
        args.model_id, args.instance_id, args.property, args.uid, args.token
    Log.logger.info("The item value is {}，model id is {}".format(item, model_id))  # [{u'code': u'baseInfo', u'value': u'victorfeng'}]
    # 修改uop数据
    # item_name = [i['value'] if i["code"] == "baseInfo" else "" for i in item]
    get_pro = lambda x, field: [i['value'] for i in x if i['code'] == field][0]
    baseInfo = ""
    project_status = ""
    Chinese_name = ""
    version = ""
    OPS = ""
    DEV = ""
    if len(item) != 1:  # 只修改业务
        project_status = get_pro(item, "status")
        Chinese_name = get_pro(item, "Chinese_name")
        version = get_pro(item, "version")
        OPS = get_pro(item, "OPS")
        DEV = get_pro(item, "DEV")
    baseInfo = get_pro(item, "baseInfo")
    # Log.logger.info("Item_name is {},instance_id is {}".format(item_name, instance_id))
    try:
        ItemInformation.objects(item_id=instance_id).update_one(set__item_name=str(baseInfo))
        ItemInformation.objects(item_id=instance_id).update_one(set__project_status=str(project_status))
        ItemInformation.objects(item_id=instance_id).update_one(set__Chinese_name=str(Chinese_name))
        ItemInformation.objects(item_id=instance_id).update_one(set__version=str(version))
        ItemInformation.objects(item_id=instance_id).update_one(set__OPS=str(OPS))
        ItemInformation.objects(item_id=instance_id).update_one(set__DEV=str(DEV))

    except Exception as e:
        msg = traceback.format_exc()
        Log.logger.info("Save uop is wrong ".format(msg))
    # end_time_uop = time.time()
    # use_time_uop = end_time_uop - start_time
    # Log.logger.info("The UOP waste time is {}".format(use_time_uop))

    if not uid or not token:
        uid, token = get_uid_token()
    entity = get_relations(CMDB2_VIEWS["3"][0])["entity"]  # B7
    Log.logger.info("The entity is {}".format(entity))
    get_fix_model = lambda x: x[0] if x else "CMDB模型有变动，在视图{}未找到实体{}的信息，请联系管理员".format(CMDB2_VIEWS["3"][0], model_id)
    fix_model = get_fix_model(filter(lambda x: x["entity_id"] == model_id, entity))
    get_value = lambda item, pro, code: judge_value_format([{i.get("code"): i.get("value")}for i in item if i.get("code") == code], pro, {})
    data = {
        "uid": uid,
        "token": token,
        "sign": "",
        "data": {
            "instance": [
                {
                    "model_id": model_id,
                    "instance_id": instance_id,
                    'parameters': list(
                        (
                            lambda property, item:
                            (
                                {
                                    "code": str(pro["code"]),
                                    "value_type": pro["value_type"],
                                    "value": get_value(item, pro, str(pro["code"]))
                                }
                                for pro in property
                            )
                        )(fix_model["parameters"], item)
                    )
                }
            ]
        }
    }
    if isinstance(fix_model, str):
        return {"warning": fix_model}
    data_str = json.dumps(data)
    try:
        # Log.logger.info("post 'fix instances data' to cmdb/openapi/graph/ request:{}".format(data))
        instance = requests.post(url, data=data_str, timeout=5).json()
        # Log.logger.info("post return json:{}".format(instance))
        instance = instance["data"]["instance"]
        # Log.logger.info("post 'fix instances data' to cmdb/openapi/graph/ result:{}".format(instance))
    except Exception as exc:
        instance = []
        Log.logger.error("post 'fix instances data' to cmdb/openapi/graph/ error:{}".format(str(exc)))
    data.pop("data")
    data.update({
        "instance": instance
    })
    Log.logger.info("DATA IS {}".format(data))
    # end_time_cmdb = time.time()
    # use_time_cmdb = end_time_cmdb - end_time_uop
    # Log.logger.info("The CMDB use time is {}".format(use_time_cmdb))
    return data


def delete_instance(args):
    url = CMDB2_URL + "cmdb/openapi/graph/"
    delete_list = args.delete_list
    assert(isinstance(delete_list, list))
    uid, token = get_uid_token()
    data = {
        "uid": uid,
        "token": token,
        "sign": "",
        "data": {
            "instance": delete_list
        }
    }
    data_str = json.dumps(data)
    try:
        # Log.logger.info("delete 'instances' to cmdb/openapi/graph/ request:{}".format(data))
        instance = requests.delete(url, data=data_str).json()
        # Log.logger.info("delete return json:{}".format(instance))
        # Log.logger.info("delete 'instances' to cmdb/openapi/graph/ result:{}".format(instance))
    except Exception as exc:
        instance = []
        Log.logger.error("delete 'instances' to cmdb/openapi/graph/ error:{}".format(str(exc)))
    data.pop("data")
    data.update({
        "instance": instance
    })
    return data

