# -*- coding: utf-8 -*-
import datetime
from flask_mongoengine import MongoEngine

db = MongoEngine()


class User(db.Document):
    email = db.StringField(required=True)
    first_name = db.StringField(max_length=50)
    last_name = db.StringField(max_length=50)


class UserInfo(db.Document):
    id = db.StringField(required=True, max_length=50, unique=True, primary_key=True)
    username = db.StringField(required=False, max_length=50)
    password = db.StringField(required=True, max_length=50)
    department = db.StringField(required=False)
    is_admin = db.BooleanField(required=False, default=False)
    is_external = db.BooleanField(required=False, default=False)
    created_time = db.DateTimeField(auto_now_add=True, default=datetime.datetime.now())

    meta = {
            "collection": "uop_userinfo",
            "index": [{
                'fields': ['username', 'id', 'department', 'is_admin'],
                'unique': True,
                }]
            }


class DisconfIns(db.EmbeddedDocument):
    ins_name = db.StringField(required=True)
    ins_id = db.StringField(required=True)
    disconf_tag = db.StringField(required=False)
    disconf_name = db.StringField(required=False)
    disconf_content = db.StringField(required=False)
    disconf_admin_content = db.StringField(required=False)
    disconf_server_name = db.StringField(required=False)
    disconf_server_url = db.StringField(required=False)
    disconf_server_user = db.StringField(required=False)
    disconf_server_password = db.StringField(required=False)
    disconf_version = db.StringField(required=False)
    disconf_env = db.StringField(required=False)
    disconf_id = db.StringField(required=False)
    meta = {
        'collection': 'disconf_ins',
        'index': [
            {
                'fields': ['ins_name','ins_id'],
                'sparse': True,
                }
            ],
        'index_background': True
        }


class Deployment(db.Document):
    deploy_id = db.StringField(unique=True)
    deploy_name = db.StringField()
    initiator = db.StringField()
    project_id = db.StringField()
    project_name = db.StringField()
    resource_id = db.StringField()
    resource_name = db.StringField()
    created_time = db.DateTimeField(default=datetime.datetime.now())
    environment = db.StringField()
    release_notes = db.StringField()
    mysql_tag = db.StringField()
    mysql_context = db.StringField()
    redis_tag = db.StringField()
    redis_context = db.StringField()
    mongodb_tag = db.StringField()
    mongodb_context = db.StringField()
    app_image = db.StringField()
    deploy_result = db.StringField()
    user_id = db.StringField()
    database_password = db.StringField()  # 数据库用户的密码
    apply_status = db.StringField()  # 部署申请状态
    approve_status = db.StringField()  # 部署审批状态
    approve_suggestion = db.StringField()  # 审批意见
    disconf_list = db.ListField(db.EmbeddedDocumentField('DisconfIns'))
    meta = {
        'collection': 'deployment',
        'index': [
            {
                'fields': ['initiator', 'project_name', 'deploy_name', 'created_time'],
                'sparse': True,
            }
        ],
        'index_background': True
    }


class ComputeIns(db.EmbeddedDocument):
    ins_name = db.StringField(required=True, unique=True)
    ins_id = db.StringField(required=True, unique=True)
    # ins_type = db.StringField(required=False)
    cpu = db.IntField(required=False)
    mem = db.IntField(required=False)
    # disk = db.StringField(required=False)
    domain = db.StringField(required=False)
    domain_ip = db.StringField(required=False)
    quantity = db.IntField(required=False)
    # version = db.StringField(required=False)
    ips = db.ListField(required=False)
    url = db.StringField(required=False)
    port = db.StringField(required=False)
    domain_ip = db.StringField(required=False)
    docker_meta = db.StringField(required=False)
    meta = {
        'collection': 'compute_ins',
        'index': [
            {
                'fields': ['ins_name', 'ins_id'],
                'sparse': True,
                }
            ],
        'index_background': True
        }


