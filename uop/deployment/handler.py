# -*- coding: utf-8 -*-
import requests
from flask import current_app
from uop.models import  ResourceModel, ComputeIns,Deployment,ConfigureNginxModel,DisconfIns
from uop.disconf.disconf_api import *
from uop.util import get_CRP_url
from uop.log import Log
import uuid
import datetime
from config import configs, APP_ENV

__all__ = [
    "format_resource_info","get_resource_by_id_mult",
    "get_resource_by_id","deploy_to_crp",
    "upload_files_to_crp","upload_disconf_files_to_crp",
    "disconf_write_to_file", "attach_domain_ip"
]
UPLOAD_FOLDER = current_app.config['UPLOAD_FOLDER']
K8S_NGINX_PORT = configs[APP_ENV].K8S_NGINX_PORT
K8S_NGINX_IPS = configs[APP_ENV].K8S_NGINX_IPS

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
    resources = ResourceModel.objects.filter(res_id=resource_id,is_deleted=0)
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
                  disconf_server_info,deploy_type,deploy_name=None):
    resource_id = deploy_item.resource_id
    res_obj = ResourceModel.objects.get(res_id=resource_id)
    data = {
        "deploy_id": deploy_item.deploy_id,
        "appinfo": appinfo,
        "disconf_server_info": disconf_server_info,
        "deploy_type": deploy_type,
        "dns": [],
        "environment": environment,
        "cloud":res_obj.cloud,
        "resource_name":res_obj.resource_name,
        "project_name": res_obj.project_name,
        "resource_id": resource_id,
        "deploy_name": deploy_name,
    }
    compute_list = res_obj.compute_list
    if compute_list:
        compute = compute_list[0]
        namespace = compute.namespace
        if namespace:
            data["namespace"] = namespace
    if appinfo:  # 判断nginx信息，没有则不推送dns配置
        for compute in compute_list:
            dns_info = {'domain': compute.domain,
                        'domain_ip': compute.domain_ip,
                        'certificate': compute.certificate,
                        'named_url': compute.named_url,
                        }
            data['dns'].append(dns_info)
    docker_list = []
    for compute in compute_list:
        try:
            url = compute.url
            host_env = compute.host_env
            deploy_source = compute.deploy_source
            if compute.deploy_source == "git" and deploy_type in ["rollback","increase","reduce"]:
                url = compute.git_res_url
                deploy_source = "war"
            docker_list.append(
                {
                    'url': url,
                    'insname': compute.ins_name,
                    'ip': compute.ips,
                    'health_check':compute.health_check,
                    'host_env':host_env,
                    'language_env':compute.language_env,
                    'deploy_source':deploy_source,
                    'database_config':compute.database_config,
                    'flavor':str(compute.cpu) + str(compute.mem),
                    'host_mapping':compute.host_mapping,
                    'networkName':compute.networkName,
                    'tenantName':compute.tenantName,
                    'replicas': compute.quantity,
                    'ready_probe_path':compute.ready_probe_path,
                    'port': compute.port,
                    'pom_path': compute.pom_path,
                    'branch': compute.branch,
                    'scheduler_zone': compute.scheduler_zone,
                }
            )
        except AttributeError as e:
            Log.logger.error("Deploy to crp get docker info error {e}".format(e=str(e)))
    data['docker'] = docker_list
    #获取数据库信息
    database_info = get_database_info(res_obj,database_password)
    Log.logger.debug("#####uop database info {}".format(database_info))
    if database_info:
        db_type = database_info["database"]
        data[db_type] = database_info
    err_msg = None
    result = None
    try:
        CPR_URL = get_CRP_url(res_obj['env'])
        crp_url = CPR_URL + "api/deploy/deploys"
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
                    if data.get(type):
                        data[type]['path_filename'] = path_filename
            elif cont.get('code') == 500:
                return 'upload sql file failed', result
        Log.logger.debug("{}  {}".format(crp_url, json.dumps(headers)))
        data_str = json.dumps(data)
        Log.logger.debug("Data args is " + str(data))
        Log.logger.debug("Data args is " + str(data_str))
        result = requests.post(url=crp_url, headers=headers, data=data_str)
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
            host_mapping=match_one.get("host_mapping",[])
            if not isinstance(host_mapping,list):
                host_mapping=eval(host_mapping)
                host_mapping = json.dumps(host_mapping)
            else:
                host_mapping = json.dumps(host_mapping)
            #modles.ComputeIns 字段变更时这里也要变
            compute = ComputeIns(ins_name=o.ins_name, ips=o.ips, ins_id=o.ins_id, cpu=match_one.get("cpu","2"), mem=match_one.get("mem","2"), certificate=match_one.get("certificate", ""),
                                 url=match_one.get("url",""), domain=match_one.get("domain", ""), quantity=o.quantity, port=match_one.get("port"),
                                 docker_meta=o.docker_meta, domain_ip=match_one.get("domain_ip", ""),
                                 health_check=match_one.get("health_check", 0),capacity_list=o.capacity_list,
                                 network_id=o.network_id,networkName=match_one.get("networkName"),tenantName=match_one.get("tenantName"),
                                 host_env=o.host_env,language_env=match_one.get("language_env","java7"),deploy_source=o.deploy_source,database_config=match_one.get("database_config"),
                                 ready_probe_path=match_one.get("ready_probe_path"),lb_methods=match_one.get("lb_methods"),namespace=o.namespace,domain_path=match_one.get("domain_path"),
                                 host_mapping=host_mapping,named_url=match_one.get("named_url"),availability_zone=o.availability_zone,image_id=o.image_id,flavor_id=o.flavor_id,
                                 pom_path=match_one.get("pom_path"),branch=match_one.get("branch"),git_res_url = o.git_res_url,scheduler_zone=match_one.get("scheduler_zone"))
            old_compute_list.insert(i, compute)
            domain = match_one.get("domain", "")
            res.domain = domain
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
        Log.logger.error("attach domain_ip to appinfo error:{}".format(str(e)))
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
        deps = Deployment.objects.filter(resource_id=resource.res_id)
        cloud = resource.cloud
        resource_type = resource.resource_type
        for compute in compute_list:
            for app in app_image:
                if compute.ins_id == app.get("ins_id"):
                    app["o_domain"] = compute.domain
                    app["o_port"] = compute.port
                    if deps.__len__() == 0 and compute.domain:
                        app["is_nginx"] = 1
                    if compute.domain != app.get("domain") or compute.domain_path != app.get("domain_path") or compute.port != app.get("port,"):
                        if compute.domain or compute.domain_path or compute.port:
                            app["ingress_flag"] = "update"
                            app["is_nginx"] = 1
                        elif not compute.domain and app.get("domain"):
                            app["ingress_flag"] = "create"
                            app["is_nginx"] = 1
                        if not app.get("domain") and compute.domain:
                            app["ingress_flag"] = "delete"
                            app["is_nginx"] = 1
                    if  not (cloud == "2" and resource_type == "app"):
                        app["ingress_flag"] = ""

    except Exception as e:
        Log.logger.error("Check domain port error {e}".format(e=str(e)))
    return app_image


