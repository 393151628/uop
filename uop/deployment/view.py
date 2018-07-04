# -*- coding: utf-8 -*-

import uuid
import datetime
from uop.log import Log
import copy
from flask import request, send_from_directory, jsonify
from flask_restful import reqparse, Api, Resource
from flask import current_app
from uop.deployment import deployment_blueprint
from uop.models import  ResourceModel, DisconfIns, Deployment, Approval, Capacity, NetWorkConfig,ConfOpenstackModel
from uop.deployment.errors import deploy_errors
from uop.disconf.disconf_api import *
from uop.util import get_CRP_url
from uop.deployment.handler import  get_k8s_nginx, deploy_to_crp, deal_disconf_info, disconf_write_to_file, attach_domain_ip,check_domain_port
from uop.log import Log
from config import configs, APP_ENV
from uop.permission.handler import api_permission_control


K8S_NGINX_PORT = configs[APP_ENV].K8S_NGINX_PORT
K8S_NGINX_IPS = configs[APP_ENV].K8S_NGINX_IPS

deployment_api = Api(deployment_blueprint, errors=deploy_errors)

class DeploymentListAPI(Resource):

    # @api_permission_control(request)
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('user_id', type=str, location='args')
        parser.add_argument('deploy_id', type=str, location='args')
        parser.add_argument('initiator', type=str, location='args')
        parser.add_argument('deploy_name', type=str, location='args')
        parser.add_argument('deploy_type', type=str, location='args')
        parser.add_argument('project_name', type=str, location='args')
        parser.add_argument('resource_name', type=str, location='args')
        parser.add_argument('deploy_result', type=str, location='args')
        parser.add_argument('environment', type=str, location='args')
        parser.add_argument('start_time', type=str, location='args')
        parser.add_argument('end_time', type=str, location='args')
        parser.add_argument('approve_status', type=str, location='args')
        parser.add_argument('resource_id', type=str, location='args')
        parser.add_argument('page_num', type=int, location='args')
        parser.add_argument('page_size', type=int, location='args')
        parser.add_argument('department', type=str, location='args')
        parser.add_argument('resource_type', type=str, location='args')
        parser.add_argument('module_name', type=str, location='args')

        args = parser.parse_args()
        condition = {}
        domain_info = []
        if args.deploy_id:
            condition['deploy_id'] = args.deploy_id
        if args.user_id and args.user_id != "admin":
            condition['user_id'] = args.user_id
        if args.initiator:
            condition['initiator'] = args.initiator
        if args.deploy_name:
            condition['deploy_name'] = args.deploy_name
        if args.deploy_type:
            condition['deploy_type'] = args.deploy_type
        if args.project_name:
            condition['project_name__icontains'] = args.project_name
        if args.resource_name:
            condition['resource_name__icontains'] = args.resource_name
        if args.deploy_result:
            condition['deploy_result'] = args.deploy_result
        if args.environment:
            condition['environment'] = args.environment
        if args.start_time:
            condition['created_time__gte'] = args.start_time
        if args.end_time:
            condition['created_time__lte'] = args.end_time
        if args.approve_status:
            condition['approve_status'] = args.approve_status
        if args.department and args.department != "admin":
            departments = [dep.strip() for dep in args.department.strip().split(',')]
            condition["department__in"]=args.department
        if args.resource_type:
            condition["resource_type"] = departments
        if args.module_name:
            condition["module_name"]=args.module_name
        if args.resource_id:
            resource_id = args.resource_id
            condition['resource_id'] = resource_id
        deployments = []
        res={}
        try:
            total_count=Deployment.objects.filter(**condition).count()
            res["total_count"]=total_count
            if args.page_num and args.page_size:
                skip_count = (args.page_num - 1) * args.page_size
                Deployments = Deployment.objects.filter(**condition).order_by('-created_time').skip(skip_count).limit(
                    args.page_size)
            else:
                Deployments = Deployment.objects.filter(**condition).order_by('-created_time')
            for deployment in Deployments:
                # 返回disconf的json
                disconf = []
                for disconf_info in deployment.disconf_list:
                    instance_info = dict(ins_name=disconf_info.ins_name,
                                         ins_id=disconf_info.ins_id,
                                         dislist=[dict(disconf_tag=disconf_info.disconf_tag,
                                                       disconf_name=disconf_info.disconf_name,
                                                       disconf_content=disconf_info.disconf_content,
                                                       disconf_admin_content=disconf_info.disconf_admin_content,
                                                       disconf_server_name=disconf_info.disconf_server_name,
                                                       disconf_version=disconf_info.disconf_version,
                                                       disconf_id=disconf_info.disconf_id,
                                                       disconf_env=disconf_info.disconf_env,
                                                       disconf_app_name=disconf_info.disconf_app_name
                                                       )]
                                         )
                    if len(disconf) == 0:
                        disconf.append(instance_info)
                    else:
                        for disconf_choice in disconf:
                            if disconf_choice.get('ins_name') == instance_info.get('ins_name'):
                                disconf_choice.get('dislist').extend(instance_info.get('dislist'))
                                break
                        else:
                            disconf.append(instance_info)
                image_name, flavor_name, image2_name, flavor2_name, network_name = "","","","",""
                if args.resource_id:
                    resource = ResourceModel.objects.get(res_id=args.resource_id)
                    resource_list = resource.resource_list
                    compute_list = resource.compute_list
                    if resource_list:
                        for db_res in resource_list:
                            image_id = db_res.image_id
                            network_id = db_res.network_id
                            flavor_id = db_res.flavor_id
                            image2_id = db_res.image2_id
                            flavor2_id = db_res.flavor2_id
                            if image_id:
                                opsk_image = ConfOpenstackModel.objects.filter(image_id=image_id).first()
                                image_name = opsk_image.image_name
                            if flavor_id:
                                opsk_flavor = ConfOpenstackModel.objects.filter(flavor_id=flavor_id).first()
                                flavor_name = opsk_flavor.flavor_name
                            if image2_id:
                                opsk_image = ConfOpenstackModel.objects.filter(image_id=image2_id).first()
                                image2_name = opsk_image.image_name
                            if flavor2_id:
                                opsk_flavor = ConfOpenstackModel.objects.filter(flavor_id=flavor2_id).first()
                                flavor2_name = opsk_flavor.flavor_name
                            if network_id:
                                network = NetWorkConfig.objects.filter(vlan_id=network_id).first()
                                network_name = network.name
                    if compute_list:
                        for db_com in compute_list:
                            image_id = db_com.image_id
                            flavor_id = db_com.flavor_id
                            if image_id:
                                opsk_image = ConfOpenstackModel.objects.filter(image_id=image_id).first()
                                image_name = opsk_image.image_name
                            if flavor_id:
                                opsk_flavor = ConfOpenstackModel.objects.filter(flavor_id=flavor_id).first()
                                flavor_name = opsk_flavor.flavor_name
                deployments.append({
                    'deploy_id': deployment.deploy_id,
                    'deploy_name': deployment.deploy_name,
                    'initiator': deployment.initiator,
                    'user_id': deployment.user_id,
                    'project_id': deployment.project_id,
                    'project_name': deployment.project_name,
                    'business_name': deployment.business_name,
                    'module_name':deployment.module_name,
                    'resource_id': deployment.resource_id,
                    'resource_name': deployment.resource_name,
                    'environment': deployment.environment,
                    'release_notes': deployment.release_notes,
                    'mysql_tag': deployment.mysql_tag,
                    'mysql_context': deployment.mysql_context,
                    'redis_tag': deployment.redis_tag,
                    'redis_context': deployment.redis_context,
                    'mongodb_tag': deployment.mongodb_tag,
                    'mongodb_context': deployment.mongodb_context,
                    'app_image': eval(deployment.app_image),
                    # 'app_image': type(deployment.app_image),
                    'created_time': str(deployment.created_time),
                    'deploy_result': deployment.deploy_result,
                    'apply_status': deployment.apply_status,
                    'approve_status': deployment.approve_status,
                    'deploy_type': deployment.deploy_type,
                    'disconf': disconf,
                    'database_password': deployment.database_password,
                    'is_deleted': deployment.is_deleted,
                    'is_rollback': deployment.is_rollback,
                    'approve_suggestion': deployment.approve_suggestion,
                    'resource_type': deployment.resource_type,
                    "image_name":image_name,
                    "flavor_name":flavor_name,
                    "image2_name": image2_name,
                    "flavor2_name": flavor2_name,
                    "network_name":network_name,
                })

                res["deployments"]=deployments
        except Exception as e:
            ret = {
                "code": 400,
                "result": {
                    "res": "failed",
                    "msg": str(e)
                }
            }
            return ret, 400
        else:
            ret = {
                "code": 200,
                "result": {
                    "res": res,
                    "msg": "success"
                }
            }
            return ret, 200

    # @api_permission_control(request)
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('action', type=str,
                            choices=('save_to_db', 'admin_approve_allow', 'admin_approve_forbid', 'not_need_approve'),
                            required=True,
                            help='No action(save_to_db/admin_approve_allow/admin_approve_forbid/not_need_approve) provided',
                            location='json')
        parser.add_argument('deploy_name', type=str, required=True,
                            help='No deploy name provided', location='json')
        parser.add_argument('initiator', type=str, location='json')
        parser.add_argument('user_id', type=str, location='json')
        parser.add_argument('project_id', type=str, required=True,
                            help='No project id provided', location='json')
        parser.add_argument('project_name', type=str, location='json')
        parser.add_argument('resource_id', type=str, required=True,
                            help='No resource id provided', location='json')
        parser.add_argument('resource_name', type=str, location='json')
        parser.add_argument('environment', type=str, location='json')
        parser.add_argument('release_notes', type=str, location='json')
        parser.add_argument('mysql_exe_mode', type=str, location='json')
        parser.add_argument('mysql_context', type=str, location='json')
        parser.add_argument('redis_exe_mode', type=str, location='json')
        parser.add_argument('redis_context', type=str, location='json')
        parser.add_argument('mongodb_exe_mode', type=str, location='json')
        parser.add_argument('mongodb_context', type=str, location='json')
        parser.add_argument('app_image', type=list, location='json')
        parser.add_argument('approve_suggestion', type=str, location='json')
        parser.add_argument('apply_status', type=str, location='json')
        parser.add_argument('approve_status', type=str, location='json')
        parser.add_argument('dep_id', type=str, location='json')
        parser.add_argument('disconf', type=list, location='json')
        parser.add_argument('database_password', type=str, location='json')
        parser.add_argument('department', type=str, location='json')
        parser.add_argument('resource_type', type=str, location='json')
        parser.add_argument('module_name', type=str, location='json')
        parser.add_argument('business_name', type=str, location='json')

        args = parser.parse_args()
        action = args.action

        UPLOAD_FOLDER = current_app.config['UPLOAD_FOLDER']
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
            #deploy_obj.save()

            # 将computer信息如IP，更新到数据库
            app_image = [dict(app, cloud=cloud,resource_type=resource_type,project_name=project_name) for app in args.app_image]
            appinfo = []
            if action == "admin_approve_allow":
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
                                            args.database_password, appinfo, disconf_server_info,deploy_type)
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
            app_image=check_domain_port(resource,app_image)
            #---
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
                resource_type = args.resource_type
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

        try:
            func_map = {
                'admin_approve_allow': admin_approve_allow,
                'admin_approve_forbid': admin_approve_forbid,
                'save_to_db': save_to_db,
                'not_need_approve': not_need_approve,
            }
            uid = str(uuid.uuid1())
            setattr(args, 'uid', uid)
            func = func_map[action]
            message = func(args)
        except Exception as e:
            res = {
                "code": 400,
                "result": {
                    "res": "failed",
                    "msg": e.message
                }
            }
            return res, 400
        else:
            res = {
                "code": 200,
                "result": {
                    'deploy_id': uid,
                    "res": message,
                }
            }
            return res, 200

    # @api_permission_control(request)
    @classmethod
    def delete(cls):
        parser = reqparse.RequestParser()
        parser.add_argument('deploy_id', type=str)
        parser.add_argument('user', type=str)

        args = parser.parse_args()
        user = args.user
        deploy_id = args.deploy_id
        Log.logger.info("delete deployment:{}".format(deploy_id))
        try:
            deploy = Deployment.objects.get(deploy_id=deploy_id)
            if len(deploy):
                env_ = get_CRP_url(deploy.environment)
                crp_url = '%s%s' % (env_, 'api/deploy/deploys')
                disconf_list = deploy.disconf_list
                disconfs = []
                for dis in disconf_list:
                    dis_ = dis.to_json()
                    disconfs.append(eval(dis_))
                crp_data = {
                    "disconf_list": disconfs,
                    "resources_id": '',
                    "domain_list": [],
                }
                resm = ResourceModel.objects.filter(res_id=deploy.resource_id,is_deleted=0)
                if resm:
                    for res in resm:
                        crp_data['resources_id'] = res.res_id
                        compute_list = res.compute_list
                        domain_list = []
                        for compute in compute_list:
                            domain = compute.domain
                            domain_ip = compute.domain_ip
                            domain_list.append({"domain": domain, 'domain_ip': domain_ip})
                            crp_data['domain_list'] = domain_list
                        # 调用CRP 删除nginx资源
                        d_count = ResourceModel.objects.filter(domain=domain,is_deleted=0).count()
                        #如果还有一个以上的工程使用这个domain 不删除
                        if d_count <= 1:
                            crp_data = json.dumps(crp_data)
                            requests.delete(crp_url, data=crp_data)
                deploy.delete()

                # 回写CMDB
                # cmdb_url = '%s%s%s'%(CMDB_URL, 'api/repores_delete/', resources.res_id)
                # requests.delete(cmdb_url)
        except Exception as e:
            Log.logger.info('----Scheduler_utuls _delete_deploy  function Exception info is %s' % (e))
            ret = {
                'code': 500,
                'result': {
                    'res': 'fail',
                    'msg': 'Delete deployment  application failed.'
                }
            }
            return ret, 500
        # try:
        #     deploy = Deployment.objects.get(deploy_id=deploy_id)
        #     if len(deploy):
        #         env_ = get_CRP_url(deploy.environment)
        #         crp_url = '%s%s'%(env_, 'api/deploy/deploys')
        #         disconf_list = deploy.disconf_list
        #         disconfs = []
        #         for dis in disconf_list:
        #             dis_ = dis.to_json()
        #             disconfs.append(eval(dis_))
        #         crp_data = {
        #                 "disconf_list" : disconfs,
        #                 "resources_id": '',
        #                 "domain_list":[],
        #                 "resources_id": ''
        #         }
        #         res = ResourceModel.objects.get(res_id=deploy.resource_id)
        #         if res:
        #             #if hasattr(res, 'disconf_list'):
        #             #crp_data['disconf_list'] = res.disconf_list
        #             crp_data['resources_id'] = res.res_id
        #             compute_list = res.compute_list
        #             domain_list = []
        #             for compute in compute_list:
        #                 domain = compute.domain
        #                 domain_ip = compute.domain_ip
        #                 domain_list.append({"domain": domain, 'domain_ip': domain_ip})
        #             crp_data['domain_list'] = domain_list
        #
        #         deploy.delete()
        #         # 调用CRP 删除资源
        #         crp_data = json.dumps(crp_data)
        #         requests.delete(crp_url, data=crp_data)
        #         # 回写CMDB
        #         #cmdb_url = '%s%s%s'%(CMDB_URL, 'api/repores_delete/', resources.res_id)
        #         #requests.delete(cmdb_url)
        #
        #     else:
        #         ret = {
        #             'code': 200,
        #             'result': {
        #                 'res': 'success',
        #                 'msg': 'deployment not found.'
        #             }
        #         }
        #         return ret, 200
        # except Exception as e:
        #     print e
        #     ret = {
        #         'code': 500,
        #         'result': {
        #             'res': 'fail',
        #             'msg': 'Delete deployment  application failed.'
        #         }
        #     }
        #     return ret, 500
        ret = {
            'code': 200,
            'result': {
                'res': 'success',
                'msg': 'Delete deployment application success.'
            }
        }
        return ret, 200

    # @api_permission_control(request)
    @classmethod
    def put(cls):
        parser = reqparse.RequestParser()
        parser.add_argument('resource_id', type=str)
        args = parser.parse_args()
        resource_id = args.resource_id
        try:
            deploys = Deployment.objects.filter(resource_id=resource_id,deploy_result="deploy_fail").order_by('-created_time')
            if deploys:
                resource = ResourceModel.objects.get(res_id=resource_id)
                resource.updated_date = datetime.datetime.now()
                resource.save()
                deploy=deploys[0]
                environment=deploy.environment
                database_password=deploy.database_password
                cloud = resource.cloud
                resource_type = resource.resource_type
                #获取disconf信息
                disconf_server_info=deal_disconf_info(deploy)
                # 将computer信息如IP，更新到数据库
                app_image=eval(deploy.app_image)
                cmdb_url = current_app.config['CMDB_URL']
                appinfo = attach_domain_ip(app_image, resource, cmdb_url)
                if cloud == '2' and resource_type == "app":
                    nginx_info = get_k8s_nginx(environment)
                    ips = nginx_info.get("nginx_ips") if nginx_info.get("nginx_ips") else K8S_NGINX_IPS
                    nginx_port = nginx_info.get("nginx_port") if nginx_info.get("nginx_port") else K8S_NGINX_PORT
                    appinfo = [dict(app, nginx_port=nginx_port, ips=ips) for app in appinfo]
                ##推送到crp
                deploy.approve_status = 'success'
                deploy_type = "deploy"
                err_msg, result = deploy_to_crp(deploy,
                                                environment,
                                                database_password,
                                                appinfo, disconf_server_info,deploy_type)
                if err_msg:
                    deploy.deploy_result = 'deploy_fail'
                # 更新状态
                deploy.deploy_result = 'deploying'
                deploy.save()

            else:
                ret = {
                    'code': 400,
                    'result': {
                        'res': 'success',
                        'msg': 'deployment not found.'
                    }
                }
                return ret, 200
        except Exception as e:
            err_msg=str(e)
            Log.logger.error(err_msg)
            ret = {
                'code': 500,
                'result': {
                    'res': 'fail',
                    'msg': 'Put deployment application failed. %s ' % err_msg
                }
            }
            return ret, 500
        ret = {
            'code': 200,
            'result': {
                'res': 'success',
                'msg': 'Put deployment application success.'
            }
        }
        return ret, 200