class DBIns(db.EmbeddedDocument):
    ins_name = db.StringField(required=True)
    ins_id = db.StringField(required=True, unique=True)
    ins_type = db.StringField(required=False)
    cpu = db.IntField(required=False)
    mem = db.IntField(required=False)
    disk = db.IntField(required=False)
    quantity = db.IntField(required=False, default_value=0)
    version = db.StringField(required=False)
    meta = {
        'collection': 'db_ins',
        'index': [
            {
                'fields': ['ins_name', 'ins_id'],
                'sparse': True,
                }
            ],
        'index_background': True
        }


class ResourceModel(db.DynamicDocument):
    resource_name = db.StringField(required=True)
    project = db.StringField(required=True)
    project_id = db.StringField(required=False)
    department = db.StringField(required=True)
    department_id = db.StringField(required=True)
    res_id = db.StringField(required=True, unique=True)
    user_name = db.StringField(required=False)
    user_id = db.StringField(required=False)
    # created_date = db.DateTimeField(default=datetime.datetime.now())
    created_date = db.DateTimeField(required=False)
    domain = db.StringField(required=False)
    env = db.StringField(required=True, unique_with= 'resource_name')
    application_status = db.StringField(required=False)
    approval_status = db.StringField(required=False)
    reservation_status = db.StringField(required=False)
    resource_list = db.ListField(db.EmbeddedDocumentField('DBIns'))
    compute_list = db.ListField(db.EmbeddedDocumentField('ComputeIns'))
    cmdb_p_code = db.StringField(requeired=False)

    meta = {
        'collection': 'resources',
        'indexes': [
            {
                'fields': ['res_id', ('resource_name', 'env')],
                'sparse': True,
                }
            ],
        'index_background': True
        }


class Approval(db.DynamicDocument):
    approval_id = db.StringField(required=True, max_length=50, unique=True)
    resource_id = db.StringField(required=True, unique=True)
    project_id = db.StringField(required=True)
    department_id = db.StringField(required=True)
    creator_id = db.StringField(required=True)
    create_date = db.DateTimeField(default=datetime.datetime.now())
    approve_uid = db.StringField(required=False)
    approve_date = db.DateTimeField(required=False)
    # processing/success/failed
    approval_status = db.StringField(required=True)
    annotations = db.StringField(max_length=50, required=False)
    meta = {
        'collection': 'approval',
        'index': [
            {
                'fields': ['resource_id', 'approval_status'],
                'sparse': True,
                }
            ],
        'index_background': True
    }

class ItemInformation(db.DynamicDocument):
    user = db.StringField(required=True)
    user_id = db.StringField(required=True)
    item_id = db.StringField(required=True)
    item_name = db.StringField(required=True, unique=True)
    item_code = db.StringField(required=True)
    item_depart = db.StringField(required=True)
    item_description = db.StringField(required=False)
    create_date = db.DateTimeField(default=datetime.datetime.now)

    meta = {
        'collection': 'item_information',
        'index': [
            {
                'fields': ['item_id'],
                'sparse': True,
                }
            ],
        'index_background': True
    }

#class ConfigureEnv(db.DynamicDocument):
class ConfigureEnvModel(db.Document):
    id = db.StringField(required=True, max_length=50, unique=True, primary_key=True)
    name = db.StringField(required=False, max_length=50)

    meta = {
            "collection": "configure_env",
            "index": [{
                'fields': ['id'],
                'unique': True,
                }]
            }

class ConfigureDisconfModel(db.Document):
    id = db.StringField(required=True, max_length=50, unique=True, primary_key=True)
    env = db.StringField(required=False, max_length=50)
    name = db.StringField(required=False, max_length=50)
    username = db.StringField(required=False, max_length=50)
    password = db.StringField(required=False, max_length=50)
    ip = db.StringField(required=False, max_length=50)
    url = db.StringField(required=False, max_length=50)

    meta = {
            "collection": "configure_disconf",
            "index": [{
                'fields': ['id'],
                'unique': True,
                }]
            }


class ConfigureNginxModel(db.Document):
    id = db.StringField(required=True, max_length=50, unique=True, primary_key=True)
    env = db.StringField(required=False, max_length=50)
    name = db.StringField(required=False, max_length=50)
    ip = db.StringField(required=False, max_length=50)

    meta = {
            "collection": "configure_nginx",
            "index": [{
                'fields': ['id'],
                'unique': True,
                }]
            }

