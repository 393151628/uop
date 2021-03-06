# -*- coding: utf-8 -*-
import re
import datetime
import json
from collections import defaultdict
from flask_restful import reqparse, Api, Resource, fields, marshal
import requests
from flask import request
from uop.configure import configure_blueprint
from uop.configure.handler import fuzzyfinder
from uop.models import ConfigureEnvModel
from uop.models import ConfigureNginxModel
from uop.models import ConfigureDisconfModel
from uop.models import NetWorkConfig,ConfigureK8sModel,ConfOpenstackModel,ConfigureNamedModel
from uop.util import get_CRP_url,response_data
from uop.log import Log
from uop.permission.handler import api_permission_control

configure_api = Api(configure_blueprint)


class ConfigureEnv(Resource):
    # @api_permission_control(request)
    @classmethod
    def get(cls):
        ret = ConfigureEnvModel.objects.all().order_by("-ordering")
        envs = []
        for env in ret:
            envs.append(dict(id=env.id,
                             name=env.name))
        res = {
            'code': 200,
            'result': {
                'res': envs,
                'msg': u'请求成功'
            }
        }
        return res


class ConfigureV2(Resource):
    nginx_fields = {
        "id": fields.String,
        "env": fields.String,
        "name": fields.String,
        "nginx_type": fields.String,
        "ip": fields.String,
        "port": fields.String
    }

    network_fields = {
        "id": fields.String,
        "env": fields.String,
        "name": fields.String,
        "sub_network": fields.String,
        "vlan_id": fields.String,
        "networkName": fields.String,
        "tenantName": fields.String,
        "cloud": fields.String,
    }

    k8s_fields = {
        "id": fields.String,
        "env": fields.String,
        "namespace_name": fields.String,
        "config_map_name": fields.String,
        "network_url": fields.String,
    }


    label_fields = {
        "id": fields.String,
        "env": fields.String,
        "scheduler_zone": fields.String,
    }

    openstack_fields = {
        "id": fields.String,
        "env": fields.String,
        "image_id": fields.String,
        "image_name": fields.String,
        "image_type": fields.String,
        "port": fields.String,
        "flavor_name": fields.String,
        "flavor_id": fields.String,
        "flavor_cpu": fields.String,
        "flavor_memory": fields.Integer,
        "flavor_type": fields.String,
        "cloud": fields.String,
        "availability_zone": fields.String,
    }

    named_fields = {
        "id": fields.String,
        "env": fields.String,
        "name": fields.String,
        "url": fields.String,
    }

    disconf_fields = {
        "id": fields.String,
        "env": fields.String,
        "name": fields.String,
        "username": fields.String,
        "password": fields.String,
        "ip": fields.String,
        "url": fields.String,
    }

    @classmethod
    def get(cls):
        parser = reqparse.RequestParser()
        parser.add_argument('env', type=str,location="args")
        args = parser.parse_args()
        env = args.env if args.env else 'dev'
        Log.logger.info("[UOP] Get configs, env:%s", env)

        # result = defaultdict(list)
        keys = ['k8s_nginx', 'nginx', 'network', 'namespace',
                'k8s_network_url', 'image', 'flavor', 'scheduler_zone',
                'availability_zone', 'namedmanager', 'disconf']
        result = {key: [] for key in keys}

        for obj in ConfigureNginxModel.objects.filter(env=env):
            tmp_data = marshal(obj, cls.nginx_fields)
            if obj.nginx_type == 'k8s':
                result['k8s_nginx'].append(tmp_data)
            else:
                result['nginx'].append(tmp_data)

        for obj in NetWorkConfig.objects.filter(env=env):
            result['network'].append(marshal(obj, cls.network_fields))

        for obj in ConfigureK8sModel.objects.filter(env=env):
            # scheduler_zone
            if obj.scheduler_zone:
                result['scheduler_zone'].append(marshal(obj, cls.label_fields))

            # namespace
            tmp_data = marshal(obj, cls.k8s_fields)
            if obj.namespace_name:
                result['namespace'].append(tmp_data)
            if obj.network_url:
                tmp_data['url'] = tmp_data.pop('network_url', None)
                result['k8s_network_url'].append(tmp_data)

        for obj in ConfOpenstackModel.objects.filter(env=env):
            tmp_data = marshal(obj, cls.openstack_fields)
            if obj.image_name:
                result['image'].append(tmp_data)
            if obj.flavor_name:
                result['flavor'].append(tmp_data)
            if obj.availability_zone:
                result['availability_zone'].append(tmp_data)

        for obj in ConfigureNamedModel.objects.filter(
            env=env).order_by("-create_time"):
            if  obj.name:
                result['namedmanager'].append(marshal(obj, cls.named_fields))

        for obj in ConfigureDisconfModel.objects.filter(env=env):
            result['disconf'].append(marshal(obj, cls.disconf_fields))
                
        res = {
            'code': 200,
            'result': {
                'res': result,
                'msg': u'请求成功'
            }
        }
        return res