class DeploymentAPI(Resource):
    # @api_permission_control(request)
    def put(self, deploy_id):
        pass

    # @api_permission_control(request)
    def delete(self, deploy_id):
        res_code = 204
        parser = reqparse.RequestParser()
        parser.add_argument('options', type=str)
        parser.add_argument('department', type=str)
        args = parser.parse_args()
        deploys = Deployment.objects.filter(deploy_id=deploy_id)
        if deploys:
            for deploy in deploys:
                if args.options == "rollback" and args.department == deploy.department:
                    flag = deploy.is_rollback
                    repo = ResourceModel.objects.filter(res_id=deploy.resource_id,is_deleted=0)
                    if repo:
                        for r in repo:
                            r.reservation_status = "set_success"
                            r.save()
                        deploy.is_rollback = 1 if flag == 0 else 0
                    else:
                        deploy.is_rollback = 1 if flag == 0 else 0
                        ret = {
                            'code': 203,
                            'result': {
                                'res': 'success rollback, but resource not found',
                                'msg': 'The deployment for its resource had been deleted.'
                            }
                        }
                        return ret, 200
                    deploy.save()
            ret = {
                'code': 200,
                'result': {
                    'res': 'success',
                    'msg': 'Rollback deployment success.'
                }
            }
            return ret, 200
            # deploys.delete()
        else:
            res_code = 404
        return "", res_code


