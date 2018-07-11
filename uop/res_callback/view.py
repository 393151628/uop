# -*- coding: utf-8 -*-
import copy
import requests
import json
import datetime
import traceback
import uuid
from flask import request, current_app
from flask_restful import reqparse, Api, Resource
from uop.models import  ResourceModel, StatusRecord,OS_ip_dic,Deployment, Statusvm
from uop.res_callback import res_callback_blueprint
from uop.res_callback.errors import res_callback_errors
from uop.deploy_callback.handler import create_status_record
from uop.res_callback.handler import *
from uop.res_callback.handler import send_email_res
from transitions import Machine
from uop.util import get_CRP_url,async
from uop.log import Log
from uop.resources.handler import delete_cmdb1,delete_cmdb2,delete_uop
from uop.permission.handler import api_permission_control

res_callback_api = Api(res_callback_blueprint, errors=res_callback_errors)

# Define CallBack JSON Format
items_sequence_list_config = [
    {
        'deploy_instance':
            {
                'container':
                    [
                        {
                            'app_cluster':
                                [
                                    {
                                        'instance':
                                            {
                                                'app_instance'
                                            }
                                    }
                                ]
                        }
                    ],
                'db_info':
                    {
                        'mysql':
                            {
                                'mysql_cluster':
                                    [
                                        {
                                            'instance':
                                                {
                                                    'mysql_instance'
                                                }
                                        }
                                    ],
                            },
                        'mongodb':
                            {
                                'mongodb_cluster':
                                    [
                                        {
                                            'instance':
                                                {
                                                    'mongodb_instance'
                                                }
                                        }
                                    ],
                            },
                        'redis':
                            {
                                'redis_cluster':
                                    [
                                        {
                                            'instance':
                                                {
                                                    'redis_instance'
                                                }
                                        }
                                    ]
                            }
                    }
            }
    }]

# Define CMDB Item Property p_code to CallBack JSON Property Mapper
property_json_mapper_config = {
    'deploy_instance': {
        'name': 'resource_name',
        'deploy_instance_id': 'resource_id',
        'project_pople': 'username',
        'project_dep': 'department',
        'create_time': 'created_time',
        'reservation_status': 'status',
        'deploy_status': 'deploy_status',
    },
    'app_cluster': {
        'name': 'cluster_name',
        'project_domain': 'domain'
    },
    'app_instance': {
        'name': 'container_name',
        'ip': 'ip',
        'ip_address': 'ip',
        'cpu_count': 'cpu',
        'memory_count': 'memory',
        'username': 'username',
        'password': 'password',
        'image_addr': 'image_addr',
        'physical_server': 'physical_server'
    },
    'docker': {
        'name': 'container_name',
        'ip_address': 'ip',
        'cpu_count': 'cpu',
        'memory_count': 'memory',
        'username': 'username',
        'password': 'password',
        'image_addr': 'image_addr',
        'physical_server': 'physical_server'
    },
    'mysql_cluster': {
        'name': 'name',
        "username": "username",
        "password": "password",
        "port": "port",
        "mysql_cluster_wvip": "wvip",
        "mysql_cluster_rvip": "rvip",
        "ins_id": "ins_id"
    },
    'mysql_instance': {
        'name': 'name',
        "mysql_username": "username",
        "mysql_password": "password",
        "dbtype": "dbtype",
        'ip_address': 'ip',
        "port": "port",
        'cpu_count': 'cpu',
        'memory_count': 'memory',
        'physical_server': 'physical_server'
    },
    'mongodb_cluster': {
        'name': 'name',
        "username": "username",
        "password": "password",
        "port": "port",
        "mongodb_cluster_ip1": "vip1",
        "mongodb_cluster_ip2": "vip2",
        "mongodb_cluster_ip3": "vip3",
        "ins_id": "ins_id"
    },
    'mongodb_instance': {
        'name': 'name',
        "username": "username",
        "password": "password",
        "dbtype": "dbtype",
        'ip_address': 'ip',
        "port": "port",
        'cpu_count': 'cpu',
        'memory_count': 'memory',
        'physical_server': 'physical_server'
    },
    'redis_cluster': {
        'name': 'name',
        "username": "username",
        "password": "password",
        "port": "port",
        "redis_cluster_vip": "vip",
        "ins_id": "ins_id"
    },
    'redis_instance': {
        'name': 'name',
        "username": "username",
        "password": "password",
        "dbtype": "dbtype",
        'ip_address': 'ip',
        "port": "port",
        'cpu_count': 'cpu',
        'memory_count': 'memory',
        'physical_server': 'physical_server'
    },
    'virtual_server': {
        'name': 'name',
        'ip_address': 'ip',
        'cpu_count': 'cpu',
        'memory_count': 'memory',
        'username': 'username',
        'password': 'password',
        'physical_server': 'physical_server'
    },
}

mapping_type_status = {
    'mysql' : 'mysql',
    'mycat' : 'mysql',
    'mongodb' : 'mongo',
    'redis' : 'redis',
    'app_cluster' : 'docker',
}

mapping_scale_info = {
    'increase' : '扩容',
    'reduce' : '缩容',
    'res': '预留',
}

mapping_msg_info = {
    'app' : '应用集群',
    'kvm' : 'kvm',
}


