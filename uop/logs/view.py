# -*- coding: utf-8 -*-

import json
import requests
import datetime
from flask_restful import reqparse, Api, Resource, fields
from uop.logs import logs_blueprint
from uop.models import ResourceModel, Deployment
from uop.logs.errors import logs_errors
from uop.util import get_CRP_url

logs_api = Api(logs_blueprint, errors=logs_errors)

resource_fileds = {
    "resource_name": fields.String,
    "project_name": fields.String,
    "module_name": fields.String,
    "business_name": fields.String,
    "env": fields.String,
    "user_name": fields.String,
    "created_date": fields.String(
        attribute=lambda x: x.created_date.strftime("%Y-%m-%d %H:%M:%S"))
}

class LogsListApi(Resource):
    """
        构建日志列表
    """

    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('resource_name', type=str, location='args')
        parser.add_argument('project_name', type=str, location='args')
        parser.add_argument('module_name', type=str, location='args')
        parser.add_argument('business_name', type=str, location='args')
        parser.add_argument('resource_type', type=str, location='args')
        parser.add_argument('env', type=str, location='args')
        parser.add_argument('user_name', type=str, location='args')
        parser.add_argument('department', type=str, location='args')
        parser.add_argument('page_num', type=int, location='args')
        parser.add_argument('page_size', type=int, location='args')
        parser.add_argument('start_time', type=str, location='args')
        parser.add_argument('end_time', type=str, location='args')

        args = parser.parse_args()

        page_num = args.pop("page_num", 1)
        page_size = args.pop("page_size", 10)
        start_time = args.pop("start_time", None)
        end_time = args.pop("end_time", None)

        condition = {k: v for k, v in dict(args).items() if v}
        condition["is_deleted"] = 0
        condition["resource_type__in"] = ["app","kvm"]
        condition["approval_status__in"] = ["success", "failed", "revoke", "config_revoke", "config_processing"]

        departments = condition.get("department")
        if departments:
            if "admin" in departments.split(","):
                condition.pop("department")
            else:
                condition["department__in"] = departments.split(",")


        if start_time:
            condition['created_date__gte'] = start_time
        if end_time:
            condition['created_date__lte'] = end_time

        queryset = ResourceModel.objects.filter(compute_list__deploy_source='git')

        if page_num and page_size:
            skip_count = (page_num - 1) * page_size
            queryset = queryset.filter(**condition).order_by(
                '-created_date').skip(skip_count).limit(page_size)
        else:
            queryset = queryset.filter(**condition).order_by('-created_date')

        
        result = []
        for obj in queryset:
            tmp = {}
            dp = Deployment.objects.filter(
                resource_id=obj.res_id).order_by("-created_time").first()

            tmp["resource_name"] = obj.resource_name
            tmp["project_name"] = obj.project_name
            tmp["module_name"] = obj.module_name
            tmp["business_name"] = obj.business_name
            tmp["env"] = obj.env 
            tmp["user_name"] = obj.user_name
            tmp["created_date"] = obj.created_date.strftime("%Y-%m-%d %H:%M:%S")
            tmp["reservation_status"] = dp.deploy_result if dp else obj.reservation_status
            tmp["resource_type"] = obj.resource_type
            tmp["deploy_source"] = obj.compute_list[0].deploy_source
            result.append(tmp)
            

        return {
            "code": 200,
            "page_num": page_num,
            "page_size": page_size,
            "total_count": queryset.count(),
            "data": result
        }


class LogDetailApi(Resource):
    
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument(
            'resource_name', type=str, required=True, location='args')
        parser.add_argument('project_name', type=str, location='args')
        parser.add_argument('env', type=str, location='args')
        parser.add_argument('version', type=str, location='args')
        args = parser.parse_args()

        version = args.version if args.version else 1
        _env = get_CRP_url(args.env)
        crp_url = '%s%s' % (_env, 'api/deploy/log_detail')

        condition = 'resource_name={r}&project_name={p}&version={v}'.format(
            r=args.resource_name, p=args.project_name, v=version)
        request_url = "{url}?{p}".format(url=crp_url, p=condition)
        res = requests.get(request_url)
        return json.loads(res.text)


logs_api.add_resource(LogsListApi, '/log_list')
logs_api.add_resource(LogDetailApi, '/log_detail')
