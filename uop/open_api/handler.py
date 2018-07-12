# -*- coding: utf-8 -*-


import uuid
from uop.deployment.handler import admin_approve_allow,save_to_db
from uop.resources.handler import resource_post
from uop.approval.handler import approval_info_post,approval_list_post,reservation_post
from uop.models import Deployment,ResourceModel,ItemInformation
from uop.util import async
from uop.log import Log



def get_item_id(project_name):
    msg = ''
    code = 200
    cmdb2_project_id = ""
    module_id = ""
    business_id = ""
    module_name = ""
    business_name = "凤凰计划二期"
    try:
        items_p = ItemInformation.objects.filter(item_name=project_name).order_by("-create_date")
        for item_p in items_p:
            cmdb2_project_id = item_p.cmdb2_project_id
            p_item_relation = item_p.item_relation
            if cmdb2_project_id:
                item_m = ItemInformation.objects.get(cmdb2_project_id=p_item_relation)
                m_cmdb2_project_id = item_m.cmdb2_project_id
                m_item_relation = item_m.item_relation
                if m_cmdb2_project_id:
                    module_id = m_cmdb2_project_id
                    module_name =item_m.item_name
                    item_b = ItemInformation.objects.get(cmdb2_project_id=m_item_relation)
                    b_cmdb2_project_id = item_b.cmdb2_project_id
                    if b_cmdb2_project_id and item_b.item_name == business_name:
                        business_id  = b_cmdb2_project_id
                        return code, msg, cmdb2_project_id, module_id, business_id,project_name,module_name,business_name
                    else:
                        continue
        else:
            code = 500
            msg = "{business_name}业务模块没有创建".format(business_name=business_name)
            return code,msg,cmdb2_project_id,module_id,business_id,project_name,module_name,business_name
    except Exception as e:
        code = 500
        msg = "工程{project_name}没有在{business_name}创建".format(project_name=project_name,business_name=business_name)
    return  code,msg,cmdb2_project_id,module_id,business_id,project_name,module_name,business_name



def approval_post(args):
    """
    资源
    :param args:
    :return:
    """
    code = 200
    try:
        resource = ResourceModel.objects.get(resource_name=args.resource_name)
        res_id = resource.res_id
        setattr(args, 'approve_uid', args.user_id)
        ret, code = approval_info_post(args, res_id)
        if code == 200:
            setattr(args, 'resource_id', res_id)
            reservation_post(args)
    except Exception as e:
        raise Exception(e)
    return code

def resource_db_post(args):
    """
    资源申请要调用的接口
    :param args:
    :return:
    """
    code = 200
    try:
        resource_info_list = []
        resource_info_dict = {}
        resource_info_dict["resource_name"] = args.resource_name
        resource_info_dict["project_name"] = args.project_name
        resource_info_dict["module_name"] = args.module_name
        resource_info_dict["business_name"] = args.business_name
        resource_info_dict["cmdb2_project_id"] = args.cmdb2_project_id
        resource_info_dict["cmdb2_module_id"] = args.cmdb2_module_id
        resource_info_dict["department"] = args.department
        resource_info_dict["user_name"] = args.user_name
        resource_info_dict["user_id"] = args.user_id
        resource_info_dict["env"] = args.env
        resource_info_dict["formStatus"] = "submit"
        resource_info_dict["resource_list"] = args.resource_list
        resource_info_dict["compute_list"] = args.compute_list
        resource_info_dict["cloud"] = args.cloud
        resource_info_dict["domain"] = args.domain
        resource_info_dict["resource_type"] = args.resource_type
        resource_info_list.append(resource_info_dict)
        ret, code = resource_post(resource_info_list)
        if code == 200:
            approval_info_list = []
            approval_info_dict = {}
            resource = ResourceModel.objects.get(resource_name=args.resource_name)
            res_id = resource.res_id
            approval_info_dict["resource_id"] = res_id
            approval_info_dict["project_id"] = args.cmdb2_project_id
            approval_info_dict["department"] = args.department
            approval_info_dict["user_id"] = args.user_id
            approval_info_list.append(approval_info_dict)
            ret,code = approval_list_post(approval_info_list)
    except Exception as e:
        raise Exception(e)
    return code


def deployment_post(args):
    code = 200
    try:
        resource = ResourceModel.objects.get(resource_name=args.resource_name)
        res_id = resource.res_id
        project_id = resource.cmdb2_project_id
        environment = resource.env
        app_image = [dict(eval(resource.compute_list[0].to_json()),domain_ip=args.domain_ip,certificate=args.certificate,named_url=args.named_url)]
        uid = str(uuid.uuid1())
        setattr(args, 'project_id', project_id)
        setattr(args, 'environment', environment)
        setattr(args, 'app_image', app_image)
        setattr(args, 'uid', uid)
        # resource_id = getattr(args, 'resource_id')
        # if not resource_id:
        setattr(args, 'resource_id', res_id)
        message = save_to_db(args)
        if message == 'save_to_db success':
            setattr(args, 'dep_id', uid)
            admin_approve_allow(args)
    except Exception as e:
        raise Exception("deployment_post {}".format(e))
    return code


@async
def res_deploy(args):
    code = 200
    msg = ""
    try:
        #将信息存放到resource 表
        deploys = Deployment.objects.filter(resource_name=args.resource_name)
        if deploys:
            #直接部署
            deployment_post(args)
        else:
            #先创建资源再部署
            resources = ResourceModel.objects.filter(resource_name=args.resource_name,is_deleted=0,reservation_status="set_success")
            if not resources:
                resource_db_post(args)
                approval_post(args)
            while 1:
                resource = ResourceModel.objects.get(resource_name=args.resource_name)
                if resource.reservation_status == "set_success":
                    deployment_post(args)
                    break
                elif resource.reservation_status == "set_fail":break
    except Exception as e:
        raise Exception(e)
        code = 500
        msg = "res and deploy error:{e}".format(e=str(e))
    return msg,code