class ResourceProviderTransitions(object):
    # Define some states.
    states = ['init', 'stop',
              'deploy_instance',
              'app_cluster', 'app_instance',
              'mysql_cluster', 'mysql_instance',
              'mongodb_cluster', 'mongodb_instance',
              'redis_cluster', 'redis_instance',
              'docker', 'virtual_server']

    # Define transitions.
    transitions = [
        {'trigger': 'stop', 'source': '*', 'dest': 'stop', 'after': 'do_stop'},
        {'trigger': 'deploy_instance', 'source': 'init', 'dest': 'deploy_instance', 'after': 'do_deploy_instance'},
        {'trigger': 'app_cluster', 'source': ['deploy_instance', 'docker', 'virtual_server'], 'dest': 'app_cluster', 'after': 'do_app_cluster'},
        {'trigger': 'app_instance', 'source': 'app_cluster', 'dest': 'app_instance', 'after': 'do_app_instance'},
        {'trigger': 'app_instance', 'source': 'docker', 'dest': 'app_instance', 'after': 'do_app_instance'},
        {'trigger': 'mysql_cluster', 'source': ['deploy_instance', 'docker', 'virtual_server'], 'dest': 'mysql_cluster', 'after': 'do_mysql_cluster'},
        {'trigger': 'mysql_instance', 'source': 'mysql_cluster', 'dest': 'mysql_instance', 'after': 'do_mysql_instance'},
        {'trigger': 'mysql_instance', 'source': 'virtual_server', 'dest': 'mysql_instance', 'after': 'do_mysql_instance'},
        {'trigger': 'mongodb_cluster', 'source': ['deploy_instance', 'docker', 'virtual_server'], 'dest': 'mongodb_cluster', 'after': 'do_mongodb_cluster'},
        {'trigger': 'mongodb_instance', 'source': 'mongodb_cluster', 'dest': 'mongodb_instance', 'after': 'do_mongodb_instance'},
        {'trigger': 'mongodb_instance', 'source': 'virtual_server', 'dest': 'mongodb_instance', 'after': 'do_mongodb_instance'},
        {'trigger': 'redis_cluster', 'source': ['deploy_instance', 'docker', 'virtual_server'], 'dest': 'redis_cluster', 'after': 'do_redis_cluster'},
        {'trigger': 'redis_instance', 'source': 'redis_cluster', 'dest': 'redis_instance', 'after': 'do_redis_instance'},
        {'trigger': 'redis_instance', 'source': 'virtual_server', 'dest': 'redis_instance', 'after': 'do_redis_instance'},
        {'trigger': 'docker', 'source': 'app_instance', 'dest': 'docker', 'after': 'do_docker'},
        {'trigger': 'virtual_server', 'source': ['mysql_instance', 'mongodb_instance', 'redis_instance'], 'dest': 'virtual_server', 'after': 'do_virtual_server'}
    ]

    def __init__(self, property_mappers_list):
        """
        property_mappers_list = [
            {
                'deploy_instance': {
                     'name': '部署实例1',
                     'resource_id': '资源ID'
                 }
             },
            {
                'app_cluster': {
                     'name': '应用集群1',
                     'domain': 'checkin.syswin.com'
                 }
             }
        ]
        """
        # Initialize the variable
        self.property_mappers_list = copy.deepcopy(property_mappers_list)
        self.property_mappers_list.reverse()
        # 刚刚处理过的节点，可能为存在引用关系的父节点
        self.pre_property_mapper = {}
        # 待处理的节点
        self.property_mapper = {}

        # self.pcode_mapper 仅记录最近一次更新的 pcode 数据，因此集群需要按如下顺序构造property_mappers_list
        # 第一个集群 -> 第一个集群的实例1 -> …… -> 第一个集群的实例n -> 第二个集群 -> 第二个集群的实例1 -> ……
        self.pcode_mapper = {}

        # Initialize the state machine
        self.machine = Machine(model=self,
                               states=ResourceProviderTransitions.states,
                               transitions=ResourceProviderTransitions.transitions,
                               initial='init')

    def preload_property_mapper(self):
        if len(self.property_mappers_list) != 0:
            if len(self.pre_property_mapper) == 0:
                self.pre_property_mapper = self.property_mapper
            if len(self.pre_property_mapper) != 0 and len(self.property_mapper) != 0 \
                    and (self.pre_property_mapper.keys()[0] != self.property_mapper.keys()[0]):
                self.pre_property_mapper = self.property_mapper
            self.property_mapper = self.property_mappers_list.pop()
        else:
            self.pre_property_mapper = {}
            self.property_mapper = {}

    def tick_announce(self):
        self.preload_property_mapper()
        if len(self.property_mapper) != 0:
            item_id = self.property_mapper.keys()[0]
            func = getattr(self, item_id, None)
            if not func:
                raise NotImplementedError("Unexpected item_id=%s" % item_id)
            Log.logger.debug('Trigger is %s', item_id)
            func()
        else:
            self.stop()

    def transit_item_property_list(self, item_id):
        repo_item = {}
        transited_property_list = []
        try:
            CMDB_URL = current_app.config['CMDB_URL']
            CMDB_ITEM_PROPERTY_LIST_URL = CMDB_URL+'cmdb/api/property_list/'
            resp_item_property = requests.get(CMDB_ITEM_PROPERTY_LIST_URL+item_id)
            item_property = json.loads(resp_item_property.text)
            property_list = item_property.get('result').get('res')
            for one_property in property_list:
                p_code = one_property.get('id')
                property_type = one_property.get('type')
                # string 类型
                if 'string' == property_type:
                    value = self.property_mapper.values()[0].get(p_code)
                    if value is None:
                        keys = self.pre_property_mapper.keys()
                        if len(keys) >= 1:
                            value = self.pre_property_mapper.values()[0].get(p_code)
                    if value is not None:
                        transited_property = {
                            'type': property_type,
                            'p_code': p_code,
                            'value': value
                        }
                        transited_property_list.append(transited_property)
                # reference 类型
                elif 'reference' == property_type:
                    reference_ci = one_property.get('reference_ci')
                    reference_id = self.pcode_mapper.get(reference_ci)
                    if reference_id is not None:
                        transited_property = {
                            'type': property_type,
                            'p_code': p_code,
                            'name': one_property.get('name'),
                            'reference_ci': reference_ci,
                            'reference_id': reference_id
                        }
                        transited_property_list.append(transited_property)
            if len(transited_property_list) >= 1:
                repo_item['item_id'] = item_id
                CMDB_URL = current_app.config['CMDB_URL']
                CMDB_ITEM_URL = CMDB_URL+'cmdb/api/cmdb/item/'
                resp_item = requests.get(CMDB_ITEM_URL+item_id)
                item = json.loads(resp_item.text)
                repo_item['name'] = item.get('result').get('res').get('item_name')
                repo_item['property_list'] = transited_property_list
        except Exception as e:
            Log.logger.debug(e.message)
        return repo_item

    def _do_one_item_post(self, item_id):
        repo_item = self.transit_item_property_list(item_id)
        data = json.dumps(repo_item)
        Log.logger.debug("Resource Provider CallBack to CMDB RESTFUL API Post data is:")
        Log.logger.debug(data)
        CMDB_URL = current_app.config['CMDB_URL']
        CMDB_REPO_URL = CMDB_URL+'cmdb/api/repo/'
        resp_repo_item = requests.post(CMDB_REPO_URL, data=data)
        item_property = json.loads(resp_repo_item.text)
        code = item_property.get('code')
        Log.logger.debug("The CMDB RESTFUL API Post Response is:")
        Log.logger.debug(item_property)
        Log.logger.debug("The Response code is :"+code.__str__())
        if 2002 == code:
            p_code = item_property.get('result').get('id')
            if str(item_id) == "app_cluster":
                Log.logger.info("if item_id:{}".format(item_id))
                property_list = repo_item.get("property_list")
                name_dict = {}
                for p in property_list:
                    for k, v in p.items():
                        if v == "name":
                            name_dict = p
                            break
                app_name = name_dict["value"]
                self.pcode_mapper[app_name + u"应用集群"] = p_code
                self.pcode_mapper[item_id] = p_code
            else:
                Log.logger.info("else item_id:{}".format(item_id))
                self.pcode_mapper[item_id] = p_code
            Log.logger.debug("Add Item(%s): p_code(%s) for self.pcode_mapper" % (item_id, p_code))

    def _do_get_physical_server_for_instance(self, physical_server):
        if "@" in physical_server:
            physical_server = physical_server.split("@")[0]
        condition = 'item_id=physical_server&p_code=hostname&value=' + physical_server
        CMDB_URL = current_app.config['CMDB_URL']
        CMDB_REPO_ITEM_CONDITION_GET_URL = CMDB_URL+'cmdb/api/repo_detail/'
        request_url = CMDB_REPO_ITEM_CONDITION_GET_URL + '?' + condition
        resp_repo_item = requests.get(request_url)
        item_property = json.loads(resp_repo_item.text)
        code = item_property.get('code')
        if 2002 == code:
            res=item_property.get('result').get('res')
            if res:
                p_code = res[0].get('p_code')
            else:
                p_code = str(uuid.uuid1())
            self.pcode_mapper['physical_server'] = p_code
            Log.logger.debug("Add Item physical_server(%s): p_code(%s) for self.pcode_mapper"
                             % (physical_server, p_code))

    def start(self):
        self.run()

    def run(self):
        while self.state != 'stop':
            self.tick_announce()

    @transition_state_logger
    def do_init(self):
        # 状态机初始状态
        pass

    @transition_state_logger
    def do_stop(self):
        # 停止状态机
        del self

    @transition_state_logger
    def do_deploy_instance(self):
        # 部署实例状态
        self._do_one_item_post('deploy_instance')

    @transition_state_logger
    def do_app_cluster(self):
        # 应用集群状态
        if 'app_instance' in self.pcode_mapper:
            self.pcode_mapper.pop('app_instance', None)
        self._do_one_item_post('app_cluster')

    @transition_state_logger
    def do_app_instance(self):
        # 应用实例状态
        if 'docker' in self.pcode_mapper:
            self.pcode_mapper.pop('docker', None)
        self._do_one_item_post('app_instance')
        physical_server = self.property_mapper.get('app_instance').get('physical_server')
        self._do_get_physical_server_for_instance(physical_server)
        self.docker()

    @transition_state_logger
    def do_docker(self):
        # docker状态
        self._do_one_item_post('docker')

    @transition_state_logger
    def do_mysql_cluster(self):
        # MySQL数据库集群状态
        if 'mysql_instance' in self.pcode_mapper:
            self.pcode_mapper.pop('mysql_instance', None)
        if 'mongodb_instance' in self.pcode_mapper:
            self.pcode_mapper.pop('mongodb_instance', None)
        if 'redis_instance' in self.pcode_mapper:
            self.pcode_mapper.pop('redis_instance', None)
        self._do_one_item_post('mysql_cluster')

    @transition_state_logger
    def do_mysql_instance(self):
        # MySQL数据库实例状态
        if 'virtual_server' in self.pcode_mapper:
            self.pcode_mapper.pop('virtual_server', None)
        self._do_one_item_post('mysql_instance')
        physical_server = self.property_mapper.get('mysql_instance').get('physical_server')
        self._do_get_physical_server_for_instance(physical_server)
        self.virtual_server()

    @transition_state_logger
    def do_mongodb_cluster(self):
        # MongoDB数据库集群状态
        if 'mysql_instance' in self.pcode_mapper:
            self.pcode_mapper.pop('mysql_instance', None)
        if 'mongodb_instance' in self.pcode_mapper:
            self.pcode_mapper.pop('mongodb_instance', None)
        if 'redis_instance' in self.pcode_mapper:
            self.pcode_mapper.pop('redis_instance', None)
        self._do_one_item_post('mongodb_cluster')

    @transition_state_logger
    def do_mongodb_instance(self):
        # MongoDB数据库实例状态
        if 'virtual_server' in self.pcode_mapper:
            self.pcode_mapper.pop('virtual_server', None)
        self._do_one_item_post('mongodb_instance')
        physical_server = self.property_mapper.get('mongodb_instance').get('physical_server')
        self._do_get_physical_server_for_instance(physical_server)
        self.virtual_server()

    @transition_state_logger
    def do_redis_cluster(self):
        # Redis数据库集群状态
        if 'mysql_instance' in self.pcode_mapper:
            self.pcode_mapper.pop('mysql_instance', None)
        if 'mongodb_instance' in self.pcode_mapper:
            self.pcode_mapper.pop('mongodb_instance', None)
        if 'redis_instance' in self.pcode_mapper:
            self.pcode_mapper.pop('redis_instance', None)
        self._do_one_item_post('redis_cluster')

    @transition_state_logger
    def do_redis_instance(self):
        # Redis数据库实例状态
        if 'virtual_server' in self.pcode_mapper:
            self.pcode_mapper.pop('virtual_server', None)
        self._do_one_item_post('redis_instance')
        physical_server = self.property_mapper.get('redis_instance').get('physical_server')
        self._do_get_physical_server_for_instance(physical_server)
        self.virtual_server()

    @transition_state_logger
    def do_virtual_server(self):
        # virtual_server状态
        self._do_one_item_post('virtual_server')