class Configure(Resource):
    # @api_permission_control(request)
    @classmethod
    def get(cls):
        parser = reqparse.RequestParser()
        parser.add_argument('env', type=str,location="args")
        parser.add_argument('category', type=str,location="args")
        args = parser.parse_args()
        env = args.env if args.env else 'dev'
        category = args.category
        Log.logger.info("[UOP] Get configs, env:%s, category: %s", env, category)
        results = []
        # nets = []
        if category == 'nginx':
            ret = ConfigureNginxModel.objects.filter(env=env)
            for env in ret:
                if not env.nginx_type:
                    results.append(dict(id=env.id,
                                    name=env.name,
                                    ip=env.ip))
        elif category == 'k8s_nginx':
            ret = ConfigureNginxModel.objects.filter(env=env)
            for env in ret:
                if env.nginx_type == "k8s":
                    results.append(dict(id=env.id,
                                        name=env.name,
                                        ip=env.ip,
                                        nginx_type=env.nginx_type,
                                        port=env.port))
        elif category in ['network','k8s_network']:
            ret = NetWorkConfig.objects.filter(env=env)
            for net in ret:
                results.append(dict(id=net.id,
                                 name=net.name,
                                 sub_network=net.sub_network,
                                 vlan_id=net.vlan_id,
                                 tenantName=net.tenantName,
                                 networkName=net.networkName,
                                 cloud = net.cloud))
        elif category == 'namespace':
            ret = ConfigureK8sModel.objects.filter(env=env)
            for net in ret:
                if net.namespace_name:
                    results.append(dict(id=net.id,
                                 namespace_name=net.namespace_name,
                                 config_map_name=net.config_map_name,
                                 env = net.env,
                                ))
        elif category =="image":
            ret = ConfOpenstackModel.objects.filter(env=env)
            for net in ret:
                if net.image_name:
                    results.append(dict(
                        id = net.id,
                        port = net.port,
                        image_id = net.image_id,
                        image_name = net.image_name,
                        image_type = net.image_type,
                        cloud = net.cloud,
                        env = net.env,
                    ))
        elif category == "flavor":
            ret = ConfOpenstackModel.objects.filter(env=env)
            for net in ret:
                if net.flavor_name:
                    results.append(dict(
                        id = net.id,
                        flavor_id = net.flavor_id,
                        flavor_name = net.flavor_name,
                        flavor_type = net.flavor_type,
                        flavor_cpu = net.flavor_cpu,
                        flavor_memory = net.flavor_memory,
                        cloud = net.cloud,
                        env = net.env,
                    ))
        elif category == "availability_zone":
            ret = ConfOpenstackModel.objects.filter(env=env)
            for net in ret:
                if net.availability_zone:
                    results.append(dict(
                        id=net.id,
                        availability_zone = net.availability_zone,
                        cloud=net.cloud,
                        env=net.env,
                    ))
        elif category == "namedmanager":
            ret = ConfigureNamedModel.objects.filter(env=env).order_by("-create_time")
            for net in ret:
                if net.name:
                    results.append(dict(
                        id = net.id,
                        name=net.name,
                        url=net.url,
                        env=net.env,
                    ))
        elif category == "k8s_network_url":
            ret = ConfigureK8sModel.objects.filter(env=env)
            for net in ret:
                if net.network_url:
                    results.append(dict(id=net.id,
                                    url=net.network_url,
                                    env=net.env,
                                    ))
        elif category == "scheduler_zone":
            ret = ConfigureK8sModel.objects.filter(env=env)
            for sz in ret:
                if sz.scheduler_zone:
                    results.append(dict(id=sz.id,
                                    scheduler_zone=sz.scheduler_zone,
                                    env=sz.env,
                                    ))

        else:  # disconf
            ret = ConfigureDisconfModel.objects.filter(env=env)
            for env in ret:
                results.append(dict(id=env.id,
                                 name=env.name,
                                 username=env.username,
                                 password=env.password,
                                 ip=env.ip,
                                 url=env.url))
        res = {
            'code': 200,
            'result': {
                'res': results,
                'msg': u'请求成功'
            }
        }
        return res

    # @api_permission_control(request)
    @classmethod
    def post(cls):
        parser = reqparse.RequestParser()
        parser.add_argument('env', type=str)
        parser.add_argument('category', type=str)
        parser.add_argument('url', type=str)
        parser.add_argument('ip', type=str)
        parser.add_argument('name', type=str)
        parser.add_argument('username', type=str)
        parser.add_argument('password', type=str)
        parser.add_argument('sub_network', type=str)
        parser.add_argument('vlan_id', type=str)
        parser.add_argument('networkName', type=str)
        parser.add_argument('tenantName', type=str)
        parser.add_argument('namespace_name', type=str)
        parser.add_argument('config_map_name', type=str)
        parser.add_argument('cloud', type=str)
        parser.add_argument('image_id', type=str)
        parser.add_argument('image_name', type=str)
        parser.add_argument('image_type', type=str)
        parser.add_argument('flavor_id', type=str)
        parser.add_argument('flavor_name', type=str)
        parser.add_argument('flavor_type', type=str)
        parser.add_argument('flavor_cpu', type=int)
        parser.add_argument('flavor_memory', type=int)
        parser.add_argument('nginx_type', type=str)
        parser.add_argument('port', type=str)
        parser.add_argument('availability_zone', type=str)
        parser.add_argument('scheduler_zone', type=str)
        args = parser.parse_args()
        env = args.env if args.env else 'dev'
        url = args.url if args.url else ''
        ip = args.ip if args.ip else ''
        name = args.name if args.name else ''
        username = args.username if args.username else 'dev'
        password = args.password if args.password else 'dev'
        category = args.category
        sub_network = args.sub_network if args.sub_network else ''
        vlan_id = args.vlan_id if args.vlan_id else ''
        networkName = args.networkName if args.networkName else ''
        tenantName = args.tenantName if args.tenantName else ''
        namespace_name = args.namespace_name if args.namespace_name else ''
        config_map_name = args.config_map_name if args.config_map_name else ''
        cloud = args.cloud if args.cloud else '2'
        scheduler_zone = args.scheduler_zone if args.scheduler_zone else ''
        Log.logger.info("[UOP] Create configs, env:%s, category: %s", env, category)
        import uuid
        id = str(uuid.uuid1())
        if category == 'nginx':
            ret = ConfigureNginxModel(env=env,
                                      ip=ip,
                                      name=name,
                                      id=id,
                                      nginx_type=args.nginx_type,
                                      port=args.port).save()
        elif category in ['network','k8s_network']:
            ret = NetWorkConfig(env=env,
                                name=name,
                                sub_network=sub_network,
                                vlan_id=vlan_id,
                                tenantName=tenantName,
                                networkName=networkName,
                                id=id,
                                cloud = cloud).save()
        elif category == "namespace":
            ret = ConfigureK8sModel(
                id = id,
                env = env,
                namespace_name = namespace_name,
                config_map_name = config_map_name,
            ).save()
        elif category == "scheduler_zone":
            ret = ConfigureK8sModel(
                id = id,
                env = env,
                scheduler_zone = scheduler_zone,
            ).save()
        elif category == "image":
            ret = ConfOpenstackModel(
                id=id,
                port = args.port,
                image_id=args.image_id,
                image_name=args.image_name,
                image_type=args.image_type,
                cloud=cloud,env=env).save()
        elif category == "flavor":
            ret = ConfOpenstackModel(id=id,
                                   flavor_id=args.flavor_id,
                                   flavor_name=args.flavor_name,
                                   flavor_type=args.flavor_type,
                                   flavor_cpu=args.flavor_cpu,
                                   flavor_memory=args.flavor_memory,
                                   cloud=cloud,env=env).save()
        elif category == "availability_zone":
            ret = ConfOpenstackModel(id=id,
                                     availability_zone=args.availability_zone,
                                     cloud=cloud,
                                     env=env).save()
        elif category == "namedmanager":
            ret = ConfigureNamedModel(id=id,name=name,env=env,url=url,create_time=datetime.datetime.now()).save()
        elif category == "k8s_network_url":
            ret = ConfigureK8sModel(id=id, env=env, network_url=url).save()
        else:#disconf
            ret = ConfigureDisconfModel(env=env,
                                        url=url,
                                        ip=ip,
                                        name=name,
                                        username=username,
                                        password=password,
                                        id=id).save()
        res = {
            'code': 200,
            'result': {
                'res': id,
                'msg': u'请求成功'
            }
        }
        return res

    # @api_permission_control(request)
    @classmethod
    def put(cls):
        parser = reqparse.RequestParser()
        parser.add_argument('env', type=str)
        parser.add_argument('category', type=str)
        parser.add_argument('url', type=str)
        parser.add_argument('ip', type=str)
        parser.add_argument('name', type=str)
        parser.add_argument('username', type=str)
        parser.add_argument('password', type=str)
        parser.add_argument('id', type=str)
        parser.add_argument('sub_network', type=str)
        parser.add_argument('vlan_id', type=str)
        parser.add_argument('networkName', type=str)
        parser.add_argument('tenantName', type=str)
        parser.add_argument('namespace_name', type=str)
        parser.add_argument('config_map_name', type=str)
        parser.add_argument('cloud', type=str)
        parser.add_argument('image_id', type=str)
        parser.add_argument('image_name', type=str)
        parser.add_argument('image_type', type=str)
        parser.add_argument('flavor_id', type=str)
        parser.add_argument('flavor_name', type=str)
        parser.add_argument('flavor_type', type=str)
        parser.add_argument('flavor_cpu', type=int)
        parser.add_argument('flavor_memory', type=int)
        parser.add_argument('nginx_type', type=str)
        parser.add_argument('port', type=str)
        parser.add_argument('availability_zone', type=str)
        parser.add_argument('scheduler_zone', type=str)
        args = parser.parse_args()
        env = args.env if args.env else 'dev'
        id = args.id if args.id else ''
        url = args.url if args.url else ''
        ip = args.ip if args.ip else ''
        name = args.name if args.name else ''
        category = args.category
        username = args.username if args.username else ''
        password = args.password if args.password else ''
        sub_network = args.sub_network if args.sub_network else ''
        vlan_id = args.vlan_id.strip() if args.vlan_id else ''
        networkName = args.networkName if args.networkName else ''
        tenantName = args.tenantName if args.tenantName else ''
        namespace_name = args.namespace_name if args.namespace_name else ''
        config_map_name = args.config_map_name if args.config_map_name else ''
        cloud = args.cloud if args.cloud else '2'
        scheduler_zone = args.scheduler_zone if args.scheduler_zone else ''
        Log.logger.info("[UOP] Modify configs, env:%s, category: %s,args: %s", env, category,args)

        if category == 'nginx':
            ret = ConfigureNginxModel.objects(id=id)
            ret.update(name=name,ip=ip,nginx_type=args.nginx_type,port=args.port,env=env)
        elif category in ['network','k8s_network']:
            ret = NetWorkConfig.objects(id=id)
            ret.update(name=name, sub_network=sub_network, vlan_id=vlan_id,networkName=networkName,tenantName=tenantName,cloud=cloud)
        elif category == "namespace":
            ret = ConfigureK8sModel.objects(id = id)
            ret.update(env=env,namespace_name=namespace_name,config_map_name=config_map_name)
        elif category == "scheduler_zone":
            ret = ConfigureK8sModel.objects(id = id)
            ret.update(env=env, scheduler_zone=scheduler_zone)
        elif category == "image":
            ret = ConfOpenstackModel.objects(id=id)
            ret.update(image_id=args.image_id,
                image_name=args.image_name,
                image_type=args.image_type,
                port = args.port,
                cloud=cloud,
                env=env)
        elif category == "flavor":
            ret = ConfOpenstackModel.objects(id=id)
            ret.update(flavor_id=args.flavor_id,
                    flavor_name=args.flavor_name,
                    flavor_type=args.flavor_type,
                    flavor_cpu=args.flavor_cpu,
                    flavor_memory=args.flavor_memory,
                    cloud=cloud,
                    env=env)
        elif category == "availability_zone":
            ret = ConfOpenstackModel.objects(id=id)
            ret.update(availability_zone=args.availability_zone, cloud=cloud, env=env)
        elif category == "namedmanager":
            ret = ConfigureNamedModel.objects(id=id)
            ret.update(name=name,env=env,url=url)
        elif category == "k8s_network_url":
            ret = ConfigureK8sModel.objects(id=id)
            ret.update(env=env, network_url=url)

        else:
            ret = ConfigureDisconfModel.objects(id=id)
            ret.update(name=name, url=url, ip=ip, username=username, password=password)

        res = {
            'code': 200,
            'result': {
                'msg': u'请求成功'
            }
        }
        return res

    # @api_permission_control(request)
    @classmethod
    def delete(cls):
        parser = reqparse.RequestParser()
        parser.add_argument('env', type=str)
        parser.add_argument('category', type=str)
        parser.add_argument('id', type=str)
        args = parser.parse_args()
        env = args.env if args.env else 'dev'
        category = args.category
        id = args.id if args.id else -1
        Log.logger.info("[UOP] Delete configs, env:%s, category: %s, id: %s", env, category, id)
        if category == 'nginx':
            ret = ConfigureNginxModel.objects.filter(id=id)
        elif category  in ['network','k8s_network']:
            ret = NetWorkConfig.objects.filter(id=id)
        elif category in ["namespace","k8s_network_url", "scheduler_zone"]:
            ret = ConfigureK8sModel.objects.filter(id=id)
        elif category in ["image","flavor","availability_zone"]:
            ret = ConfOpenstackModel.objects.filter(id=id)
        elif category == "namedmanager":
            ret = ConfigureNamedModel.objects.filter(id=id)
        else:
            ret = ConfigureDisconfModel.objects.filter(id=id)
        if len(ret):
            ret.delete()
        else:
            Log.logger.info("[UOP] Do not found the item, id:%s", id)

        res = {
            'code': 200,
            'result': {
                'msg': u'请求成功'
            }
        }
        return res


