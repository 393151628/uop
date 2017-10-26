# -*- coding: utf-8 -*-

import logging
import re
from flask_restful import reqparse, Api, Resource, fields
import requests
from uop.configure import configure_blueprint
from uop.models import ConfigureEnvModel 
from uop.models import ConfigureNginxModel 
from uop.models import ConfigureDisconfModel 
from uop.models import NetWorkConfig
from uop.util import get_CRP_url
configure_api = Api(configure_blueprint)


class ConfigureEnv(Resource):

    @classmethod
    def get(cls):
        ret = ConfigureEnvModel.objects.all()
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

class Configure(Resource):

    @classmethod
    def get(cls):
        parser = reqparse.RequestParser()
        parser.add_argument('env', type=str)
        parser.add_argument('category', type=str)
        args = parser.parse_args()
        category = parser.parse_args()
        env = args.env if args.env else 'dev'
        category = args.category if args.category else 'nginx'
        logging.info("[UOP] Get configs, env:%s, category: %s", env, category)
        envs = []
        #nets = []
        if category == 'nginx':
            ret = ConfigureNginxModel.objects.filter(env=env)
            for env in ret: 
                envs.append(dict(id=env.id, 
                                 name=env.name,
                                 ip=env.ip))
        elif category == 'network':
            ret = NetWorkConfig.objects.filter(env=env)
            for net in ret:
                envs.append(dict(id=net.id,
                                 name=net.name,
                                 sub_network=net.sub_network,
                                 vlan_id=net.vlan_id))
        else: # disconf
            ret = ConfigureDisconfModel.objects.filter(env=env)
            for env in ret: 
                envs.append(dict(id=env.id, 
                                 name=env.name,
                                 username=env.username,
                                 password=env.password,
                                 ip=env.ip,
                                 url=env.url))
        res = {
                'code': 200,
                'result': {
                    'res': envs,
                    'msg': u'请求成功'
                    }
                }
        return res

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
        args = parser.parse_args()
        env = args.env if args.env else 'dev'
        url = args.url if args.url else ''
        ip = args.ip if args.ip else ''
        name = args.name if args.name else ''
        username = args.username if args.username else 'dev'
        password = args.password if args.password else 'dev'
        category = args.category if args.category else 'nginx'
        sub_network = args.sub_network if args.sub_network else ''
        vlan_id = args.vlan_id if args.vlan_id else ''
        logging.info("[UOP] Create configs, env:%s, category: %s", env, category)
        import uuid
        id = str(uuid.uuid1())
        if category == 'nginx':
            ret = ConfigureNginxModel(env=env,
                                     ip=ip,
                                     name=name,
                                     id=id).save()
        elif category == 'network':
            ret = NetWorkConfig(env=env,
                               name=name,
                               sub_network=sub_network,
                               vlan_id=vlan_id,
                               id=id).save()
        else:
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

        args = parser.parse_args()
        category = parser.parse_args()
        env = args.env if args.env else 'dev'
        id = args.id if args.id else ''
        url = args.url if args.url else ''
        ip = args.ip if args.ip else ''
        name = args.name if args.name else ''
        category = args.category if args.category else 'nginx'
        username = args.username if args.username else ''
        password = args.password if args.password else ''
        sub_network = args.sub_network if args.sub_network else ''
        vlan_id = args.vlan_id.strip() if args.vlan_id else ''
        logging.info("[UOP] Modify configs, env:%s, category: %s", env, category)

        if category == 'nginx':
            ret = ConfigureNginxModel.objects(id=id)
            ret.update(name=name,ip=ip)
        elif category == 'network':
            ret = NetWorkConfig.objects(id=id)
            ret.update(name=name,sub_network=sub_network, vlan_id=vlan_id)
        else:
            ret = ConfigureDisconfModel.objects(id=id)
            ret.update(name=name,url=url,ip=ip,username=username,password=password)

        res = {
                'code': 200,
                'result': {
                    'msg': u'请求成功'
                    }
                }
        return res

    @classmethod
    def delete(cls):
        parser = reqparse.RequestParser()
        parser.add_argument('env', type=str)
        parser.add_argument('category', type=str)
        parser.add_argument('id', type=str)
        args = parser.parse_args()
        category = parser.parse_args()
        env = args.env if args.env else 'dev'
        category = args.category if args.category else 'nginx'
        id = args.id if args.id else -1 
        logging.info("[UOP] Delete configs, env:%s, category: %s, id: %s", env, category, id)


        if category == 'nginx':
            ret = ConfigureNginxModel.objects.filter(id=id)
        elif category == 'network':
            ret = NetWorkConfig.objects.filter(id=id)
        else:
            ret = ConfigureDisconfModel.objects.filter(id=id)
        if len(ret):
            ret.delete()
        else:
            logging.info("[UOP] Do not found the item, id:%s", id)

        res = {
                'code': 200,
                'result': {
                    'msg': u'请求成功'
                    }
                }
        return res

class ConfigureNetwork(Resource):
    def fuzzyfinder(self,keywords, collection):
        suggestions = []
        pattern = '.*'.join(keywords)
        regex = re.compile(pattern) 
        for item in collection:
            match = regex.search(item)
            if match:
                suggestions.append((match.start(), item))
        return [x for _, x in suggestions]    

    def get(self):
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('keywords', type=str)
            parser.add_argument('env', type=str)
            args = parser.parse_args()
            keywords=args.keywords
            env_=args.env
            network_list=[]
            CRP_URL = get_CRP_url(env_)
            headers = {'Content-Type': 'application/json'}
            url_ = '%s%s'%(CRP_URL, 'api/openstack/network/list')
            result = requests.get(url_, headers=headers)
            networks=result.json().get('result').get('res')
            if keywords:
                fuzzy_res={}
                network_names=self.fuzzyfinder(keywords, networks.keys())
                for name in network_names:
                    fuzzy_res[name]=networks[name]
                networks=fuzzy_res
            for name,info in networks.items():
                network_info={}
                network_info["vlan_name"]=name
                network_info["vlan_id"]=info[0]
                network_info["subnets"]=info[1]
                network_list.append(network_info)
        except Exception as e:
            err_msg = e.args
            logging.error('Uop get network list err: %s' % err_msg)
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
        


configure_api.add_resource(ConfigureEnv, '/env')
configure_api.add_resource(Configure, '/')
configure_api.add_resource(ConfigureNetwork, '/network')