class ResourceProviderCallBack(Resource):
    """
    资源预留回调
    """
    # @async
    @classmethod
    def write_data_cmdb1(cls,request_data,resource,set_flag,cloud,resource_type,is_write_to_cmdb,CMDB_URL):
        """
        异步往cmdb1.0写入数据
        :param request_data:
        :param resource:
        :param set_flag:
        :param cloud:
        :param resource_type:
        :param is_write_to_cmdb:
        :param CMDB_URL:
        :return:
        """
        Log.logger.info("Save to cmdb request data is {}".format(request_data))
        property_mappers_list = do_transit_repo_items(items_sequence_list_config, property_json_mapper_config,
                                                      request_data)
        Log.logger.debug('property_mappers_list 的内容是：%s' % property_mappers_list)
        rpt = ResourceProviderTransitions(property_mappers_list)
        rpt.start()
        if rpt.state == "stop":
            Log.logger.debug("完成停止")
        else:
            Log.logger.debug(rpt.state)
        if is_write_to_cmdb is True:
            Log.logger.debug("rpt.pcode_mapper的内容:%s" % (rpt.pcode_mapper))
            if set_flag in ["increase", "reduce"]:
                if cloud == "2" and resource_type == "app":
                    resource.cmdb_p_code = rpt.pcode_mapper.get('deploy_instance')
                else:
                    CMDB_STATUS_URL = CMDB_URL + 'cmdb/api/scale/'
                    old_pcode = copy.deepcopy(resource.cmdb_p_code)
                    app_cluster_name = ""
                    new_pcode = ""
                    for itemid, pcode in rpt.pcode_mapper.items():
                        if u"应用集群" in itemid:
                            app_cluster_name = itemid[:-4]
                            new_pcode = pcode
                            break
                    cmdb_req = {"old_pcode": old_pcode, "new_pcode": new_pcode,
                                "app_cluster_name": app_cluster_name}
                    Log.logger.info("increase or reduce to CMDB cmdb_req:{}".format(cmdb_req))
                    data = json.dumps(cmdb_req)
                    ret = requests.post(CMDB_STATUS_URL, data=data)
                    Log.logger.info("CMDB return:{}".format(ret))
            else:
                resource.cmdb_p_code = rpt.pcode_mapper.get('deploy_instance')
            resource.save()

    @classmethod
    def process_data(cls, request_data):
        resource_id = request_data.get('resource_id')
        status = request_data.get('status')
        error_msg = request_data.get('error_msg')
        set_flag = request_data.get('set_flag')
        resource_type = request_data.get('resource_type')
        resource = ResourceModel.objects.get(res_id=resource_id)
        env = resource.env
        cloud = resource.cloud
        is_write_to_cmdb = False
        increase_ips=[]
        if status == "ok":
            is_write_to_cmdb = True
            container = request_data.get('container',[])
            for i in container:
                for j in resource.compute_list:
                    if i.get('ins_id') == j.ins_id:
                        ips=j.ips
                        if cloud == "2" and resource_type == "app":
                            ips=[]
                        for ins in i.get('instance'):
                            ip = ins.get('ip')
                            ips.append(ip)
                            increase_ips.append(ip)
                            img_url = ins.get("img_url")
                            deploy_source = ins.get("deploy_source")
                        if deploy_source == "git":
                            j.git_res_url = img_url
                        j.ips = ips
                        j.quantity = len(ips)
            # 往cmdb写入数据
            CMDB_URL = current_app.config['CMDB_URL']
            if CMDB_URL:
                cls.write_data_cmdb1(request_data,resource,set_flag,cloud,resource_type,is_write_to_cmdb,CMDB_URL)
            else:
                pcode = str(uuid.uuid1())
                resource.cmdb_p_code = pcode
        os_ids = []
        os_ip_list = []
        os_ins_list = resource.os_ins_list
        os_ins_ip_list = resource.os_ins_ip_list
        if os_ins_list:
            if cloud == "2" and resource_type == "app":
                os_ids = []
            else:
                os_ids = os_ins_list
        if os_ins_ip_list:
            if cloud == "2" and resource_type == "app":
                os_ip_list=[]
            else:
                os_ip_list = os_ins_ip_list
        container = request_data.get('container')
        for _container in container:
            instances = _container.get('instance')
            cpu = str(_container.get('cpu', '2'))
            mem = str(_container.get('mem', '2'))
            for instance in instances:
                os_ins_id = instance.get('os_inst_id')
                ip = instance.get('ip')
                os_vol_id = instance.get('os_vol_id')
                physical_server = instance.get('physical_server')
                os_type = "docker"
                if resource_type == "app":
                    os_type = "docker"
                if resource_type == "kvm":
                    os_type = "kvm"
                os_ip_dic = OS_ip_dic(ip=ip, os_ins_id=os_ins_id, os_type=os_type, cpu=cpu, mem=mem,
                                      os_vol_id=os_vol_id,physical_server=physical_server)
                os_ip_list.append(os_ip_dic)
                os_ids.append(os_ins_id)

        db_info = request_data.get('db_info')
        vid_list = []
        for key, value in db_info.items():
            os_ins_ids = []
            wid = value.get("wvid")
            rid = value.get("rvid")
            vid = value.get("vid")
            cpu = str(value.get("cpu", '2'))
            mem = str(value.get("mem", '2'))
            wvip = value.get("wvip")
            rvip = value.get("rvip")
            vip = value.get("vip")
            port = value.get("port")
            if wid:
                vid_list.append(wid)
            if rid:
                vid_list.append(rid)
            if vid:
                vid_list.append(vid)
            for instance in value.get('instance'):
                os_ins_id = instance.get('os_inst_id')
                ip = instance.get('ip')
                os_type = instance.get('instance_type')
                os_vol_id = instance.get('os_vol_id')
                physical_server = instance.get('physical_server')
                username = instance.get('username')
                password = instance.get('password')
                os_ip_dic = OS_ip_dic(ip=ip, os_ins_id=os_ins_id, os_type=os_type, cpu=cpu, mem=mem,
                                      os_vol_id=os_vol_id,wvip=wvip,rvip=rvip,vip=vip,port=port,physical_server=physical_server,
                                      username=username,password=password)
                os_ip_list.append(os_ip_dic)
                os_ids.append(os_ins_id)
            if os_ins_ids:
                os_ids.append(os_ins_ids)
        resource.os_ins_list = os_ids
        resource.vid_list = vid_list
        resource.os_ins_ip_list = os_ip_list
        # ---------to statusrecord
        deps = Deployment.objects.filter(resource_id=resource_id).order_by('-created_time')
        if len(deps) > 0:
            dep = deps[0]
            deploy_id = dep.deploy_id
        else:
            dep = None
            deploy_id = None
        status_record = StatusRecord()
        status_record.res_id = resource_id
        status_record.s_type = "set"
        status_record.set_flag = set_flag
        status_record.created_time = datetime.datetime.now()
        if cloud == "2":
            if status == 'ok':
                if set_flag == "res":
                    status_record.status = "set_success"
                    status_record.msg = "%s资源创建成功" % mapping_msg_info.get(resource_type,resource_type)
                if set_flag in ["increase","reduce","config"]:
                    if resource_type == "app":
                        status_record.status = "%s_success" % set_flag
                        status_record.msg = "%s资源%s成功" % (mapping_msg_info.get(resource_type,resource_type),mapping_scale_info.get(set_flag,set_flag))
                        if dep:
                            dep.deploy_result = "%s_success" % set_flag
                    else:
                        status_record.status = "%s_success" % set_flag
                        status_record.msg = "%s资源%s成功" % (mapping_msg_info.get(resource_type,resource_type), mapping_scale_info.get(set_flag,set_flag))
                    status_record.deploy_id = deploy_id
                    if dep:
                        dep.save()
            else:
                if set_flag == "res":
                    status_record.status = "set_fail"
                    status_record.msg = "%s资源创建失败,错误日志为: %s" % (mapping_msg_info.get(resource_type,resource_type),error_msg)
                elif set_flag in ["increase","reduce","config"]:
                    status_record.status = "%s_fail" % set_flag
                    status_record.msg = "%s资源%s失败,错误日志为: %s" % (mapping_msg_info.get(resource_type,resource_type),mapping_scale_info.get(set_flag,set_flag),error_msg)
                    status_record.deploy_id = deploy_id
                    if dep:
                        dep.deploy_result = "%s_fail" % set_flag
                        dep.save()
        else:
            if status == 'ok':
                if set_flag == "res":
                    status_record.status = "set_success"
                    status_record.msg = "预留成功"
                if set_flag in ["increase","config"]:
                    status_record.status = "%s_success" % set_flag
                    status_record.msg = "%s资源%s成功" % (mapping_msg_info.get(resource_type,resource_type),mapping_scale_info.get(set_flag,set_flag))
                    status_record.deploy_id = deploy_id
            else:
                if set_flag == "res":
                    status_record.status = "set_fail"
                    status_record.msg = "预留失败,错误日志为: %s" % error_msg
                elif set_flag in ["increase","config"]:
                    status_record.status = "%s_fail" % set_flag
                    status_record.msg = "%s资源%s失败,错误日志为: %s" % (mapping_msg_info.get(resource_type,resource_type),mapping_scale_info.get(set_flag,set_flag),error_msg)
                    status_record.deploy_id = deploy_id
                    if dep:
                        dep.deploy_result = "%s_fail" % set_flag
                        dep.save()
        status_record.save()
        resource.reservation_status = status_record.status
        resource.save()
        if status == "ok":
            # 往vmstatus表里写入的数据
            cmdb_p_code = resource.cmdb_p_code
            filter_status_data(cmdb_p_code, "@", "@")
        # 判断是正常预留还是扩容set_flag=increase,扩容成功后 在nginx中添加扩容的docker
        if set_flag  == "increase" and status == 'ok':
            if cloud == '2' and resource_type == "app":
                pass
            else:
                CPR_URL = get_CRP_url(env)
                url = CPR_URL + "api/deploy/deploys"
                deploy_to_crp(resource_id, url, set_flag, cloud,increase_ips)


    # @api_permission_control(request)
    @classmethod
    def post(cls):
        code = 2002
        request_data = json.loads(request.data)
        try:
            cls.process_data(request_data)
        except Exception as e:
            Log.logger.exception("[UOP to CMDB1] Resource callback failed, Excepton: %s", e.args)
            code = 500
            ret = {
                'code': code,
                'result': {
                    'res': 'fail',
                    'msg': "Resource find error."
                }
            }
            return ret, code
        # async send email
        resource_id = request_data.get("resource_id")
        status = request_data.get('status')
        set_flag = request_data.get('set_flag')
        if status == "ok" and set_flag == "res":
            #其他资源创建成功，异步发邮件
            send_email_res(resource_id, '100')
        # 异步存到CMDB2
        Log.logger.info("Start save to CMDB2")
        CMDB_URL = current_app.config['CMDB_URL']
        crp_data_cmdb(request_data, CMDB_URL, 'POST')
        Log.logger.info("End save to CMDB2")

        res = {
            "code": code,
            "result": {
                "res": "success",
                "msg": "test info"
            }
        }
        return res, 200

    def put(self):
        request_data = json.loads(request.data)
        resource_id = request_data.get('resource_id')
        status = request_data.get('status')
        msg = request_data.get('msg')
        set_flag = request_data.get('set_flag')
        resource_type = request_data.get('resource_type')
        code = 200
        try:
            resource = ResourceModel.objects.get(res_id=resource_id)
            # 修改violume
            if set_flag == "config" and status == "success":
                resource_list = resource.resource_list
                os_ins_ip_list = resource.os_ins_ip_list
                for res in resource_list:
                    volume_size = res.volume_size
                    volume_exp_size = res.volume_exp_size
                    res.volume_size = volume_size + volume_exp_size
                    res.volume_exp_size = 0
                    res.save()
                #修改Statusvm表数据
                for res in resource_list:
                    volume_size = res.volume_size
                    cpu = res.cpu
                    mem = res.mem
                vms = Statusvm.objects.filter(resource_id=resource_id)
                for vm in vms:
                    vm.update(volume_size=str(volume_size) if volume_size else "0",
                              cpu=str(cpu) if cpu else "2",
                              mem=str(mem) if mem else "2")
                for os_ins in os_ins_ip_list:
                    os_ins.cpu = str(cpu) if cpu else "2"
                    os_ins.mem = str(mem) if mem else "2"
            status_record = StatusRecord()
            status_record.res_id = resource_id
            status_record.s_type = "config"
            status_record.set_flag = set_flag
            status_record.created_time = datetime.datetime.now()
            if status == "success":
                status_record.status = "config_success"
                status_record.msg = "%s资源配置成功" % resource_type
                # 异步更新到cmdb2
                res_data = ResourceModel.objects.filter(res_id=resource_id)
                CMDB_URL = current_app.config['CMDB_URL']
                Log.logger.info("Modify the configure result save to cmdb2 STARTED")
                if res_data:
                    origin_data = res_data[0]
                    crp_data_cmdb(origin_data, CMDB_URL, 'PUT', request_data)
                    Log.logger.info("Modify the configure result save to cmdb2 DOWN")
                else:
                    Log.logger.info("The resource is not exist!!!")
            else:
                status_record.status = "config_fail"
                status_record.msg = "%s资源配置失败，错误日志为：%s" % (resource_type,msg)
            status_record.save()
            resource.reservation_status = status_record.status
            resource.save()
        except Exception as e:
            Log.logger.error("[UOP] PUT resource callback  failed, Excepton: %s" % str(e))
            code = 500
            ret = {
                'code': code,
                'result': {
                    'res': 'fail',
                    'msg': "Resource put error.",
                }
            }
            return ret, code

        res = {
            "code": code,
            "result": {
                "res": "success",
                "msg": "Resource put success",
            }
        }
        return res, code