class DeploymentListByByInitiatorAPI(Resource):
    # @api_permission_control(request)
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('initiator', type=str, location='args')
        args = parser.parse_args()
        Log.logger.info("[UOP] come into uop/deployment/handler.py, args: %s", args)

        condition = {}
        if args.initiator:
            condition['initiator'] = args.initiator

        pipeline = [
            {
                '$match': condition
            },
            {
                '$sort': {'created_time': 1}
            },
            {
                '$group': {
                    '_id': {'resource_id': "$resource_id"},
                    'created_time': {'$last': "$created_time"},
                    'deploy_id': {'$last': "$deploy_id"},
                    'deploy_name': {'$last': "$deploy_name"},
                    'resource_id': {'$last': "$resource_id"},
                    'resource_name': {'$last': "$resource_name"},
                    'project_id': {'$last': "$project_id"},
                    'project_name': {'$last': "$project_name"},
                    'initiator': {'$last': "$initiator"},
                    'environment': {'$last': "$environment"},
                    'release_notes': {'$last': "$release_notes"},
                    'app_image': {'$last': "$app_image"},
                    'deploy_result': {'$last': "$deploy_result"},
                }
            },
        ]

        rst = []
        try:
            for _deployment in Deployment._get_collection().aggregate(pipeline):
                rst.append({
                    "resource_id": _deployment['resource_id'],
                    "resource_name": _deployment['resource_name'],
                    "deploy_id": _deployment['deploy_id'],
                    "deploy_name": _deployment['deploy_name'],
                    "deploy_result": _deployment['deploy_result'],
                    "project_id": _deployment['project_id'],
                    "project_name": _deployment['project_name'],
                    "created_time": str(_deployment['created_time']),
                    "initiator": _deployment['initiator'],
                    "environment": _deployment['environment'],
                    "app_image": _deployment['app_image']
                })
        except Exception as e:
            res = {
                "code": 400,
                "result": {
                    "res": "failed",
                    "msg": e.message
                }
            }
            return res, 400
        else:
            return rst, 200


