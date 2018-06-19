# -*- coding: utf-8 -*-
import os
import json
APP_ENV = "testing"
basedir = os.path.abspath(os.path.dirname(__file__))

DEV_CRP_URL = "http://crp-dev.syswin.com/"
TEST_CRP_URL = "http://crp-test.syswin.com/"
PROD_CRP_URL = "http://crp.syswin.com/"


def get_entity_from_local_file():
    with open(basedir + "/uop/entity.txt", "rb") as f:
        entity = json.load(f)
        CMDB2_ENTITY = {
            "Person": entity.get("Person", ""),
            "department": entity.get("department", ""),
            "yewu": entity.get("yewu", ""),
            "Module": entity.get("Module", ""),
            "project": entity.get("project", ""),
            "host": entity.get("host", ""),
            "container": entity.get("container", ""),
            "virtual_device": entity.get("virtual_device", ""),
            "tomcat": entity.get("tomcat", ""),
            "mysql": entity.get("mysql", ""),
            "redis": entity.get("redis", ""),
            "mongodb": entity.get("mongodb", ""),
            "nginx": entity.get("nginx", ""),
            "rabbitmq": entity.get("rabbitmq", ""),
            "codis": entity.get("codis", ""),
            "apache": entity.get("apache", ""),
            "zookeeper": entity.get("zookeeper", ""),
            "mycat": entity.get("mycat", "")
        }
        CMDB2_VIEWS = {
            # 注意：定时任务只会缓存1，2，3 三个视图下的基础模型数据
            "1": ("B7", u"工程 --> 物理机，用于拿到各层间实体关系信息", entity.get("project", "")),  # （视图名，描述，起点实体id）
            "2": ("B6", u"部门 --> 资源，用于分级展示业务模块工程", entity.get("department", "")),
            "3": ("B5", u"人 --> 部门 --> 工程", entity.get("Person", "")),

            "4": ("B8", u"tomcat --> 机房，展示tomcat资源视图", entity.get("tomcat", "")),
            "5": ("B9", u"mysql --> 机房，展示mysql资源视图", entity.get("mysql", "")),
            "6": ("B10", u"mongodb--> 机房，展示mongodb资源视图", entity.get("mongodb", "")),
            "7": ("B11", u"redis --> 机房，展示redis资源视图", entity.get("redis", "")),
            "8": ("B12", u"物理机信息", entity.get("host", "")),
            "9": ("B13", u"模块 --> 物理机，用于拿到各层间实体关系信息", entity.get("Module", "")),
            "10": ("B14", u"nginx --> 机房，展示nginx资源视图", entity.get("nginx", "")),
            "11": ("B15", u"rabbitmq --> 机房，展示rabbitmq资源视图", entity.get("rabbitmq", "")),
            "12": ("B16", u"codis --> 机房，展示codis资源视图", entity.get("codis", "")),
            "13": ("B17", u"apache --> 机房，展示apache资源视图", entity.get("apache", "")),
            "14": ("B18", u"zookeeper --> 机房，展示zookeeper资源视图", entity.get("zookeeper", "")),
            "15": ("B19", u"mycat --> 机房，展示mycat资源视图", entity.get("mycat", "")),
            # "5": ("B3", u"资源 --> 机房"),
        }
        return CMDB2_ENTITY, CMDB2_VIEWS


class BaseConfig:
    DEBUG = False