class ConfigureNetwork(Resource):
    # @api_permission_control(request)
    def get(self):
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('keywords', type=str)
            parser.add_argument('env', type=str)
            args = parser.parse_args()
            keywords = args.keywords
            env_ = args.env
            network_list = []
            CRP_URL = get_CRP_url(env_)
            headers = {'Content-Type': 'application/json'}
            url_ = '%s%s' % (CRP_URL, 'api/openstack/network/list')
            result = requests.get(url_, headers=headers)
            networks = result.json().get('result').get('res')
            if keywords:
                fuzzy_res = {}
                network_names = fuzzyfinder(keywords, networks.keys())
                for name in network_names:
                    fuzzy_res[name] = networks[name]
                networks = fuzzy_res
            for name, info in networks.items():
                network_info = {}
                network_info["vlan_name"] = name
                network_info["vlan_id"] = info[0]
                network_info["subnets"] = info[1]
                network_info["cloud"] = info[2]
                network_list.append(network_info)
        except Exception as e:
            err_msg = str(e)
            Log.logger.error('Uop get network list err: %s' % err_msg)
            ret = {
                "code": 400,
                "result": {
                    "msg": "failed",
                    "res": err_msg
                }
            }
            return ret, 400
        else:
            ret = {
                "code": 200,
                "result": {
                    "msg": "success",
                    "res": network_list
                }
            }
            return ret, 200