class Upload(Resource):
    # @api_permission_control(request)
    def post(self):
        try:
            uid = str(uuid.uuid1())
            UPLOAD_FOLDER = current_app.config['UPLOAD_FOLDER']
            file = request.files['file']
            type = request.form['file_type']

            if type == 'disconf':
                disconf_uid = str(uuid.uuid1())
                instance_name = request.form.get('instance_name')
                user_id = request.form.get('user_id')
                index = request.form.get('index')
                filename = '{file_name},{uuid}'.format(file_name=file.filename, uuid=disconf_uid)
                upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], type, instance_name, user_id)
                if not os.path.exists(upload_path):
                    os.makedirs(upload_path)
                path = os.path.join(upload_path, filename)
            else:
                filename = file.filename + '_' + uid
                index = request.form.get('index')
                path = os.path.join(UPLOAD_FOLDER, type, filename)
                if not os.path.exists(os.path.join(UPLOAD_FOLDER, type)):
                    os.makedirs(os.path.join(UPLOAD_FOLDER, type))
            file.save(path)
        except Exception as e:
            return {
                'code': 500,
                'msg': e.args
            }
        return {
            'code': 200,
            'msg': '上传成功！',
            'type': type,
            'path': path,
            'index': index,
        }


class Download(Resource):
    # @api_permission_control(request)
    def get(self, file_name):
        try:
            download_dir = current_app.config['UPLOAD_FOLDER']
            if os.path.isfile(os.path.join(download_dir, file_name)):
                return send_from_directory(download_dir, file_name, as_attachment=True)
            else:
                raise ServerError('file not exist.')
        except Exception as e:
            ret = {
                'code': 500,
                'msg': e.message
            }
            return ret


