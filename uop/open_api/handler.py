# -*- coding: utf-8 -*-

from uop.deployment.handler import admin_approve_allow,save_to_db
from uop.resources.handler import resource_post
from uop.approval.handler import deal_crp_data
from uop.models import Deployment,ResourceModel,Approval


def approval_post(resource_info_list):
    code = 200
    try:
        pass
    except Exception as e:
        pass
    return code

def res_to_crp():
    code = 200
    return code


def deployment_post():
    code = 200
    return code



def res_deploy(resource_info_list):
    try:
        #将信息存放到resource 表
        resource_post(resource_info_list)
        #审批时时信息的更新
    except Exception as e:
        pass





