# -*- coding: utf-8 -*-

import datetime
import os
import json
import traceback
import requests
from models import db
from uop.util import get_CRP_url
from uop.models import ResourceModel, Deployment, Cmdb, ViewCache, Statusvm,ConfigureK8sModel, EntityCache
from uop.item_info.handler import get_uid_token
from config import APP_ENV, configs
from uop.log import Log
from uop.util import async, TimeToolkit
from uop.send_email import SendEmail

curdir = os.path.dirname(os.path.abspath(__file__))

CMDB_URL = configs[APP_ENV].CMDB_URL
CMDB2_URL = configs[APP_ENV].CMDB2_URL
CMDB2_USER = configs[APP_ENV].CMDB2_OPEN_USER
CMDB2_VIEWS = configs[APP_ENV].CMDB2_VIEWS
CRP_URL = configs[APP_ENV].CRP_URL


def get_cmdb2_entity():
    Log.logger.info("-------start cache the entity--------")
    uid, token = get_uid_token()
    url = CMDB2_URL + "cmdb/openapi/entity/group/"
    data = {
      "uid": uid,
      "token": token,
      "sign": "",
      "data": {
        "name": ""
      }
    }
    entity_dict = {}
    entity_list = []
    """
    dev not exist
    """
    entity_dict['codis'] = ""
    entity_dict['apache'] = ""
    entity_dict['zookeeper'] = ""
    res = requests.post(url, data=json.dumps(data)).json()
    #Log.logger.info("The cmdb2 entity res is {}".format(res))
    with db.app.app_context():
        if res["code"] == 0:
            for i in res["data"]:
                if i["children"]:
                    for j in i["children"]:
                        code = j["code"]
                        children_id = j["id"]
                        host = children_id if code == "host" else ""
                        Person = children_id if code == "Person" else ""
                        department = children_id if code == "department" else ""
                        yewu = children_id if code == "yewu" else ""
                        Module = children_id if code == "Module" else ""
                        project = children_id if code == "project" else ""
                        container = children_id if code == "container" else ""
                        virtual_device = children_id if code == "virtual_device" else ""
                        if host:
                            entity_dict['host'] = host
                        if Person:
                            entity_dict['Person'] = Person
                        if department:
                            entity_dict['department'] = department
                        if yewu:
                            entity_dict['yewu'] = yewu
                        if Module:
                            entity_dict['Module'] = Module
                        if project:
                            entity_dict['project'] = project
                        if container:
                            entity_dict['container'] = container
                        if virtual_device:
                            entity_dict['virtual_device'] = virtual_device
                        if j["children"]:
                            for a in j["children"]:
                                code = a["code"]
                                children_id = a["id"]
                                mysql = children_id if code == "mysql" else ""
                                redis = children_id if code == "redis" else ""
                                tomcat = children_id if code == "tomcat" else ""
                                rabbitmq = children_id if code == "rabbitmq" else ""
                                mongodb = children_id if code == "mongodb" else ""
                                nginx = children_id if code == "nginx" else ""
                                codis = children_id if code == "codis" else ""
                                apache = children_id if code == "apache" else ""
                                zookeeper = children_id if code == "zookeeper" else ""
                                mycat = children_id if code == "mycat" else ""
                                if mysql:
                                    entity_dict['mysql'] = mysql
                                if redis:
                                    entity_dict['redis'] = redis
                                if tomcat:
                                    entity_dict['tomcat'] = tomcat
                                if rabbitmq:
                                    entity_dict['rabbitmq'] = rabbitmq
                                if mongodb:
                                    entity_dict['mongodb'] = mongodb
                                if nginx:
                                    entity_dict['nginx'] = nginx
                                if codis:
                                    entity_dict['codis'] = codis
                                if apache:
                                    entity_dict['apache'] = apache
                                if zookeeper:
                                    entity_dict['zookeeper'] = zookeeper
                                if mycat:
                                    entity_dict['mycat'] = mycat
    # Log.logger.info("The entity dict is {}".format(entity_dict))
    entity_list.append(entity_dict)
    entity_data = json.dumps(entity_list)
    try:
        entity_obj = EntityCache(
            entity=entity_data,
            created_time=TimeToolkit.local2utctimestamp(datetime.datetime.now())
        )
        entity_obj.save()
        # 临时写入 文件
        Log.logger.info("Current dir is {}".format(curdir))
        with open(curdir + "/entity.txt", "w") as f:
            json.dump(entity_dict, f)
    except Exception as e:
        msg = traceback.format_exc()
        Log.logger.info("The entity save error is {}".format(msg))