class K8sNetworkApi(Resource):
    # @api_permission_control(request)
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('env', type=str, location="args")
        args = parser.parse_args()
        env = args.env
        data={}
        res_list=[]
        err_msg = None
        try:
            nets = ConfigureK8sModel.objects.filter(env=env)
            for net in nets:
                if net.network_url:
                    network_url=net.network_url
                    url=get_CRP_url(env)+'api/openstack/k8s/network?env=%s&url=%s' %(env,network_url)
                    result = requests.get(url)
                    code=result.json().get('code')
                    if code == 200:
                        result_list= result.json().get('result')['data']['res_list']
                        for r in result_list:
                            res={}
                            res["networkName"] = r.get("networkName")
                            res["tenantName"] = r.get("tenantName")
                            res_list.append(res)
                    else:
                        err_msg = result.json().get('result')['msg']
            if not err_msg:
                msg = "Get k8s network info success"
                code = 200
            else:
                msg = err_msg
                code = 400
            data["res_list"] = res_list
        except Exception as e:
            code = 500
            data = "Error"
            msg = "Get k8s network info error %s" % str(e)
            Log.logger.error(msg)
        ret = response_data(code, msg, data)
        return ret, code

class K8sNamespaceManage(Resource):

    def post(self):

        parser = reqparse.RequestParser()
        parser.add_argument('namespace_name', type=str, location="json")
        parser.add_argument('config_map_name', type=str, location="json")
        parser.add_argument('config_map_info', type=str, location="json")
        parser.add_argument('env', type=str, location="json")
        args = parser.parse_args()
        env = args.env
        namespace_name = args.namespace_name
        config_map_name = args.config_map_name
        config_map_info = args.config_map_info
        data={}
        try:
            url = get_CRP_url(env) + 'api/openstack/k8s/namespace'
            data["namespace_name"] = namespace_name
            if config_map_name:
                config_map_data = {}
                data["config_map_name"] = config_map_name
                config_map_data["filebeat.yml"] = config_map_info
                data["config_map_data"] = config_map_data
            headers = {'Content-Type': 'application/json'}
            data_str = json.dumps(data)
            result = requests.post(url=url,data=data_str,headers=headers)
            code = result.json().get('code')
            msg = result.json().get('result')["msg"]
            data = result.json().get('result')["data"]
        except Exception as e:
            code = 500
            data = "Error"
            msg = "create k8s namespace error {e}".format(e=str(e))
            Log.logger.error(msg)
        ret = response_data(code, msg, data)
        return ret, code

    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('env', type=str, location="args")
        args = parser.parse_args()
        env = args.env
        data = {}
        res_list = []
        try:
            url = get_CRP_url(env) + 'api/openstack/k8s/namespace'
            result = requests.get(url)
            code = result.json().get('code')
            if code == 200:
                res_list = result.json().get('result')['data']['res_list']
            msg = result.json().get('result')['msg']
            data["res_list"] = res_list
        except Exception as e:
            code = 500
            data = "Error"
            msg = "Get k8s namespace info error {e}".format(e=str(e))
            Log.logger.error(msg)
        ret = response_data(code, msg, data)
        return ret, code