class CapacityAPI(Resource):
    '容量改变 扩容或者缩容 的提交申请'

    # @api_permission_control(request)
    def put(self):
        parser = reqparse.RequestParser()
        parser.add_argument('cluster_id', type=str)
        parser.add_argument('number', type=str)
        parser.add_argument('res_id', type=str)
        parser.add_argument('department', type=str)
        parser.add_argument('user_id', type=str)
        parser.add_argument('project_id', type=str)
        parser.add_argument('initiator', type=str)
        parser.add_argument('project_name', type=str)

        args = parser.parse_args()
        project_id = args.project_id
        department = args.department
        user_id = args.user_id
        cluster_id = args.cluster_id
        number = args.number
        res_id = args.res_id
        initiator = args.initiator
        project_name = args.project_name
        try:
            resources = ResourceModel.objects.filter(res_id=res_id,is_deleted=0)
            if len(resources):
                resource = resources[0]
                compute_list = resource.compute_list
                deploy_name = resource.deploy_name
                for compute_ in compute_list:
                    if compute_.ins_id == cluster_id:
                        if int(number) > int(compute_.quantity):
                            capacity_status = 'increase'
                            deploy_result = "increase_to_approve"
                            approval_status = "increasing"
                            deploy_type = "increase"
                        else:
                            capacity_status = 'reduce'
                            deploy_result = "reduce_to_approve"
                            approval_status = "reducing"
                            deploy_type = "reduce"
                        begin_number = compute_.quantity
                        end_number = number
                        approval_id = str(uuid.uuid1())
                        capacity = Capacity(capacity_id=approval_id, begin_number=begin_number, end_number=end_number)
                        capacity_list = compute_.capacity_list
                        capacity_list.append(capacity)
                        resource.save()

                        # approval_status = '%sing'%(capacity_status)
                        create_date = datetime.datetime.now()
                        if deploy_name:
                            deployments = Deployment.objects.filter(resource_id=res_id,
                                                                    deploy_name=deploy_name).order_by('-created_time')
                        else:
                            deployments = Deployment.objects.filter(resource_id=res_id).order_by('-created_time')
                        if deployments:
                            old_deployment = deployments[0]
                            old_deploy_name = old_deployment.deploy_name.strip().split('@')[0]
                            new_deploy_name = old_deploy_name + '@' + deploy_type + '_' + datetime.datetime.now().strftime(
                                '%Y-%m-%d_%H:%M:%S')
                            capacity_info_dict = self.deal_capacity_info(approval_id, res_id)
                            capacity_info_str = json.dumps(capacity_info_dict)
                            deploy_item = Deployment(
                                deploy_id=approval_id,
                                deploy_name=new_deploy_name,
                                initiator=initiator,
                                user_id=old_deployment.user_id,
                                project_id=project_id,
                                project_name=project_name,
                                resource_id=res_id,
                                resource_name=old_deployment.resource_name,
                                created_time=create_date,
                                environment=old_deployment.environment,
                                release_notes='',
                                mysql_tag=old_deployment.mysql_tag,
                                mysql_context=old_deployment.mysql_context,
                                redis_tag=old_deployment.redis_tag,
                                redis_context=old_deployment.redis_context,
                                mongodb_tag=old_deployment.mongodb_tag,
                                mongodb_context=old_deployment.mongodb_context,
                                app_image=old_deployment.app_image,
                                deploy_result=deploy_result,
                                apply_status="success",
                                approve_status=approval_status,
                                approve_suggestion="",
                                database_password=old_deployment.database_password,
                                disconf_list=old_deployment.disconf_list,
                                capacity_info=capacity_info_str,
                                deploy_type=deploy_type,
                                department=args.department,
                                business_name=old_deployment.business_name,
                                module_name=old_deployment.module_name,
                                resource_type=old_deployment.resource_type,
                            )
                            deploy_item.save()
                        Approval(approval_id=approval_id, resource_id=res_id, deploy_id=approval_id,
                                 project_id=project_id, department=department,
                                 user_id=user_id, create_date=create_date,
                                 approval_status=approval_status, capacity_status=capacity_status).save()
            else:
                ret = {
                    'code': 200,
                    'result': {
                        'res': 'success',
                        'msg': 'resource not found.'
                    }
                }
                return ret, 200
        except Exception as e:
            Log.logger.debug(e)
            ret = {
                'code': 500,
                'result': {
                    'res': 'fail',
                    'msg': 'Put deployment  application failed %s.' % e
                }
            }
            return ret, 500
        ret = {
            'code': 200,
            'result': {
                'res': 'success',
                'msg': 'Put deployment capacity application success.'
            }
        }
        return ret, 200

        # '资源实例的集群信息'

    # @api_permission_control(request)
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('res_id', type=str, location='args')
        args = parser.parse_args()
        res_id = args.res_id
        rst = []
        try:
            resource = ResourceModel.objects.get(res_id=res_id)
            if len(resource):
                compute_list = resource.compute_list
                for compute_ in compute_list:
                    quantity = compute_.quantity
                    ins_name = compute_.ins_name
                    rst.append({"quantity": quantity, "ins_name": ins_name, 'res_id': res_id, "ins_id": compute_.ins_id,
                                "resource_name": resource.resource_name})
        except Exception as e:
            res = {
                "code": 400,
                "result": {
                    "res": "failed",
                    "msg": e.message
                }
            }
            return res, 400
        else:
            return rst, 200

    def deal_capacity_info(self, approval_id, res_id):
        rst_dict = {}
        rst = []
        net = None
        cur_data = None
        try:
            resource = ResourceModel.objects.get(res_id=res_id)
            if len(resource):
                compute_list = resource.compute_list
                for compute_ in compute_list:
                    capacity_list = compute_.capacity_list
                    for capacity_ in capacity_list:
                        tmp = {'cluster_id': compute_.ins_id, 'ins_name': compute_.ins_name,
                               'cpu': compute_.cpu, 'mem': compute_.mem, 'url': compute_.url,
                               'port': compute_.port, "capacity_id": capacity_.capacity_id,
                               "quantity": compute_.quantity, 'domain_ip': compute_.domain_ip,
                               'domain': compute_.domain}
                        tmp['meta'] = compute_.docker_meta if getattr(compute_, "docker_meta", "") else ""
                        if capacity_.capacity_id == approval_id:
                            tmp2 = copy.deepcopy(tmp)
                            cur_data = tmp
                            tmp2["quantity"] = capacity_.end_number
                            cur_data["quantity"] = capacity_.begin_number
                            rst.append(tmp2)
                            if capacity_.network_id:
                                net = NetWorkConfig.objects.get(vlan_id=capacity_.network_id)
                if cur_data:
                    rst.insert(0, cur_data)
                rst_dict["resource_name"] = resource.resource_name
                rst_dict["project"] = resource.project
                rst_dict["compute_list"] = rst
                rst_dict["env"] = resource.env
                if net:
                    net_work_name = net.name
                else:
                    nets = NetWorkConfig.objects.filter(vlan_id=resource.docker_network_id)
                    net = nets[0]
                    net_work_name = net.name
                rst_dict["network_name"] = net_work_name
                return rst_dict
        except Exception as e:
            err_msg = e.args
            Log.logger.error("UOP deal_capacity_info error: %s" % err_msg)
            return rst_dict