class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True

    # Connect to mongo cluster. mongo_url is valid.
    MONGODB_SETTINGS = {
        'host': 'mongodb://uop:uop@mongo-1:28010,mongo-2:28010,mongo-3:28010/uop',
    }


    CRP_URL = {
        'dev': DEV_CRP_URL,
        'test': TEST_CRP_URL,
        'prod': PROD_CRP_URL,
    }
    
    #CMDB_URL = "http://cmdb-test.syswin.com/" #如果是None 不走cmdb1,0
    CMDB_URL = None
    CMDB2_URL = "http://cmdb2-test.syswin.com/"
    CMDB2_OPEN_USER = "uop"
    #CMDB2_VIEWS = {
    #    "1": ("B7", u"工程 --> 物理机"),
    #    "2": ("B6", u"部门 --> 业务 --> 资源"),
    #    "3": ("B5", u"人 --> 部门 --> 工程"),
    #    "4": ("B4", u"资源 --> 环境 --> 机房"),
    #    # "5": ("B3", u"资源 --> 机房"),
    #}
    UPLOAD_FOLDER = "/data/"

    data = get_entity_from_local_file()

    CMDB2_ENTITY = data[0]
    CMDB2_VIEWS = data[1]
    UOPCODE_CMDB2 = {
        data[0]['yewu']: 'business',
        data[0]['Module']: 'module',
        data[0]['project']: 'project'
    }
    # print "The data is {}\n{}\n".format(CMDB2_ENTITY, CMDB2_VIEWS)

    # CMDB知识库变动时，需要改动，或添加
    # CMDB2_ENTITY = {
    #     "Person": "d8098981df71428784e65427",
    #     "department": "9a544097f789495e8ee4f5eb",
    #     "yewu": "c73339db70cc4647b515eaca",
    #     "Module": "9e97b54a4a54472e9e913d4e",
    #     "project": "59c0af57133442e7b34654a3",
    #     "host": "b593293378c74ba6827847d3",
    #     "container": "d0f338299fa34ce2bf5dd873",
    #     "virtual_device": "d4ad23e58f31497ca3ad2bab",
    #     "tomcat": "d1b11a713e8842b2b93fe397",
    #     "mysql": "e5024d360b924e0c8de3c6a8",
    #     "redis": "de90d618f7504723b677f196",
    #     "mongodb": "9bc4a41eb6364022b2f2c093",
    # }
    # UOPCODE_CMDB2 = {
    #     "c73339db70cc4647b515eaca": "business",
    #     "9e97b54a4a54472e9e913d4e": "module",
    #     "59c0af57133442e7b34654a3": "project"
    # }

    # CMDB知识库变动时，改动此字典与 CMDB2_ENTITY 保持一致即可，为确保查询性能，稍有冗余，但同一起点的实体id只能有一个视图
    # CMDB2_VIEWS = {
    #     # 注意：定时任务只会缓存1，2，3 三个视图下的基础模型数据
    #     "1": ("B7", u"工程 --> 物理机，用于拿到各层间实体关系信息", "59c0af57133442e7b34654a3"),     # （视图名，描述，起点实体id）
    #     "2": ("B6", u"部门 --> 资源，用于分级展示业务模块工程", "9a544097f789495e8ee4f5eb"),
    #     "3": ("B5", u"人 --> 部门 --> 工程", "d8098981df71428784e65427"),
    #
    #     "4": ("B8", u"tomcat --> 机房，展示tomcat资源视图", "d1b11a713e8842b2b93fe397"),
    #     "5": ("B9", u"mysql --> 机房，展示mysql资源视图", "e5024d360b924e0c8de3c6a8"),
    #     "6": ("B10", u"mongodb--> 机房，展示mongodb资源视图", "9bc4a41eb6364022b2f2c093"),
    #     "7": ("B11", u"redis --> 机房，展示redis资源视图", "de90d618f7504723b677f196"),
    #     "8": ("B12", u"物理机信息", "b593293378c74ba6827847d3"),
    #     # "5": ("B3", u"资源 --> 机房"),
    # }

    UPLOAD_FOLDER = "/data/"
    BASE_K8S_IMAGE = "reg1.syswin.com/base/uop-base-k8s:v-1.0.1"
    K8S_NGINX_PORT = "80"
    K8S_NGINX_IPS = ["172.28.13.5"]
    ADMIN_EMAILS = ["zhanghai@syswin.com"]

configs = {
    'testing': TestingConfig,
}
