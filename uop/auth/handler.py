# -*- coding: utf-8 -*-
import json
import requests
import datetime
from uop.log import Log
from flask import current_app
from uop.models import PermissionList

def add_person(name, user_id, department, contact_info, privilege):
    """
        cmdb1.0临时跳过了将用户权限信息入库操作
    """
    return True # 直接返回
    success = False
    already_exist = False
    CMDB_URL = current_app.config['CMDB_URL']
    CMDB_API = CMDB_URL+'cmdb/api/'
    req = CMDB_API + "repo_detail?item_id=person_item&p_code=user_id&value=" + user_id
    res = requests.get(str(req))
    ret_query_decode = res.content.decode('unicode_escape')
    ret = json.loads(ret_query_decode)
    if res.status_code == 200:
        repoitem_person = ret.get("result").get("res")
        if len(repoitem_person) is not 0:
            already_exist = True
            success = True

    if already_exist is False:
        data = {}
        data["name"] = u"人"
        data["layer_id"] = "Organization"
        data["group_id"] = "OrganizationLine"
        data["item_id"] = "person_item"

        property_list = []
        property_list.append({"type": "string", "p_code": "name", "name": u"姓名", "value": name})
        property_list.append({"type": "string", "p_code": "user_id", "name": u"员工工号", "value": user_id})
        property_list.append({"type": "string", "p_code": "department", "name": u"部门", "value": department})
        property_list.append({"type": "string", "p_code": "contact_info", "name": u"联系方式", "value": contact_info})
        property_list.append({"type": "string", "p_code": "privilege", "name": u"权限", "value": privilege})
        property_list.append({"type": "string", "p_code": "create_time", "name": u"创建时间",
                              "value": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
        data["property_list"] = property_list
        data_str = json.dumps(data)


        CMDB_URL = current_app.config['CMDB_URL']
        CMDB_API = CMDB_URL+'cmdb/api/'

        res = requests.post(CMDB_API + "repo/", data=data_str)
        ret = eval(res.content.decode('unicode_escape'))
        if res.status_code == 200:
            success = True
    return success





def get_login_permission(role):
    """
    根据角色获取登录时的权限
    :param role:
    :return:
    """
    menu_list = []
    menus = []
    menu2s = []
    buttons = []
    icons = []
    operations=[]
    name1 = []
    name2 = []
    try:
        #获取权限
        Permissions=PermissionList.objects.filter(role=role,perm_type__in=["button","icon","operation","menu"])
        for permission in Permissions:
            if permission.perm_type == "menu":
                menu_dict = {}
                menu2_dict={}
                name=permission.name
                url=permission.url
                menu_id=permission.menu_id
                level=permission.level
                parent_id=permission.parent_id
                isDropdown = permission.isDropdown
                if int(level) == 1:
                    menu_dict["name"] = name
                    menu_dict["url"] = url
                    menu_dict["menu_id"] = menu_id
                    menu_dict["isDropdown"] = isDropdown
                    menu_dict["children"] = []
                    menus.append(menu_dict)
                    name1.append(name)
                elif int(level) == 2:
                    menu2_dict["name"] = name
                    menu2_dict["url"] = url
                    menu2_dict["menu_id"] = menu_id
                    menu2_dict["parent_id"] = parent_id
                    menu_dict["isDropdown"] = isDropdown
                    menu_dict["children"] = []
            elif permission.perm_type == "operation":
                operations.append(permission.operation)
            elif permission.perm_type == "icon":
                icons.append(permission.icon)
            elif permission.perm_type == "button":
                buttons.append(permission.button)
        for menu in menus:
            for menu2 in menu2s:
                if menu.get("menu_id") == menu2.get("parent_id"):
                    menu["children"].append(menu2)
                    if len(menu["children"]) == 0:
                        menu_list.append(menu)
                        name2.append(menu.get("name"))
        for menu in menus:
            if menu.get("name") not in name2:
                menu_list.append(menu)
        return menu_list,buttons,icons,operations
    except Exception as e:
        Log.logger.error("UOP User get menu list error,error msg is %s" % str(e) )
        return  menu_list,buttons,icons,operations