def get_database_info(resource,database_password):
    database_info={}
    try:
        os_ins_ip_list=resource.os_ins_ip_list
        project_name = resource.project_name
        resource_type = resource.resource_type
        for os_ins in os_ins_ip_list:
            port = os_ins.port
            vip = os_ins.vip
            wvip = os_ins.wvip
            ip = wvip if wvip else vip
        database_info["ip"] = ip
        database_info["port"] = port
        database_info["database_user"] = "uop"+ project_name[:5]
        database_info["database_password"] = database_password
        database_info["database"] = resource_type
    except Exception as e:
        pass
    return database_info


def get_k8s_nginx(env):
    nginx_info={}
    nginx_ips=[]
    try:
        nginxs=ConfigureNginxModel.objects.filter(env=env,nginx_type="k8s")
        for ng in nginxs:
            nginx_port = ng.port
            nginx_ips.append(ng.ip)
        nginx_info["nginx_ips"] = nginx_ips
        nginx_info["nginx_port"] = nginx_port
    except Exception as e:
        err_msg = "Uop get nginx info error {e}".format(e=str(e))
        Log.logger.error(err_msg)
    return nginx_info


def write_file(uid, context, type):
    path = os.path.join(UPLOAD_FOLDER, type, 'script_' + uid)
    with open(path, 'wb') as f:
        f.write(context)
    return path