class ResourceStatusProviderCallBack(Resource):
    """
    资源预留状态记录回调
    """

    # @api_permission_control(request)
    @classmethod
    def post(cls):
        code = 200
        request_data = json.loads(request.data)
        instance = request_data.get('instance', '')
        db_push = request_data.get('db_push', '')
        set_flag = request_data.get('set_flag', '')
        war_dict = request_data.get('war_dict', '')
        build_image = request_data.get("build_image", '')
        push_image = request_data.get("push_image", '')
        git_package = request_data.get("git_package", '')
        try:
            status_record = StatusRecord()
            if instance:
                resource_id = instance.get('resource_id')
                os_inst_id = instance.get('os_inst_id', '')
                instance_type = instance.get('instance_type')
                quantity = int(instance.get('quantity', '0'))

                cur_instance_type = mapping_type_status.get(instance_type, instance_type)
                d_instance_type = mapping_type_status.get(instance_type, "other")
                deps = Deployment.objects.filter(resource_id=resource_id).order_by('-created_time')
                if len(deps) > 0:
                    dep = deps[0]
                    deploy_id = dep.deploy_id
                status_record = StatusRecord.objects.filter(res_id=resource_id,s_type=cur_instance_type,set_flag=set_flag)
                if status_record:
                    status_record=status_record[0]
                    cur_instance_type_list = getattr(status_record, d_instance_type)
                    if quantity > 1:
                        if len(cur_instance_type_list)==(quantity-1):
                            status_record.s_type=cur_instance_type
                            if set_flag == "res":
                                status_record.status = '%s_success'%(cur_instance_type)
                                status_record.msg='%s预留完成'%(cur_instance_type)
                            elif set_flag == "increase":
                                status_record.status = '%s_increase_reserving' % (cur_instance_type)
                                status_record.msg = '%s扩容中' % (cur_instance_type)
                                status_record.deploy_id=deploy_id
                            cur_instance_type_list.append(os_inst_id)
                        else:
                            cur_instance_type_list.append(os_inst_id)
                            if set_flag == "res":
                                status_record.status = '%s_reserving'%(cur_instance_type)
                                status_record.msg='%s预留中'%(cur_instance_type)
                            elif set_flag == "increase":
                                status_record.status = '%s_increase_reserving' % (cur_instance_type)
                                status_record.msg = '%s扩容中' % (cur_instance_type)
                                status_record.deploy_id = deploy_id
                            status_record.s_type=cur_instance_type

                else:
                    status_record = StatusRecord()
                    status_record.res_id = resource_id
                    if quantity > 1:
                        if set_flag == "res":
                            status_record.status = '%s_reserving'%(cur_instance_type)
                            status_record.msg='%s预留中'%(cur_instance_type)
                        elif set_flag == "increase":
                            status_record.status = '%s_increase_reserving' %(cur_instance_type)
                            status_record.msg = '%s扩容中' %(cur_instance_type)
                            status_record.deploy_id = deploy_id
                        cur_instance_type_list = [os_inst_id]
                        status_record.s_type=cur_instance_type
                    else:
                        if set_flag == "res":
                            status_record.status = '%s_success'%(cur_instance_type)
                            status_record.msg='%s预留完成'%(cur_instance_type)
                        elif set_flag == "increase":
                            status_record.status = '%s_increase_reserving' % (cur_instance_type)
                            status_record.msg = '%s扩容中' %(cur_instance_type)
                            status_record.deploy_id = deploy_id
                        cur_instance_type_list = [os_inst_id]
                        status_record.s_type=cur_instance_type
                setattr(status_record, d_instance_type, cur_instance_type_list)
            if db_push:
                resource_id = db_push.get('resource_id')
                cluster_type = db_push.get('cluster_type')
                status_record.res_id = resource_id
                status_record.s_type = cluster_type
                status_record.status = '%s_success'%(cluster_type)
                status_record.msg='%s配置推送完成'%(cluster_type)

            if war_dict:
                Log.logger.info("This is war to image operations")
                resource_id = war_dict.get('resource_id')
                war_to_image_status = war_dict.get('war_to_image_status')
                status_record.res_id = resource_id
                if war_to_image_status == "war_to_image_running":
                    status_record.status = war_to_image_status
                    status_record.msg = "war包转镜像进行中"
                elif war_to_image_status == "war_to_image_success":
                    status_record.status = war_to_image_status
                    status_record.msg = "war包转镜像完成"

                Log.logger.info("War to image operations successful")
            if build_image:
                Log.logger.info("This is build image progress")
                resource_id = build_image.get('resource_id')
                build_image_status = build_image.get('build_image_status')
                status_record.res_id = resource_id

                if build_image_status == "build_image_running":
                    status_record.status = build_image_status
                    status_record.msg = "镜像构建中"
                elif build_image_status == "build_image_success":
                    status_record.status = build_image_status
                    status_record.msg = "镜像构建完成"

                Log.logger.info("Build image successfully")
            if push_image:
                resource_id = push_image.get("resource_id")
                push_image_status = push_image.get("push_image_status")
                status_record.res_id = resource_id
                
                if push_image_status == "push_image_running":
                    status_record.status = push_image_status
                    status_record.msg = "推送镜像中"
                elif push_image_status == "push_image_success":
                    status_record.status = push_image_status
                    status_record.msg = "镜像推送完成"

            if git_package:
                Log.logger.info("Git Package successful")
                resource_id = git_package.get("resource_id")
                git_package_status = git_package.get("git_package_status")
                status_record.res_id = resource_id
                if git_package_status == "pull_code_success":
                    status_record.msg = "拉代码成功"
                elif git_package_status == "clone_branch_success":
                    status_record.msg = "克隆代码成功"
                elif git_package_status == "package_success":
                    status_record.msg = "构建包成功"
                elif git_package_status == "pull_or_clone_error":
                    status_record.msg = "拉代码或克隆失败"
                elif git_package_status == "package_error":
                    status_record.msg = "构建包失败"
            status_record.created_time = datetime.datetime.now()
            status_record.set_flag = set_flag
            status_record.save()
        except Exception as e:
            msg = traceback.format_exc()
            Log.logger.error("[UOP] Resource Status callback failed, Excepton: %s" % msg)
            code = 500
            ret = {
                'code': code,
                'result': {
                    'res': 'fail',
                    'msg': "Resource find error."
                }
            }
            return ret, code

        res = {
            "code": code,
            "result": {
                "res": "success",
                "msg": "test info"
            }
        }
        return res, code

    @classmethod
    # @api_permission_control(request)
    def get(cls):
        code = 200
        parser = reqparse.RequestParser()
        parser.add_argument('resource_id',location='args')
        args = parser.parse_args()
        resource_id=args.resource_id
        try:
            status_records = StatusRecord.objects.filter(res_id=resource_id).order_by('created_time')
            set_msg_list=[]
            dep_msg_list=[]
            data={}
            for sr in status_records:
                dep_id=sr.deploy_id
                if dep_id:
                    s_msg=sr.created_time.strftime('%Y-%m-%d %H:%M:%S') +':'+ sr.msg
                    dep_msg_list.append(s_msg)
                else:
                    s_msg=sr.created_time.strftime('%Y-%m-%d %H:%M:%S') +':'+ sr.msg
                    set_msg_list.append(s_msg)
            data["set"]=set_msg_list
            data["deploy"]=dep_msg_list
        except Exception as e:
            Log.logger.error("[UOP] Get resource  callback msg failed, Excepton: %s" % str(e.args))
            code = 500
            ret = {
                'code': code,
                'result': {
                    'res': 'fail',
                    'msg': "Resource find error.",
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
        return res, code


class ResourceDeleteCallBack(Resource):
    # @api_permission_control(request)
    def post(self):
        code = 200
        request_data = json.loads(request.data)
        resource_id = request_data.get('resource_id')
        os_inst_id = request_data.get('os_inst_id')
        unique_flag = request_data.get('unique_flag')
        del_os_ins_ip_list = request_data.get('del_os_ins_ip_list',[])
        set_flag = request_data.get('set_flag')
        status = request_data.get('status')
        del_msg = request_data.get('msg')
        status_list = []
        os_inst_ip_dict = {}
        try:
            resources = ResourceModel.objects.filter(res_id=resource_id,is_deleted=0)
            if resources:
                resource = resources[0]
                env = resource.env
                cloud = resource.cloud
                resource_type = resource.resource_type
                deps = Deployment.objects.filter(resource_id=resource_id).order_by('-created_time')
                if deps:
                    dep = deps[0]
                    deploy_id = dep.deploy_id
                else:
                    dep = None
                    deploy_id = None
                if status == "success":
                    msg = "删除资源成功,%s" % os_inst_id
                else:
                    msg = "删除资源失败，%s，%s" % (os_inst_id,del_msg)
                s_type = resource_type
                if resource_type == "app":
                    s_type = "docker"
                create_status_record(resource_id, deploy_id, s_type, msg, status, set_flag, unique_flag)
                status_records = StatusRecord.objects.filter(res_id=resource_id, unique_flag=unique_flag)
                for sd in status_records:
                    status = sd.status
                    status_list.append(status)
                del_count = len(del_os_ins_ip_list)
                if resource_type == "app" and cloud == "2":
                    del_count = 1
                # set_flag == "reduce" 存在说明是缩容不是正常删除
                if set_flag == "reduce":
                    compute_list=resource.compute_list
                    os_ins_list=resource.os_ins_list
                    os_ins_ip_list=resource.os_ins_ip_list
                    cmdb_p_code=resource.cmdb_p_code
                    new_compute_list = []
                    new_os_ins_list = []
                    new_os_ins_ip_list = []
                    #更新resource表中的数据，把要删除的数据删除
                    for os_ins_ip in os_ins_ip_list:
                        if os_ins_ip["os_ins_id"]  == os_inst_id:
                            ip=os_ins_ip["ip"]
                            os_inst_ip_dict[os_inst_id]=ip
                        else:
                            new_os_ins_ip_list.append(os_ins_ip)
                    for os_ins_id in os_ins_list:
                        if os_ins_id !=os_inst_id:
                            new_os_ins_list.append(os_ins_id)
                    for compute in compute_list:
                        ips=compute.ips
                        quantity=compute.quantity
                        ip=os_inst_ip_dict[os_inst_id]
                        if ip in ips:
                            ips.remove(ip)
                            quantity = quantity - 1
                        compute.ips=ips
                        compute.quantity=quantity
                        new_compute_list.append(compute)
                    resource.compute_list=new_compute_list
                    resource.os_ins_list=new_os_ins_list
                    resource.os_ins_ip_list=new_os_ins_ip_list
                    resource.save()
                    if len(status_records) == del_count and "fail" not in status_list:
                        #create_status_record(resource_id, deploy_id, "reduce", "资源缩容成功", "reduce_success",set_flag)
                        # 要缩容的资源都删除完成,开始删除nginx配置
                        CPR_URL = get_CRP_url(env)
                        url = CPR_URL + "api/deploy/deploys"
                        deploy_to_crp(resource_id,url,set_flag,cloud)
                        #要缩容的资源都删除完成,开始调用cmdb接口删除对应数据
                        data={}
                        ip_list=[]
                        osid_list=[]
                        for ip_ins in del_os_ins_ip_list:
                            ip=ip_ins["ip"]
                            os_id=ip_ins["os_ins_id"]
                            ip_list.append(ip)
                            osid_list.append(os_id)
                        data["p_code"]=cmdb_p_code
                        data["ip_list"]=ip_list
                        data["osid_list"] = osid_list
                        data_str=json.dumps(data)
                        dirty = Statusvm.objects.filter(osid__in=osid_list)
                        if dirty:
                            for d in dirty:
                                d.delete()
                        CMDB_URL = current_app.config['CMDB_URL']
                        if CMDB_URL:
                            CMDB_DEL_URL = CMDB_URL + 'cmdb/api/scale/'
                            headers = {'Content-Type': 'application/json', }
                            Log.logger.debug("Data args is " + str(data))
                            result = requests.delete(url=CMDB_DEL_URL, headers=headers, data=data_str)
                            result = json.dumps(result.json())
                            Log.logger.debug(result)
                    elif len(status_records) == del_count and "fail" in status_list:
                        resource.update(reservation_status="reduce_fail")
                        dep.update(deploy_result="delete_fail")
                # set_flag == "res" 存在说明是正常删除
                elif set_flag == "res":
                    if len(status_records) == del_count and "fail" not in status_list:
                        cmdb_p_code = resource.cmdb_p_code
                        resource.update(is_deleted=1,deleted_date=datetime.datetime.now(),reservation_status="delete_success")
                        for dep in deps:
                            dep.update(deploy_result="delete_success")
                        # 回写CMDB
                        delete_cmdb1(cmdb_p_code)
                        delete_uop(resource_id)
                        delete_cmdb2(resource_id)
                    elif len(status_records) == del_count and "fail" in status_list:
                        resource.reservation_status = "delete_fail"
                        resource.save()
                        if dep:
                            dep.update(deploy_result="delete_fail")
        except Exception as e:
            Log.logger.error("[UOP] Delete resource callback  failed, Excepton: %s" % str(e))
            code = 500
            ret = {
                'code': code,
                'result': {
                    'res': 'fail',
                    'msg': "Resource delete error.",
                }
            }
            return ret, code

        res = {
            "code": code,
            "result": {
                "res": "success",
                "msg": "Resource delete success",
            }
        }
        return res, code


res_callback_api.add_resource(ResourceProviderCallBack, '/res')
res_callback_api.add_resource(ResourceDeleteCallBack, '/delete')
res_callback_api.add_resource(ResourceStatusProviderCallBack, '/status')