class CapacityInfoAPI(Resource):
    # '获取扩容详情'


    # @api_permission_control(request)
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('deploy_id', type=str, location='args')
        args = parser.parse_args()
        deploy_id = args.deploy_id
        try:
            deployment = Deployment.objects.get(deploy_id=deploy_id)
            approve_suggestion = deployment.approve_suggestion
            capacity_info = deployment.capacity_info
            if capacity_info:
                capacity_info_dict = json.loads(capacity_info)
            else:
                capacity_info_dict = {}
            capacity_info_dict["approve_suggestion"]=approve_suggestion
        except Exception as e:
            res = {
                "code": 400,
                "result": {
                    "res": "failed",
                    "msg": str(e)
                }
            }
            return res, 400
        else:
            return capacity_info_dict, 200


class RollBackAPI(Resource):
    # 应用回滚
    # @api_permission_control(request)
    def get(self):
        # distinguish_tag 为资源管理和部署申请返回值不同做区分 resource_manage deploy_apply
        parser = reqparse.RequestParser()
        parser.add_argument('resource_id', type=str, location='args')
        parser.add_argument('distinguish_tag', type=str, location='args')
        args = parser.parse_args()
        resource_id = args.resource_id
        distinguish_tag = args.distinguish_tag

        deployments = {}
        history_version = []
        resource = ResourceModel.objects.get(res_id=resource_id, is_deleted=0)
        if resource.deploy_name:
            now_deploy_name = resource.deploy_name.strip().split('@')[0]
        else:
            now_deploy_name = None
        deployments["now_deploy_name"] = now_deploy_name
        try:
            if distinguish_tag == "resource_manage":
                deploys = Deployment.objects.filter(
                    resource_id=resource_id,
                    approve_status="success",
                    deploy_type="deploy",
                    deploy_result="deploy_success").order_by('-created_time')

            elif distinguish_tag == "deploy_apply":
                deploys = Deployment.objects.filter(
                    resource_id=resource_id,
                    deploy_type="deploy"
                ).order_by('-created_time')
            else:
                deploys = []

            # release_notes 部署详情 deploy_name 部署版本
            if deploys:
                for dep in deploys:
                    deploy_name = dep.deploy_name
                    release_notes = dep.release_notes
                    if deploy_name != now_deploy_name:
                        history_version.append({"deploy_name": deploy_name, "release_notes": release_notes})

            deployments["history_version"] = history_version

        except Exception as e:
            res = {
                "code": 400,
                "result": {
                    "res": "get rollback info failed",
                    "msg": str(e)
                }
            }
            return res, 400
        else:
            return deployments, 200

    # @api_permission_control(request)
    def put(self):
        parser = reqparse.RequestParser()
        parser.add_argument('deploy_name', type=str)
        parser.add_argument('res_id', type=str)
        parser.add_argument('department', type=str)
        parser.add_argument('user_id', type=str)
        parser.add_argument('project_id', type=str)
        parser.add_argument('initiator', type=str)
        parser.add_argument('project_name', type=str)
        args = parser.parse_args()
        project_id = args.project_id
        department = args.department
        user_id = args.user_id
        res_id = args.res_id
        initiator = args.initiator
        project_name = args.project_name
        deploy_name = args.deploy_name
        try:
            approval_id = str(uuid.uuid1())
            approval_status = "rollbacking"
            # 更新要回滚的deploy记录
            old_deployment = Deployment.objects.get(deploy_name=deploy_name,resource_id=res_id)
            deploy_id = approval_id
            create_date = datetime.datetime.now()
            # 状态为回滚未审批
            deploy_result = "rollback_to_approve"
            deploy_type = "rollback"
            approve_status = "rollbacking"
            # ------------------------
            new_deploy_name = deploy_name + '@' + deploy_type + '_' + datetime.datetime.now().strftime(
                '%Y-%m-%d_%H:%M:%S')
            # 回滚新生成一条部署记录原来的部署记录保存
            deploy_item = Deployment(
                deploy_id=approval_id,
                deploy_name=new_deploy_name,
                initiator=initiator,
                user_id=old_deployment.user_id,
                project_id=project_id,
                project_name=project_name,
                resource_id=res_id,
                resource_name=old_deployment.resource_name,
                created_time=create_date,
                environment=old_deployment.environment,
                release_notes=old_deployment.release_notes,
                mysql_tag=old_deployment.mysql_tag,
                mysql_context=old_deployment.mysql_context,
                redis_tag=old_deployment.redis_tag,
                redis_context=old_deployment.redis_context,
                mongodb_tag=old_deployment.mongodb_tag,
                mongodb_context=old_deployment.mongodb_context,
                app_image=old_deployment.app_image,
                deploy_result=deploy_result,
                apply_status="success",
                approve_status=approve_status,
                approve_suggestion="",
                database_password=old_deployment.database_password,
                disconf_list=old_deployment.disconf_list,
                deploy_type=deploy_type,
                department = department,
                business_name=old_deployment.business_name,
                module_name=old_deployment.module_name,
                resource_type=old_deployment.resource_type,
            )
            deploy_item.save()

            # 将回滚信息记录到申请审批表
            Approval(approval_id=approval_id, resource_id=res_id, deploy_id=deploy_id,
                     project_id=project_id, department=department,
                     user_id=user_id, create_date=create_date,
                     approval_status=approval_status).save()
        except Exception as e:
            Log.logger.debug(e)
            ret = {
                'code': 500,
                'result': {
                    'res': 'fail',
                    'msg': 'Put deployment rollback failed %s.' % e
                }
            }
            return ret, 500
        ret = {
            'code': 200,
            'result': {
                'res': approval_id,
                'msg': 'Put deployment rollback application success.'
            }
        }
        return ret, 200


@deployment_blueprint.route('/check_deploy_name', methods=['GET'])
def check_deployment_by_id():
    deploy_name = request.args.get('deploy_name', '')
    resource_id = request.args.get('resource_id', '')
    try:
        deploy = Deployment.objects.get(deploy_name=deploy_name,resource_id=resource_id)
    except Deployment.DoesNotExist as e:
        res = {
            'code': 200,
            'result': {
                'res': 'success',
                'msg': 'success'
            }
        }
        return jsonify(res=res)
    res = {
        'code': 500,
        'result': {
            'res': 'success',
            'msg': 'deploy_name has existed',
        }
    }
    return jsonify(res=res)


deployment_api.add_resource(DeploymentListAPI, '/deployments')
deployment_api.add_resource(DeploymentAPI, '/deployments/<deploy_id>/')
deployment_api.add_resource(DeploymentListByByInitiatorAPI, '/getDeploymentsByInitiator')
deployment_api.add_resource(Upload, '/upload')
deployment_api.add_resource(Download, '/download/<file_name>')
deployment_api.add_resource(CapacityAPI, '/capacity')
deployment_api.add_resource(CapacityInfoAPI, '/capacity/info')
deployment_api.add_resource(RollBackAPI, '/rollback')