# 删除 资源的 定时任务 调用接口
def delete_res_handler():
    Log.logger.info('----------------delete_res_handler----------------')
    yestoday = datetime.datetime.now() - datetime.timedelta(days = 1)
    resources = ResourceModel.objects.filter(is_deleted=1).filter(deleted_date__lte=yestoday)
    #deploies = Deployment.objects.filter(is_deleted=1).filter(deleted_time__lte=yestoday)
    #Log.logger.info('-----------deploies---------------:%s'%(deploies))
    #Log.logger.info('-----------resources---------------:%s'%(resources))
    with db.app.app_context():
        for resource in resources:
            _delete_res(resource.res_id)
        #for deploy in deploies:
        #    _delete_deploy(deploy.deploy_id)

def _delete_deploy(deploy_id):
    try:
        deploy = Deployment.objects.get(deploy_id=deploy_id)
        if len(deploy):
            env_ = get_CRP_url(deploy.environment)
            crp_url = '%s%s'%(env_, 'api/deploy/deploys')
            disconf_list = deploy.disconf_list
            disconfs = []
            for dis in disconf_list:
                dis_ = dis.to_json()
                disconfs.append(eval(dis_))
            crp_data = {
                "disconf_list" : disconfs,
                "resources_id": '',
                "domain_list":[],
                "resources_id": ''
            }
            res = ResourceModel.objects.get(res_id=deploy.resource_id)
            if res:
                crp_data['resources_id'] = res.res_id
                compute_list = res.compute_list
                domain_list = []
                for compute in compute_list:
                    domain = compute.domain
                    domain_ip = compute.domain_ip
                    domain_list.append({"domain": domain, 'domain_ip': domain_ip})
                    crp_data['domain_list'] = domain_list
                    
            deploy.delete()
            # 调用CRP 删除资源
            crp_data = json.dumps(crp_data)
            requests.delete(crp_url, data=crp_data)
            # 回写CMDB
            #cmdb_url = '%s%s%s'%(CMDB_URL, 'api/repores_delete/', resources.res_id)
            #requests.delete(cmdb_url)
    except Exception as e:
        Log.logger.info('----Scheduler_utuls _delete_deploy  function Exception info is %s'%(e))

def _delete_res(res_id):
    try:
        resources = ResourceModel.objects.get(res_id=res_id)
        if len(resources):
            os_ins_list = resources.os_ins_list
            deploys = Deployment.objects.filter(resource_id=res_id)
            for deploy in deploys:
                env_ = get_CRP_url(deploy.environment)
                crp_url = '%s%s'%(env_, 'api/deploy/deploys')
                disconf_list = deploy.disconf_list
                disconfs = []
                for dis in disconf_list:
                    dis_ = dis.to_json()
                    disconfs.append(eval(dis_))
                crp_data = {
                    "disconf_list" : disconfs,
                    "resources_id": res_id,
                    "domain_list":[],
                }
                compute_list = resources.compute_list
                domain_list = []
                for compute in compute_list:
                    domain = compute.domain
                    domain_ip = compute.domain_ip
                    domain_list.append({"domain": domain, 'domain_ip': domain_ip})
                    crp_data['domain_list'] = domain_list
                crp_data = json.dumps(crp_data)
                requests.delete(crp_url, data=crp_data)
                #deploy.delete()
            # 调用CRP 删除资源
            crp_data = {
                    "resources_id": resources.res_id,
                    "os_inst_id_list": resources.os_ins_list,
                    "vid_list": resources.vid_list,
            }
            env_ = get_CRP_url(resources.env)
            crp_url = '%s%s'%(env_, 'api/resource/deletes')
            crp_data = json.dumps(crp_data)
            requests.delete(crp_url, data=crp_data)
            cmdb_p_code = resources.cmdb_p_code
            resources.delete()
            # 回写CMDB
            if CMDB_URL:
                cmdb_url = '%s%s%s'%(CMDB_URL, 'cmdb/api/repores_delete/', cmdb_p_code)
                requests.delete(cmdb_url)
    except Exception as e:
        Log.logger.info('---- Scheduler_utuls  _delete_res  function Exception info is %s'%(e))

