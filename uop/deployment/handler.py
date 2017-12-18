# -*- coding: utf-8 -*-
import requests
from flask import current_app
from uop.models import  ResourceModel, ComputeIns
from uop.disconf.disconf_api import *
from uop.util import get_CRP_url
from uop.log import Log


__all__ = [
    "format_resource_info","get_resource_by_id_mult",
    "get_resource_by_id","deploy_to_crp",
    "upload_files_to_crp","upload_disconf_files_to_crp",
    "disconf_write_to_file", "attach_domain_ip"
]

def format_resource_info(items):
    resource_info = {}
    for item in items.get('items'):
        colunm = {}
        for i in item.get('column'):
            if i.get('p_code') is not None:
                colunm[i.get('p_code')] = i.get('value')
        if item.get('item_id') == "docker":
            if colunm.get('ip_address', '127.0.0.1') == "172.28.36.44":
                Log.logger.info("####items:{}".format(items))
            resource_info.setdefault('docker', []).append({'ip_address': colunm.get('ip_address', '127.0.0.1')})
        else:
            resource_info[item.get('item_id')] = {
                'user': colunm.get('username', 'root'),
                'password': colunm.get('password', '123456'),
                'port': colunm.get('port', '3306'),
            }
            if item.get('item_id') == 'mysql_cluster':
                resource_info[item.get('item_id')]['wvip'] = colunm.get('mysql_cluster_wvip', '127.0.0.1')
                resource_info[item.get('item_id')]['rvip'] = colunm.get('mysql_cluster_rvip', '127.0.0.1')
            elif item.get('item_id') == 'mongodb_cluster':
                resource_info[item.get('item_id')]['vip1'] = colunm.get('mongodb_cluster_ip1', '127.0.0.1')
                resource_info[item.get('item_id')]['vip2'] = colunm.get('mongodb_cluster_ip2', '127.0.0.1')
                resource_info[item.get('item_id')]['vip3'] = colunm.get('mongodb_cluster_ip3', '127.0.0.1')
            elif item.get('item_id') == 'redis_cluster':
                resource_info[item.get('item_id')]['vip'] = colunm.get('redis_cluster_vip', '127.0.0.1')
            elif item.get('item_id') == 'mongodb_instance':
                resource_info[item.get('item_id')]['vip'] = colunm.get('ip_address', '127.0.0.1')
    # Log.logger.info("####resource_info:{}".format(resource_info))
    return resource_info


def get_resource_by_id_mult(p_codes):
    CMDB_URL = current_app.config['CMDB_URL']
    url = CMDB_URL + 'cmdb/a' \
                     'pi/repo_relation/'
    headers = {'Content-Type': 'application/json'}
    data = {
        'layer_count': 3,
        'total_count': 50,
        'reference_sequence': [{'child': 2}, {'bond': 1}],
        'item_filter': ['docker', 'mongodb_cluster', 'mysql_cluster', 'redis_cluster', 'mongodb_instance'],
        'columns_filter': {
            'mysql_cluster': ['mysql_cluster_wvip', 'mysql_cluster_rvip', 'username', 'password', 'port'],
            'mongodb_cluster': ['mongodb_cluster_ip1', 'mongodb_cluster_ip2', 'mongodb_cluster_ip3', 'username',
                                'password', 'port'],
            'mongodb_instance': ['ip_address', 'username', 'password', 'port'],
            'redis_cluster': ['redis_cluster_vip', 'username', 'password', 'port'],
            'docker': ['ip_address', 'username', 'password', 'port'],
        },
        'p_codes': p_codes
    }
    data_str = json.dumps(data)
    err_msg = None
    try:
        result = requests.post(url, headers=headers, data=data_str)
        # Log.logger.info("@@@@result:{}".format(result.json()))
    except requests.exceptions.ConnectionError as rq:
        err_msg = rq.message
    except Exception as e:
        err_msg = e.message
    if err_msg:
        return False, err_msg

    result = result.json()
    data = result.get('result', {}).get('res', {})
    code = result.get('code', -1)
    if code == 2002:
        resources_dic = {}
        for p_code, items in data.items():
            resource_info = format_resource_info(items)
            resources_dic[p_code] = resource_info

        return True, resources_dic
    else:
        return False, None


