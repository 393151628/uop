# -*- coding: utf-8 -*-

from flask import current_app
import IPy
import time
import requests
import json
from uop.models import NetWorkConfig,PermissionList,RoleInfo
import threading
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class ApiPermException(Exception):
    pass

def async(fun):
    def wraps(*args, **kwargs):
        thread = threading.Thread(target=fun, args=args, kwargs=kwargs)
        thread.daemon = False
        thread.start()
        return thread
    return wraps



def get_CRP_url(env=None):
    if env:
        CPR_URL = current_app.config['CRP_URL'][env]
    else:
        CPR_URL = current_app.config['CRP_URL']['dev']
    return CPR_URL

def get_network_used(env, sub_network, vlan_id):
    sub_networks = sub_network.split(',')
    total_count = 0
    sub_networks = sub_networks[0:1]
    for net in sub_networks:
        ip = IPy.IP(net)
        _count = ip.len()
        total_count = total_count + _count
    headers = {'Content-Type': 'application/json'}
    env_ = get_CRP_url(env)
    crp_url = '%s%s'%(env_, 'api/openstack/port/count')
    data = {'network_id': vlan_id}
    data_str = json.dumps(data)
    cur_res = requests.get(crp_url, data=data_str,  headers=headers)
    cur_res = json.loads(cur_res.content)
    count = 0
    if cur_res.get('code') == 200:
        count = cur_res.get('result').get('res')
    return count, total_count


def check_network_use(env):
    networks = NetWorkConfig.objects.filter(env=env)
    headers = {'Content-Type': 'application/json'}
    network_id = ''
    for network in networks:
        vlan_id = network.vlan_id
        sub_network = network.sub_network
        ip = IPy.IP(sub_network)
        total_count = ip.len()
        env_ = get_CRP_url(env)
        crp_url = '%s%s'%(env_, 'api/openstack/port/count')
        data = {'network_id': vlan_id}
        data_str = json.dumps(data)
        cur_res = requests.get(crp_url, data=data_str,  headers=headers)
        cur_res = json.loads(cur_res.content)
        if cur_res.get('code') == 200:
            count = cur_res.get('result').get('res')
            if total_count > int(count):
                network_id = vlan_id
                break
    return network_id


class TimeToolkit(object):
    @staticmethod
    def utctimestamp2str(utctimestamp):
        utcs = float(utctimestamp) / 1000
        time_array = time.localtime(utcs)
        utc_time = time.strftime("%Y-%m-%d %H:%M:%S", time_array)
        datetime_time = datetime.strptime(utc_time, "%Y-%m-%d %H:%M:%S")
        _localtime = datetime_time + timedelta(hours=8)
        localtime = datetime.strftime(_localtime, "%Y-%m-%d %H:%M:%S")

        return localtime

    @staticmethod
    def utctimestamp2local(utctimestamp):
        utcs = long(utctimestamp) / 1000
        time_array = time.localtime(utcs)
        utc_time = time.strftime("%Y-%m-%d %H:%M:%S", time_array)
        datetime_time = datetime.strptime(utc_time, "%Y-%m-%d %H:%M:%S")
        localtime = datetime_time + timedelta(hours=8)

        return localtime

    @staticmethod
    def timestramp2local(timestrap):
        _timestrap = long(timestrap)
        time_array = time.localtime(_timestrap)
        utc_time = time.strftime("%Y-%m-%d %H:%M:%S", time_array)
        datetime_time = datetime.strptime(utc_time, "%Y-%m-%d %H:%M:%S")

        return datetime_time

    @staticmethod
    def get_utc_milli_ts():
        return long(time.mktime(datetime.utcnow().timetuple())) * 1000

    @staticmethod
    def local2utctimestamp(dt, duration=None, flag=None):
        if duration:
            delta = dt + relativedelta(months=int(duration))
        else:
            delta = dt
        print delta
        if flag:
            utc_delta = delta
        else:
            utc_delta = delta + timedelta(hours=-8)
        print utc_delta
        utc_delta_tuple = utc_delta.timetuple()
        print utc_delta_tuple
        utc_timestramp = long(time.mktime(utc_delta_tuple))
        return utc_timestramp


def response_data(code, msg, data):
    ret = {
        'code': code,
        'result': {
            'msg': msg,
            'data': data,
        }
    }
    return ret


def deal_enbedded_data(data):
    res_list=[]
    for d in data:
        d=d.to_json()
        d=json.loads(d)
        res_list.append(d)
    return res_list

def get_api_permission():
    """
    #获取角色API权限
    :return:
    """
    try:
        api_all_perm={}
        Roles=RoleInfo.objects.all()
        for Role in Roles:
            api_role_perm={}
            api_endpoint_perm={}
            Permissions=PermissionList.objects.filter(perm_type="api",role=Role.name)
            for permission in Permissions:
                api_method_perm={}
                role=permission.role
                endpoint=permission.endpoint
                api_get=permission.api_get
                api_post=permission.api_post
                api_put=permission.api_put
                api_delete=permission.api_delete
                api_method_perm["GET"] = api_get
                api_method_perm["POST"] = api_post
                api_method_perm["PUT"] = api_put
                api_method_perm["DELETE"] = api_delete
                api_endpoint_perm[endpoint] = api_method_perm
                api_role_perm[role] = api_endpoint_perm
            #将全新加入到api_all_perm所有权限
            api_all_perm = dict(api_all_perm,** api_role_perm)
        return api_all_perm
    except Exception as e:
        err_msg = "Get api permission error,error msg is %s" % str(e)
        raise ApiPermException(err_msg)