# 刷新 虚拟机 状态的 调用接口
def flush_crp_to_cmdb():
    Log.logger.info('----------------flush_crp_to_cmdb job/5min----------------')
    osid_status = []
    now = datetime.datetime.now()
    with db.app.app_context():
        try:
            envs = CRP_URL.items()
            env_list = []
            url_list = []
            for env,url in envs:
                if url not in url_list:
                    env_list.append(env)
                    url_list.append(url)
            for env in env_list:
                if not env:
                    continue
                try:
                    K8sInfos = ConfigureK8sModel.objects.filter(env=env)
                    if K8sInfos:
                        for info in K8sInfos:
                            namespace = info.namespace_name
                            env_ = get_CRP_url(env)
                            crp_url = '%s%s' % (env_, 'api/openstack/nova/states?namespace={}'.format(namespace))
                            ret = requests.get(crp_url,timeout=290).json()["result"]["vm_info_dict"]
                            osid_status.append(ret)
                    else:
                        env_ = get_CRP_url(env)
                        crp_url = '%s%s' % (env_, 'api/openstack/nova/states')
                        ret = requests.get(crp_url).json()["result"]["vm_info_dict"]
                        osid_status.append(ret)
                except Exception as e:
                    Log.logger.error("Get vm info from crp error {}".format(e))

            if osid_status:
                for os in osid_status:
                    for k, v in os.items():
                        vms = Statusvm.objects.filter(osid=str(k))
                        if not vms:
                            q="-".join(str(k).split("-")[:-2])
                            vms = Statusvm.objects.filter(resource_name__icontains=q,update_time__ne=now)
                        if vms:
                            vms[0].update(status=v[1], osid=k, ip=v[0],update_time=now,physical_server=v[-1])
                if CMDB_URL:
                    cmdb_url = CMDB_URL + "cmdb/api/vmdocker/status/"
                    ret = requests.put(cmdb_url, data=json.dumps({"osid_status": osid_status})).json()
            else:
                Log.logger.info("flush_crp_to_cmdb crp->openstack result is null")
        except Exception as exc:
            Log.logger.error("flush_crp_to_cmdb error:{}".format(exc))


def flush_crp_to_cmdb_by_osid(osid, env):
    url = get_CRP_url(env)
    crp_url = '%s%s' % (url, 'api/openstack/nova/state?os_inst_id='+ osid)
    ret = requests.get(crp_url).json()
    Log.logger.info("flush_crp_to_cmdb_by_osid crp result is:{}".format(ret))
    if ret.get('code') == 200:
        status = ret["result"]["vm_state"]
        if CMDB_URL:
            cmdb_url = CMDB_URL + "cmdb/api/vmdocker/status/"
            ret = requests.put(cmdb_url, data=json.dumps({"osid_status": [{osid: status}]})).json()
        Log.logger.info("flush_crp_to_cmdb_by_osid cmdb result is:{}".format(ret))



# B类视图list，获取已经定义的关系列表
def get_relations():
    '''
    按视图名字查询, id会有变动，保证名字不变就好
    :param view_id:
    :param uid:
    :param token:
    :return:
    '''
    uid, token = get_uid_token()
    for id in [view[0] for num, view in CMDB2_VIEWS.items() if num in ["1","2","3","9"]]:
        get_one_view(uid, token, id)


@async
def get_one_view(uid, token, view_id):
    url = CMDB2_URL + "cmdb/openapi/scene_graph/list/"
    data = {
        "uid": uid,
        "token": token,
        "sign": "",
        "data": {
            "id": "",
            "name": view_id
        }
    }
    data_str = json.dumps(data)
    try:
        ret = requests.post(url, data=data_str, timeout=60).json()
        if ret["code"] == 0:
            relations = ret["data"][0]["relation"]  # 获取视图关系实体信息
            entity = ret["data"][0]["entity"]  # 获取视图实体信息
            view = ViewCache(view_id=view_id, relation=json.dumps(relations), entity=json.dumps(entity),
                             cache_date=TimeToolkit.local2utctimestamp(datetime.datetime.now()))
            view.save()
        elif ret["code"] == 121:
            data["uid"], data["token"] = get_uid_token(True)
            data_str = json.dumps(data)
            ret = requests.post(url, data=data_str, timeout=5).json()
            relations = ret["data"][0]["relation"]  # 获取视图关系实体信息,
            entity = ret["data"][0]["entity"]  # 获取视图实体信息
            view = ViewCache(view_id=view_id, relation=json.dumps(relations), entity=json.dumps(entity),
                             cache_date=TimeToolkit.local2utctimestamp(datetime.datetime.now()))
            view.save()
        else:
            Log.logger.info("get_relations data:{}".format(ret))
    except Exception as exc:
        Log.logger.error("get_relations error: {}".format(str(exc)))


def expire_resource_warn():
    Log.logger.info('----------------expiry_resouce_handler----------------')
    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    ten_day = (now + datetime.timedelta(days=10)).strftime("%Y-%m-%d")

    resources = ResourceModel.objects.filter(
        is_deleted=0, user_emails__exists=True, user_emails__ne=[]).filter(
            expiry_date__gt=today, expiry_date__lte=ten_day, expiry_date__nin=['long', '', None])

    for res in resources:
        ips = [i.ip for i in res.os_ins_ip_list]
        content = u"您的资源：{r_name} \nip地址：\n{ip} \n将要到期。".format(r_name=res.resource_name, ip='\t\n'.join(ips))

        try:
            send = SendEmail(
                username=res.user_name,
                content=content,
                email_address=res.user_emails,
                cc_email_address = res.cc_emails,
                subject_type='300',
            )
            send.send_email()
        except Exception as e:
            Log.logger.error('Expire warn error: {}'.format(str(e)))
            continue

if __name__ == "__main__":
    #get_relations()
    flush_crp_to_cmdb()
    pass
