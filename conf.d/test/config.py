# -*- coding: utf-8 -*-
import os

APP_ENV = "testing"
basedir = os.path.abspath(os.path.dirname(__file__))

DEV_CRP_URL = "http://crp-dev.syswin.com/"
TEST_CRP_URL = "http://crp-test.syswin.com/"
PROD_CRP_URL = "http://crp.syswin.com/"


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
    
    CMDB_URL = "http://cmdb-test.syswin.com/"
    CMDB2_URL = "http://cmdb2.syswin.com/"

    UPLOAD_FOLDER = "/data/"


configs = {
    'testing': TestingConfig,
}
