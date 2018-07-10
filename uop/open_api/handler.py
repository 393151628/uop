# -*- coding: utf-8 -*-

from uop.deployment.handler import admin_approve_allow,save_to_db
from uop.resources.handler import resource_post
from uop.approval.handler import deal_crp_data


def approval_post():
    code = 200
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
    except Exception as e:
        pass