def admin_approve_allow(args):
    dep_id = args.dep_id
    # 管理员审批通过后修改resource表deploy_name,更新当前版本
    resource = ResourceModel.objects.get(res_id=args.resource_id)
    cloud = resource.cloud
    project_name = resource.project_name
    resource_type = resource.resource_type
    resource.deploy_name = args.deploy_name
    resource.updated_date = datetime.datetime.now()
    resource.save()
    # disconf配置
    # 1、将disconf信息更新到数据库
    deploy_obj = Deployment.objects.get(deploy_id=dep_id)
    for instance_info in args.disconf:
        for disconf_info_front in instance_info.get('dislist'):
            disconf_id = disconf_info_front.get('disconf_id')
            for disconf_info in deploy_obj.disconf_list:
                if disconf_info.disconf_id == disconf_id:
                    disconf_info.disconf_admin_content = disconf_info_front.get('disconf_admin_content')
                    disconf_info.disconf_server_name = disconf_info_front.get('disconf_server_name')
                    disconf_info.disconf_server_url = disconf_info_front.get('disconf_server_url')
                    disconf_info.disconf_server_user = disconf_info_front.get('disconf_server_user')
                    disconf_info.disconf_server_password = disconf_info_front.get('disconf_server_password')
                    disconf_info.disconf_env = disconf_info_front.get('disconf_env')
                    disconf_info.disconf_app_name = disconf_info_front.get('disconf_app_name')
    # deploy_obj.save()

    # 将computer信息如IP，更新到数据库
    app_image = [dict(app, cloud=cloud, resource_type=resource_type, project_name=project_name) for app in
                 args.app_image]
    appinfo = []
    if args.action == "admin_approve_allow":
        cmdb_url = current_app.config['CMDB_URL']
        appinfo = attach_domain_ip(app_image, resource, cmdb_url)
    # 如果是k8s应用修改外层nginx信息
    if cloud == '2' and resource_type == "app":
        nginx_info = get_k8s_nginx(args.environment)
        ips = nginx_info.get("nginx_ips") if nginx_info.get("nginx_ips") else K8S_NGINX_IPS
        nginx_port = nginx_info.get("nginx_port") if nginx_info.get("nginx_port") else K8S_NGINX_PORT
        appinfo = [dict(app, nginx_port=nginx_port, ips=ips) for app in appinfo]
    # 2、把配置推送到disconf
    disconf_server_info = deal_disconf_info(deploy_obj)
    app_image = appinfo if appinfo else app_image
    deploy_obj.app_image = str(app_image)
    deploy_obj.approve_status = 'success'
    message = 'approve_allow success'
    ##推送到crp
    deploy_type = "deploy"
    err_msg, result = deploy_to_crp(deploy_obj, args.environment,
                                    args.database_password, appinfo, disconf_server_info, deploy_type)
    if err_msg:
        deploy_obj.deploy_result = 'deploy_fail'
        message = 'deploy_fail'
    # 修改deploy_result状态为部署中
    deploy_obj.deploy_result = 'deploying'
    deploy_obj.approve_suggestion = args.approve_suggestion
    deploy_obj.save()
    return message


def admin_approve_forbid(args):
    deploy_obj = Deployment.objects.get(deploy_id=args.dep_id)
    deploy_obj.approve_status = 'fail'
    deploy_obj.deploy_result = 'not_deployed'
    deploy_obj.approve_suggestion = args.approve_suggestion
    deploy_obj.save()
    message = 'approve_forbid success'
    return message