class ConfigureImage(Resource):
    # @api_permission_control(request)
    def get(self):
        data = {}
        res_list = []
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('env', type=str)
            args = parser.parse_args()
            env_ = args.env
            CRP_URL = get_CRP_url(env_)
            headers = {'Content-Type': 'application/json'}
            url_ = '%s%s' % (CRP_URL, 'api/image/images')
            result = requests.get(url_, headers=headers)
            code = result.json().get('code')
            msg = result.json().get('result').get('msg')
            if code == 200:
                images = result.json().get('result').get('res')
                for image in images:
                    res = {}
                    res["image_id"] = image.get("id")
                    res["image_name"] = image.get("image_name")
                    res["cloud"] = image.get("cloud")
                    res_list.append(res)
            data["res_list"] = res_list
        except Exception as e:
            code = 500
            data = "Errot"
            msg = 'Uop get image list err: %s' % str(e)
            Log.logger.error(msg)
        ret = response_data(code, msg, data)
        return ret, code


class ConfigureFlavor(Resource):
    # @api_permission_control(request)
    def get(self):
        data = {}
        res_list = []
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('env', type=str)
            args = parser.parse_args()
            env_ = args.env
            CRP_URL = get_CRP_url(env_)
            headers = {'Content-Type': 'application/json'}
            url_ = '%s%s' % (CRP_URL, 'api/flavor/flavors')
            result = requests.get(url_, headers=headers)
            code = result.json().get('code')
            msg = result.json().get('result').get('msg')
            if code == 200:
                flavors = result.json().get('result').get('res')
                for flavor in flavors:
                    res = {}
                    res["flavor_id"] = flavor.get("flavor_id")
                    res["flavor_name"] = flavor.get("flavor_name")
                    res["flavor_cpu"] = flavor.get("cpu")
                    res["memory"] = flavor.get("memory")
                    res["cloud"] = flavor.get("cloud")
                    res_list.append(res)
            data["res_list"] = res_list
        except Exception as e:
            code = 500
            data = "Errot"
            msg = 'Uop get flavor list err: %s' % str(e)
            Log.logger.error(msg)
        ret = response_data(code, msg, data)
        return ret, code





configure_api.add_resource(ConfigureEnv, '/env')
configure_api.add_resource(Configure, '/')
configure_api.add_resource(ConfigureV2, '/v2')
configure_api.add_resource(ConfigureNetwork, '/network')
configure_api.add_resource(K8sNetworkApi, '/k8s/networks')
configure_api.add_resource(K8sNamespaceManage, '/k8s/namespace')
configure_api.add_resource(ConfigureImage, '/images')
configure_api.add_resource(ConfigureFlavor, '/flavors')
