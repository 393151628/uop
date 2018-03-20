# -*- coding: utf-8 -*-
import requests
from flask import current_app
from uop.models import  ResourceModel, ComputeIns,Deployment
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


def deploy_to_crp(deploy_item, environment, database_password, appinfo,
                  disconf_server_info):
    res_obj = ResourceModel.objects.get(res_id=deploy_item.resource_id)
    data = {
        "deploy_id": deploy_item.deploy_id,
        "appinfo": appinfo,
        "disconf_server_info": disconf_server_info,
        "deploy_type": "deploy",
        "dns": [],
        "environment": environment,
        "cloud":res_obj.cloud,
        "resource_name":res_obj.resource_name,
        "project_name": res_obj.project_name
    }
    if appinfo:  # 判断nginx信息，没有则不推送dns配置
        for app_info in res_obj.compute_list:
            dns_info = {'domain': app_info.domain,
                        'domain_ip': app_info.domain_ip
                        }
            data['dns'].append(dns_info)
    compute_list = res_obj.compute_list
    docker_list = []
    for compute in compute_list:
        try:
            docker_list.append(
                {
                    'url': compute.url,
                    'insname': compute.ins_name,
                    'ip': compute.ips,
                    'health_check':compute.health_check,
                    'host_env':compute.host_env,
                    'language_env':compute.language_env,
                    'deploy_source':compute.deploy_source,
                    'database_config':compute.database_config
                }
            )
        except AttributeError as e:
            Log.logger.error("Deploy to crp get docker info error {e}".format(e=str(e)))
    data['docker'] = docker_list
    #获取数据库信息
    database_info = get_database_info(res_obj.project_name,database_password)
    mysql = database_info.get("mysql")
    mongodb = database_info.get("mongodb")
    data["mysql"] = mysql
    data["mongodb"] = mongodb
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
        Log.logger.debug("{}  {}".format(url, json.dumps(headers)))
        data_str = json.dumps(data)
        Log.logger.debug("Data args is " + str(data))
        Log.logger.debug("Data args is " + str(data_str))
        result = requests.post(url=url, headers=headers, data=data_str)
        result = json.dumps(result.json())
    except requests.exceptions.ConnectionError as rq:
        err_msg = str(rq)
        Log.logger.error("deploy to crp error {err_msg}".format(err_msg=err_msg))
    except BaseException as e:
        err_msg = str(e)
        Log.logger.error("deploy to crp error {err_msg}".format(err_msg=err_msg))
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
                                 url=match_one.get("url",""), domain=match_one.get("domain", ""), quantity=o.quantity, port=match_one.get("port", ""),
                                 docker_meta=o.docker_meta, domain_ip=match_one.get("domain_ip", ""),
                                 health_check=match_one.get("health_check", 0),capacity_list=o.capacity_list,
                                 network_id=o.network_id,networkName=o.networkName,tenantName=o.tenantName,
                                 host_env=o.host_env,language_env=o.language_env,deploy_source=o.deploy_source,database_config=match_one.get("database_config"))
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


def deal_disconf_info(deploy_obj):
    """
    处理disconf的相关信息
    :param deploy_obj:
    :return:
    """
    disconf_server_info = []
    try:
        for disconf_info in deploy_obj.disconf_list:
            if (len(disconf_info.disconf_name.strip()) == 0) or (len(disconf_info.disconf_content.strip()) == 0):
                continue
            else:
                server_info = {'disconf_server_name': disconf_info.disconf_server_name,
                           'disconf_server_url': disconf_info.disconf_server_url,
                           'disconf_server_user': disconf_info.disconf_server_user,
                           'disconf_server_password': disconf_info.disconf_server_password,
                           'disconf_admin_content': disconf_info.disconf_admin_content,
                           'disconf_content': disconf_info.disconf_content,
                           'disconf_env': disconf_info.disconf_env,
                           'disconf_version': disconf_info.disconf_version,
                           'ins_name': disconf_info.ins_name,
                           'disconf_app_name': disconf_info.disconf_app_name,
                           }
                disconf_server_info.append(server_info)
    except Exception as e:
        Log.logger.error("deal disconf info error %s" % str(e))
    return disconf_server_info


def check_domain_port(resource,app_image):
    try:
        compute_list=resource.compute_list
        for compute in compute_list:
            for app in app_image:
                if compute.ins_id == app.get("ins_id"):
                    app["o_domain"] = compute.domain
                    app["o_port"] = compute.port
                    if compute.domain != app.get("domain"):
                        if compute.domain:
                            app["ingress_flag"] = "update"
                        else:
                            app["ingress_flag"] = "create"
                        if not app.get("domain") and compute.domain:
                            app["ingress_flag"] = "delete"
    except Exception as e:
        Log.logger.error("Check domain port error {e}".format(e=str(e)))
    return app_image


def get_database_info(project_name,database_password):
    database_info={}
    mysql = {}
    mongodb={}
    try:
        ip_list = []
        resources_app = ResourceModel.objects.filter(project_name=project_name,resource_type__in = ["app","kvm"])
        for res in resources_app:
            compute_list = res.compute_list
            for compute in compute_list:
                ips = compute.ips
                ip_list.extend(ips)
        resources_mysql = ResourceModel.objects.filter(project_name=project_name,resource_type = "mysql")
        if resources_mysql:
            resource_mysql = resources_mysql[0]
            mysql["ip"] = resource_mysql.vip
            mysql["port"] = resource_mysql.port
            mysql["database_user"] = project_name
            mysql["database_password"] = database_password
            mysql["ips"] = ip_list
            mysql["database"] = "mysql"
        resources_mongodb = ResourceModel.objects.filter(project_name=project_name, resource_type="mongodb")
        if resources_mongodb:
            resource_mongodb = resources_mongodb[0]
            mongodb["vip"] = resource_mongodb.vip
            mongodb["port"] = resource_mongodb.port
            mongodb["db_username"] = project_name
            mongodb["db_password"] = database_password
            mongodb["ips"] = ip_list
            mysql["database"] = "mongodb"
            database_info["mysql"] = mysql
            database_info["mongodb"] = mongodb
    except Exception as e:
        err_msg = "Uop get database info error {e}".format(e=str(e))
        Log.logger.error(err_msg)
    return database_info

