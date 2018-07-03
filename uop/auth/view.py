# -*- coding: utf-8 -*-

import json
import sys
import ldap
import datetime
import hashlib
from flask import request
from flask_restful import reqparse, Api, Resource
from uop.auth import auth_blueprint
from uop.models import UserInfo
from uop.auth.errors import user_errors
from uop.auth.handler import add_person,get_login_permission, registor_manual
from uop.log import Log
from uop.util import response_data
from uop.permission.handler import api_permission_control

reload(sys)
sys.setdefaultencoding('utf-8')
from flask_httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()

base_dn = 'dc=syswin,dc=com'
scope = ldap.SCOPE_SUBTREE
# TODO:move to global conf
ldap_server = 'ldap://172.28.2.100:389'
username = 'crm_test1'
passwd_admin = 'syswin#'

auth_api = Api(auth_blueprint, errors=user_errors)


class LdapConn(object):
    def __init__(self, server, admin_name, admin_pass, base_dn, scope, flag=None, cn=None):
        self.server = server,
        self.name = admin_name,
        self.passwd = admin_pass,
        self.base_dn = base_dn,
        self.scope = scope,
        self.flag = flag,

    def conn_ldap(self):
        ldap.set_option(ldap.OPT_REFERRALS, 0)
        conn = ldap.initialize(self.server[0])
        conn.simple_bind_s(self.name[0], self.passwd[0])
        return conn

    def verify_user(self, id, password):
        result = []
        con = self.conn_ldap()
        filter_field = "(&(|(cn=*%(input)s*)(sAMAccountName=*%(input)s*))(sAMAccountName=*))" % {'input': id}
        attrs = ['sAMAccountName', 'mail', 'givenName', 'sn', 'department', 'telephoneNumber', 'displayName']
        for i in con.search_s(base_dn, scope, filter_field, None):
            if i[0] and 'SYSWIN' not in i[0]:
                d = {}
                for k in i[1]:
                    d[k] = i[1][k][0]
                if 'telephoneNumber' not in d:
                    d['telephoneNumber'] = u'(无电话)'
                if 'department' not in d:
                    d['department'] = u'(无部门)'
                if 'sn' not in d and 'givenName' not in d:
                    d['givenName'] = d.get('displayName', '')
                if 'sn' not in d:
                    d['sn'] = ''
                if 'givenName' not in d:
                    d['givenName'] = ''
                result.append(d)
                self.cn = d.get('distinguishedName', '')
                Log.logger.error(self.cn)
                id = d.get('sAMAccountName', '')
                mail = d.get('mail', '')
                name = d.get('cn', '')
                mobile = d.get('mobile', '')
                department = d.get('department', '')
                field_value = {
                    'id': id,
                    'mail': mail,
                    'name': name,
                    'mobile': mobile,
                    'department': department
                }
                Log.logger.info(d)
        Log.logger.debug('共找到结果 %s 条' % (len(result)))
        try:
            if con.simple_bind_s(self.cn, password):
                Log.logger.debug('verify successfully')
                self.flag = 1
            else:
                Log.logger.debug('verify fail')
                self.flag = 0
        except ldap.INVALID_CREDENTIALS, e:
            Log.logger.error(str(e))
            self.flag = 0
        return self.flag, field_value


class UserLogin(Resource):
    #@api_permission_control(request)
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('id', type=str)
        parser.add_argument('password', type=str)
        args = parser.parse_args()
        id = args.id
        password = args.password
        md5 = hashlib.md5()
        md5.update(password)
        salt_password = md5.hexdigest()
        menu_list=[]
        try:
            #用户表里有用户
            user = UserInfo.objects.get(id=id)
            if user.password == salt_password:
                add_person(user.username, user.id, user.department, "", "")
                user.last_login_time=datetime.datetime.now()
                user.save()
                role=user.role
                menu_list,buttons,icons,operations=get_login_permission(role)
                code = 200
                msg = u'登录成功'
                res = {
                    'user_id': user.id,
                    'username': user.username,
                    'department': user.department,
                    'role':user.role,
                    'menu_list':menu_list,
                    'buttons': buttons,
                    'icons': icons,
                    'operations': operations,
                }
            else:
                msg = u'登录失败'
                code = 400
                res = u'验证错误'
        except UserInfo.DoesNotExist as e:
            #用户表没有用户,验证ldap 创建用户
            conn = LdapConn(ldap_server, username, passwd_admin, base_dn, scope)
            verify_code, verify_res = conn.verify_user(id, password)
            verify_res_name = verify_res.get('name')  # 获取到用户名
            verify_res_department = verify_res.get('department')  # 获取到部门
            user = verify_res_name.decode('utf-8')
            department = verify_res_department.decode('utf-8')
            user_id = verify_res.get('id')  # 获取到工号
            role="user"
            if verify_code:
                msg = u'登录成功'
                code = 200
                try:
                    #不通过ldap手动创建的用户
                    user = UserInfo.objects.get(id=user_id)
                    user.save()
                    role=user.role
                except UserInfo.DoesNotExist:
                    user_obj = UserInfo()
                    user_obj.id = user_id
                    user_obj.username = user
                    user_obj.password = salt_password
                    user_obj.department = department
                    user_obj.created_time = datetime.datetime.now()
                    user_obj.updated_time = datetime.datetime.now()
                    user_obj.last_login_time = datetime.datetime.now()
                    user_obj.role=role
                    user_obj.save()
                    add_person(user, user_id, department, "","")
                    menu_list, buttons, icons, operations = get_login_permission(role)
                res = {
                    'user_id': user_id,
                    'username': user,
                    'department': department,
                    'role': role,
                    'menu_list': menu_list,
                    'buttons': buttons,
                    'icons': icons,
                    'operations': operations,
                }
            else:
                registor_manual(id, user, department)
                msg = u'登录成功'
                code = 200
                res = u'ldap验证错误,已注册独立uop账号'

        ret=response_data(code, msg, res)
        return ret,code

class ServiceDirectory(Resource):

    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('menu_module', type=str)
        parser.add_argument('role', type=str)
        args = parser.parse_args()
        role = args.role
        menu_module = args.menu_module
        menu_list = []
        buttons = []
        icons = []
        operations = []
        data = {}
        code = 200
        msg = ''
        try:
            menu_list, buttons, icons, operations = get_login_permission(role,menu_module)
        except Exception as e:
            msg = "Get service menu permission info error,error msg is %s" % str(e)
            code = 500
            data = "Error"
            Log.logger.error(msg)
        data["menu_list"] = menu_list
        data["buttons"] = buttons
        data["icons"] = icons
        data["operations"] = operations
        ret = response_data(code, msg, data)
        return ret, code











auth_api.add_resource(UserLogin, '/userlogin')
auth_api.add_resource(ServiceDirectory, '/service')
