# -*- coding: utf-8 -*-
import json
import sys
import ldap
import os
from flask import request
from flask import redirect
from flask import jsonify
from flask_restful import reqparse, abort, Api, Resource, fields, marshal_with
from mongoengine import NotUniqueError
from uop.auth import auth_blueprint
from uop.models import UserInfo, User
from uop.auth.errors import user_errors
from wtforms import ValidationError
reload(sys)
sys.setdefaultencoding('utf-8')
base_dn = 'dc=syswin,dc=com'
scope = ldap.SCOPE_SUBTREE
ldap_server = 'ldap://172.28.4.103:389'
username = 'crm_test1'
password = 'syswin#'

auth_api = Api(auth_blueprint, errors=user_errors)


class LdapConn(object):
    def __init__(self, server, admin_name, admin_pass, base_dn, scope, flag=None, cn=None):
        self.server = server,
        self.name = admin_name,
        self.passwd = admin_pass,
        self.base_dn = base_dn,
        self.scope = scope,
        self.flag = flag,
        self.result = [],

    def conn_ldap(self):
        conn = ldap.initialize(self.server)
        conn.simple_bind_s(self.name, self.passwd)
        return conn

    def verify_user(self, id, password):
        con = self.conn_ldap()
        filter = "(&(|(cn=*%(input)s*)(sAMAccountName=*%(input)s*))(sAMAccountName=*))" % {'input': id}
        attrs = ['sAMAccountName', 'mail', 'givenName', 'sn', 'department', 'telephoneNumber', 'displayName']
        for i in con.search_s(base_dn, scope, filter, None):
            if i[0]:
                d = {}
                for k in i[1]:
                    d[k] = i[1][k][0]
                if 'telephoneNumber' not in d:
                    d['telephoneNumber'] = '(无电话)'
                if 'department' not in d:
                    d['department'] = '(无部门)'
                if 'sn' not in d and 'givenName' not in d:
                    d['givenName'] = d.get('displayName', '')
                if 'sn' not in d:
                    d['sn'] = ''
                if 'givenName' not in d:
                    d['givenName'] = ''
                self.result.append(d)
                self.cn = d.get('distinguishedName', '')
                print self.cn
                id = d.get('sAMAccountName', '')
                mail = d.get('mail', '')
                name = d.get('givenName', '')
                mobile = d.get('mobile', '')
                department = d.get('department', '')
                field_value = [id, mail, name, mobile, department]
        print '共找到结果 %s 条' % (len(self.result))
        for d in self.result:
            print '%(sAMAccountName)s\t%(mail)s\t%(sn)s%(givenName)s\t%(mobile)s %(department)s' % d
        try:
            if con.simple_bind_s(self.cn, password):
                print 'verify successfully'
                self.flag = 1
            else:
                print 'verify fail'
                self.flag = 0
        except ldap.INVALID_CREDENTIALS, e:
            print e
            self.flag = 0
        return self.flag, field_value


class UserRegister(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('id', type=str)
        parser.add_argument('username', type=str)
        parser.add_argument('password', type=str)
        args = parser.parse_args()

        id = args.id
        username = args.username
        password = args.password

        try:
            UserInfo(id=id, username=username, password=password).save()
            code = 200
            res = '注册成功'
        except NotUniqueError:
            code = 501
            res = '用户名已经存在'

        res = {
            "code": code,
            "result": {
                "res": res,
                "msg": "test info"
                }
        }
        return res, code

    def get(self):
        return "test info", 200


class UserList(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('id', type=str)
        parser.add_argument('password', type=str)
        args = parser.parse_args()

        id = args.id
        password = args.password

        conn = LdapConn(ldap_server, username, password, base_dn, scope)
        verify_code, verify_res = conn.verify_user(id, password)
        if verify_code:
            res = '登录成功'
            code = 200
        else:
            res = '登录失败'
            code = 304
        msg = ''
        # try:
        #     user = UserInfo.objects.get(id=id)
        #     if user:
        #         if user.password == password:
        #             res = '登录成功'
        #             code = 200
        #         else:
        #             res = '密码错误'
        #             code = 304
        #         msg = {
        #                 'username': user.username,
        #                 'user_id': id
        #                 }
        # except UserInfo.DoesNotExist:
        #     code = 305
        #     res = '用户不存在'
        #     msg = ''
        res = {
                "code": code,
                "result": {
                    "res": res,
                    "msg": msg
                    }
                }
        return res


class AdminUserList(Resource):
    def post(self):
        data = json.loads(request.body)
        id = data.get('id')
        password = data.get('password')
        user = UserInfo.objects.get(id=id)
        if user:
            if user.password == password:
                if user.is_admin:
                    res = '管理员登录成功'
                    code = 200
                else:
                    res = '您没有管理员权限'
                    code = 405
        else:
            res = '用户不存在'
            code = 404
        res = {
                'code': code,
                'result': {
                    'res': res,
                    'msg': ''
                    }
                }
        return json.dumps(res)


class AdminUserDetail(Resource):
    def put(self, name):
        user = UserInfo.objects.get(username=name)
        is_admin = json.loads(request.body())
        if user:
            user.is_admin = is_admin
            user.save()

    def delete(self, name):
        user = UserInfo.objects.get(username=name)
        user.delete()
        code = 200
        res = '删除用户成功'
        res = {
                'code': code,
                'result': {
                    'res': res,
                    'msg': ''
                    }
                }
        return res, 200


class AllUserList(Resource):
    def get(self):
        all_user = []
        users = UserInfo.objects.all()
        for i in users:
            all_user.append(i.username)
        return all_user


# admin user
auth_api.add_resource(AdminUserList, '/adminlist')
auth_api.add_resource(AdminUserDetail, '/admindetail/<name>')
# common user
auth_api.add_resource(UserRegister, '/users')
auth_api.add_resource(UserList, '/userlist')
auth_api.add_resource(AllUserList, '/all_user')


if __name__ == "__main__":
    conn = LdapConn()
    conn.verify_user(147749, 'syswin1~')
