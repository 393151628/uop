# -*- coding: utf-8 -*-
import os

APP_ENV = "development"
basedir = os.path.abspath(os.path.dirname(__file__))

DEV_CRP_URL = "http://172.28.32.32:8001/"
TEST_CRP_URL = "http://172.28.32.32:8001/"
PROD_CRP_URL = "http://172.28.32.32:8001/"



class BaseConfig:
    DEBUG = False

class DevelopmentConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    MONGODB_SETTINGS = {
            'db': 'uop',
            'host': '172.28.20.124',
            'port': 27017,
            'username': 'uop',
            'password': 'uop',
            }
    CRP_URL = {
        'dev': DEV_CRP_URL,
        'test': TEST_CRP_URL,
        'prod': PROD_CRP_URL,
    }
    CMDB_URL = "http://cmdb-dev.syswin.com/"


    UPLOAD_FOLDER = "/data/"
    #TODO:  move it to conf
    DISCONF_URL = 'http://172.28.11.111:8081'
    DISCONF_USER_INFO = {'name': 'admin', 'password': 'admin', 'remember': '0'}
    DISCONF_USER_CONFIG ={
                        '172.28.11.111':{'server_url':'http://172.28.11.111:8081','user_info':{'name': 'admin', 'password': 'admin', 'remember': '0'}},
                        '172.28.18.48':{'server_url':'http://172.28.18.48:8081','user_info':{'name': 'admin', 'password': 'admin', 'remember': '0'}},
                        }

configs = {
    'development': DevelopmentConfig,
}