def get_resource_by_id(resource_id):
    err_msg = None
    resource_info = {}
    resources = ResourceModel.objects.filter(res_id=resource_id)
    if resources:
        resource = resources[0]
    try:
        headers = {'Content-Type': 'application/json'}
        data = {
            'layer_count': 1000,
            'total_count': 5000,
            'reference_type': ["dependent"],
            'reference_sequence': [{'child': 3}, {'bond': 2}, {'parent': 5}],
            'item_filter': ['docker', 'mongodb_cluster', 'mysql_cluster', 'redis_cluster', 'mongodb_instance'],
            'columns_filter': {
                'mysql_cluster': ['mysql_cluster_wvip', 'mysql_cluster_rvip', 'username', 'password', 'port'],
                'mongodb_cluster': ['mongodb_cluster_ip1', 'mongodb_cluster_ip2', 'mongodb_cluster_ip3', 'username',
                                    'password', 'port', 'ip_address'],
                'mongodb_instance': ['ip_address', 'username', 'password', 'port', "dbtype"],
                'redis_cluster': ['redis_cluster_vip', 'username', 'password', 'port'],
                'docker': ['ip_address', 'username', 'password', 'port'],
            },
        }
        data_str = json.dumps(data)
        CMDB_URL = current_app.config['CMDB_URL']
        url = CMDB_URL + 'cmdb/api/repo_relation/' + resource.cmdb_p_code + '/'
        Log.logger.debug('UOP get_db_info: url is %(url)s, data is %(data)s', {'url': url, 'data': data})

        result = requests.get(url, headers=headers, data=data_str)
        result = result.json()
        data = result.get('result', {}).get('res', {})
        code = result.get('code', -1)
        Log.logger.info('data: ' + json.dumps(result))
    except requests.exceptions.ConnectionError as rq:
        err_msg = rq.message.message
    except BaseException as e:
        err_msg = e.message
    else:
        if code == 2002:
            resource_info = format_resource_info(data)
        else:
            err_msg = 'resource(' + resource_id + ') not found.'

    Log.logger.debug('UOP get_db_info: resource_info is %(ri)s', {'ri': resource_info})
    return err_msg, resource_info


def deploy_to_crp(deploy_item, environment, resource_info, resource_name, database_password, appinfo,
                  disconf_server_info):
    res_obj = ResourceModel.objects.get(res_id=deploy_item.resource_id)
    data = {
        "deploy_id": deploy_item.deploy_id,
        "appinfo": appinfo,
        "disconf_server_info": disconf_server_info,
        "deploy_type": "deploy",
        "dns": [],
        "environment": environment,
    }
    if appinfo:  # 判断nginx信息，没有则不推送dns配置
        for app_info in res_obj.compute_list:
            dns_info = {'domain': app_info.domain,
                        'domain_ip': app_info.domain_ip
                        }
            data['dns'].append(dns_info)

    if resource_info.get('mysql_cluster'):
        data['mysql'] = {
            "ip": resource_info['mysql_cluster']['wvip'],
            "port": resource_info['mysql_cluster']['port'],
            "database_user": resource_name,
            "database_password": database_password,
            "mysql_user": resource_info['mysql_cluster']['user'],
            "mysql_password": resource_info['mysql_cluster']['password'],
            "database": "mysql",
        }
    if resource_info.get('mongodb_cluster'):
        data['mongodb'] = {
            "vip1": resource_info['mongodb_cluster']['vip1'],
            "vip2": resource_info['mongodb_cluster']['vip2'],
            "vip3": resource_info['mongodb_cluster']['vip3'],
            "vip": resource_info['mongodb_instance']['vip'],
            "port": resource_info['mongodb_cluster']['port'],
            # TODO test data
            "db_username": resource_name,
            "db_password": database_password,
            # "db_username": 'victor',
            # "db_password": '123456',
            "mongodb_username": resource_info['mongodb_cluster']['user'],
            "mongodb_password": resource_info['mongodb_cluster']['password'],
            "database": "mongodb",
        }
    if resource_info.get('docker'):
        # data['docker'] = {
        #     "image_url": deploy_item.app_image,
        #     "ip": resource_info['docker']['ip_address']
        # }
        docker_list = []
        for obj in res_obj.compute_list:
            try:
                docker_list.append(
                    {
                        'url': obj.url,
                        'ins_name': obj.ins_name,
                        'ip': obj.ips,
                        'health_check':obj.health_check
                    }
                )
            except AttributeError as e:
                Log.logger.error(str(e))
        data['docker'] = docker_list

    err_msg = None
    result = None
    try:
        CPR_URL = get_CRP_url(res_obj['env'])
        url = CPR_URL + "api/deploy/deploys"
        headers = {
            'Content-Type': 'application/json',
        }
        # 上传disconf配置文件
        upload_disconf_files_to_crp(disconf_info_list=disconf_server_info, env=res_obj['env'])

        file_paths = []
        if deploy_item.mysql_context:
            file_paths.append(('mysql', deploy_item.mysql_context))
        if deploy_item.redis_context:
            file_paths.append(('redis', deploy_item.redis_context))
        if deploy_item.mongodb_context:
            file_paths.append(('mongodb', deploy_item.mongodb_context))

        if file_paths:
            res = upload_files_to_crp(file_paths, res_obj['env'])
            cont = json.loads(res.content)
            if cont.get('code') == 200:
                for type, path_filename in cont['file_info'].items():
                    data[type]['path_filename'] = path_filename
            elif cont.get('code') == 500:
                return 'upload sql file failed', result
        Log.logger.info("{}  {}".format(url, json.dumps(headers)))
        data_str = json.dumps(data)
        Log.logger.debug("Data args is " + str(data))
        Log.logger.debug("Data args is " + str(data_str))
        result = requests.post(url=url, headers=headers, data=data_str)
        result = json.dumps(result.json())
    except requests.exceptions.ConnectionError as rq:
        err_msg = rq.message.message
    except BaseException as e:
        err_msg = e.message

    return err_msg, result