def save_to_db(args):
    resource = ResourceModel.objects.get(res_id=args.resource_id)
    mysql_context = args.mysql_context
    redis_context = args.redis_context
    mongodb_context = args.mongodb_context
    uid = args.uid
    app_image = args.app_image
    for app in app_image:
        app["is_nginx"] = 0
    # 判断域名是否变化
    app_image = check_domain_port(resource, app_image)
    # ---
    if args.mysql_exe_mode == 'tag' and args.mysql_context:
        mysql_context = write_file(uid, args.mysql_context, 'mysql')
    if args.redis_exe_mode == 'tag' and args.redis_context:
        redis_context = write_file(uid, args.redis_context, 'redis')
    if args.mongodb_exe_mode == 'tag' and args.mongodb_context:
        mongodb_context = write_file(uid, args.mongodb_context, 'mongodb')
    # ------将部署信息更新到deployment表
    deploy_result = 'deploy_to_approve'
    deploy_type = 'deploy'
    deploy_item = Deployment(
        deploy_id=uid,
        deploy_name=args.deploy_name,
        initiator=args.initiator,
        user_id=args.user_id,
        project_id=args.project_id,
        project_name=args.project_name,
        resource_id=args.resource_id,
        resource_name=args.resource_name,
        created_time=datetime.datetime.now(),
        environment=args.environment,
        release_notes=args.release_notes,
        mysql_tag=args.mysql_exe_mode,
        mysql_context=mysql_context,
        redis_tag=args.redis_exe_mode,
        redis_context=redis_context,
        mongodb_tag=args.mongodb_exe_mode,
        mongodb_context=mongodb_context,
        app_image=str(app_image),
        deploy_result=deploy_result,
        apply_status=args.apply_status,
        approve_status=args.approve_status,
        approve_suggestion=args.approve_suggestion,
        database_password=args.database_password,
        deploy_type=deploy_type,
        department=args.department,
        business_name=args.business_name,
        module_name=args.module_name,
        resource_type=args.resource_type
    )

    for instance_info in args.disconf:
        for disconf_info in instance_info.get('dislist'):
            # 以内容形式上传，需要将内容转化为文本
            if disconf_info.get('disconf_tag') == 'tag':
                file_name = disconf_info.get('disconf_name')
                file_content = disconf_info.get('disconf_content')
                ins_name = instance_info.get('ins_name')
                upload_file = disconf_write_to_file(file_name=file_name,
                                                    file_content=file_content,
                                                    instance_name=ins_name,
                                                    type='disconf')
                disconf_info['disconf_content'] = upload_file
                disconf_info['disconf_admin_content'] = ''
            # 以文本形式上传，只需获取文件名
            else:
                file_name = disconf_info.get('disconf_name')
                if len(file_name.strip()) == 0:
                    upload_file = ''
                    disconf_info['disconf_content'] = upload_file
                    disconf_info['disconf_admin_content'] = upload_file

            ins_name = instance_info.get('ins_name')
            ins_id = instance_info.get('ins_id')
            disconf_tag = disconf_info.get('disconf_tag')
            disconf_name = disconf_info.get('disconf_name')
            disconf_content = disconf_info.get('disconf_content')
            disconf_admin_content = disconf_info.get('disconf_admin_content')
            disconf_server_name = disconf_info.get('disconf_server_name')
            disconf_server_url = disconf_info.get('disconf_server_url')
            disconf_server_user = disconf_info.get('disconf_server_user')
            disconf_server_password = disconf_info.get('disconf_server_password')
            disconf_version = disconf_info.get('disconf_version')
            disconf_env = disconf_info.get('disconf_env')
            disconf_app_name = disconf_info.get('disconf_app_name')
            disconf_id = str(uuid.uuid1())
            disconf_ins = DisconfIns(ins_name=ins_name, ins_id=ins_id,
                                     disconf_tag=disconf_tag,
                                     disconf_name=disconf_name,
                                     disconf_content=disconf_content,
                                     disconf_admin_content=disconf_admin_content,
                                     disconf_server_name=disconf_server_name,
                                     disconf_server_url=disconf_server_url,
                                     disconf_server_user=disconf_server_user,
                                     disconf_server_password=disconf_server_password,
                                     disconf_version=disconf_version,
                                     disconf_env=disconf_env,
                                     disconf_id=disconf_id,
                                     disconf_app_name=disconf_app_name,
                                     )
            deploy_item.disconf_list.append(disconf_ins)

    deploy_item.save()
    message = 'save_to_db success'
    return message


def not_need_approve(args):
    message = save_to_db(args)
    if message == 'save_to_db success':
        setattr(args, 'dep_id', args.uid)
        return admin_approve_allow(args)