def upload_files_to_crp(file_paths, env):
    CPR_URL = get_CRP_url(env)
    url = CPR_URL + "api/deploy/upload"
    files = []
    for db_type, path in file_paths:
        files.append((db_type, open(path, 'rb')))

    if files:
        data = {'action': 'upload'}
        result = requests.post(url=url, files=files, data=data)
        return result
    else:
        return {'code': -1}


def upload_disconf_files_to_crp(disconf_info_list, env):
    """
    上传disconf文件到crp
    :param disconf_info:
    :param env:
    :return:
    """
    CPR_URL = get_CRP_url(env)
    url = CPR_URL + "api/deploy/upload"
    try:
        res = []
        for disconf_info in disconf_info_list:
            disconf_type = 'disconf'
            disconf_admin_content = disconf_info.get('disconf_admin_content', '')
            disconf_content = disconf_info.get('disconf_content', '')
            if len(disconf_admin_content.strip()) == 0 and len(disconf_content.strip()) == 0:
                continue
            else:
                if len(disconf_admin_content.strip()) != 0:
                    if os.path.exists(disconf_admin_content):
                        data = dict(
                            type=disconf_type,
                            disconf_file_path=disconf_admin_content,
                        )
                        files = {'file': open(disconf_admin_content, 'rb')}
                        result = requests.post(url=url, files=files, data=data)

                    else:
                        raise ServerError('disconf admin file does not exist')
                else:
                    if os.path.exists(disconf_content):
                        data = dict(
                            type=disconf_type,
                            disconf_file_path=disconf_content,
                        )
                        files = {'file': open(disconf_content, 'rb')}
                        result = requests.post(url=url, files=files, data=data)
                    else:
                        raise ServerError('disconf content file does not exist')
                res.append(result)
        return res
    except Exception as e:
        raise ServerError(e.args)


def disconf_write_to_file(file_name, file_content, instance_name, type):
    try:
        if (len(file_name) == 0) and (len(file_content) == 0):
            upload_file = ''
        elif (len(file_name) == 0) and (len(file_content) != 0):
            raise ServerError('disconf name can not be null.')
        elif (len(file_name) != 0) and (len(file_content) == 0):
            raise ServerError('disconf content can not be null.')
        else:
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], type, instance_name)
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
            upload_file = os.path.join(upload_dir, file_name)
            with open(upload_file, 'wb') as f:
                f.write(file_content)
    except Exception as e:
        raise ServerError(e.message)
    return upload_file


def attach_domain_ip(compute_list, res, cmdb_url):
    old_compute_list = res.compute_list
    os_ins_list = res.os_ins_ip_list
    appinfo = []
    cmdb_data = []
    try:
        for i in old_compute_list:
            tmp = [x for x in compute_list if str(x["ins_id"]) == str(i.ins_id) and x.get("domain_ip", "")]
            if len(tmp) > 0:
                tmp = tmp[0]
                tmp["ips"] = i.ips
                tmp["osid"] = []
                for os_ins in os_ins_list:
                    if os_ins.ip in tmp["ips"]:
                        tmp["osid"].append(os_ins.os_ins_id)  # 传给crp
                cmdb_data.append({"osid": tmp["osid"], "domain": tmp["domain"], "domain_ip": tmp["domain_ip"]})
                appinfo.append(tmp)  # 将配置了nginx IP的 app传回，以便传回crp进行配置推送
        for i in xrange(0, len(old_compute_list)):  # 更新resources表中的镜像url和可能配置nginx IP信息
            match_one = filter(lambda x: x["ins_id"] == old_compute_list[i].ins_id, compute_list)[0]
            o = old_compute_list[i]
            old_compute_list.remove(old_compute_list[i])
            compute = ComputeIns(ins_name=o.ins_name, ips=o.ips, ins_id=o.ins_id, cpu=o.cpu, mem=o.mem,
                                 url=match_one["url"], domain=o.domain, quantity=o.quantity, port=o.port,
                                 docker_meta=o.docker_meta, domain_ip=match_one.get("domain_ip", ""),
                                 health_check=match_one.get("health_check", 0),capacity_list=o.capacity_list)
            old_compute_list.insert(i, compute)
            res.save()
        if cmdb_url:
            Log.logger.info("$$$$$$$$ Push domain info to cmdb stashvm")
            data = {"osid_domain": cmdb_data}
            # CMDB_URL = current_app.config['CMDB_URL']
            url = cmdb_url + 'cmdb/api/vmdocker/status/'
            ret = requests.put(url, data=json.dumps(data))
            if ret.json()["code"] == 2002:
                Log.logger.info("$$$$$$$$ Push domain info to cmdb stashvm, success")
            else:
                Log.logger.info("$$$$$$$$ Push domain info to cmdb stashvm: {}".format(ret.json()))
        return appinfo
    except Exception as e:
        Log.logger.error("attach domain_ip to appinfo error:{}".format(e.args))
        return appinfo
