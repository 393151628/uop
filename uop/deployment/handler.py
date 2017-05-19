# -*- coding: utf-8 -*-
import uuid
from flask_restful import reqparse, abort, Api, Resource, fields, marshal_with
from uop.deployment import deployment_blueprint
from uop.models import Deployment
from uop.deployment.errors import deploy_errors

deployment_api = Api(deployment_blueprint, errors=deploy_errors)


class DeploymentListAPI(Resource):

    def get(self):
        deployments = []
        for deployment in Deployment.objects:
            deployments.append({
                'deploy_id': deployment.deploy_id,
                'deploy_name': deployment.deploy_name,
                'initiator': deployment.initiator,
                'project_name': deployment.project_name,
                'environment': deployment.environment,
                'exec_tag': deployment.exec_tag,
                'exec_context': deployment.exec_context,
                'app_image': deployment.app_image,
                'created_time': str(deployment.created_time)
            })

        return deployments, 200

    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('deploy_name', type=str)
        parser.add_argument('initiator', type=str)
        parser.add_argument('project_name', type=str)
        parser.add_argument('environment', type=str)
        parser.add_argument('exec_tag', type=str)
        parser.add_argument('exec_context', type=str)
        parser.add_argument('app_image', type=str)
        args = parser.parse_args()

        deploy_name = args.deploy_name
        initiator = args.initiator
        project_name = args.project_name
        environment = args.environment
        exec_tag = args.exec_tag
        exec_context = args.exec_context
        app_image = args.app_image

        Deployment(
            deploy_id=str(uuid.uuid1()),
            deploy_name=deploy_name,
            initiator=initiator,
            project_name=project_name,
            environment=environment,
            exec_tag=exec_tag,
            exec_context=exec_context,
            app_image=app_image).save()

        res = {
            "code": 200,
            "result": {
                "res": "success",
                "msg": "create deployment success"
            }
        }
        return res, 200


class DeploymentDetailAPI(Resource):

    def get(self, initiator):
        """
        按发起人查询
        """
        data = []
        try:
            deploy_res = Deployment.objects.filter(initiator=initiator)
            for i in deploy_res:
                data.append(
                    {
                        'deploy_id': i.deploy_id,
                        'deploy_name': i.deploy_name,
                        'initiator': i.initiator,
                        'project_name': i.project_name,
                        'environment': i.environment,
                        'exec_tag': i.exec_tag,
                        'exec_context': i.exec_context,
                        'app_image': i.app_image,
                        'created_time': str(i.created_time)
                    }
                    )
            res = data
        except Deployment.DoesNotExist:
            res = None
        return res


class DeploymentTimeApi(Resource):

    def get(self, start_time, end_time):
        """
        按时间查询
        """
        data = []
        try:
            deploy_res = Deployment.objects.filter(created_time__gte=start_time, created_time__lt=end_time)
            for i in deploy_res:
                data.append(
                    {
                        'deploy_id': i.deploy_id,
                        'deploy_name': i.deploy_name,
                        'initiator': i.initiator,
                        'project_name': i.project_name,
                        'environment': i.environment,
                        'exec_tag': i.exec_tag,
                        'exec_context': i.exec_context,
                        'app_image': i.app_image,
                        'created_time': str(i.created_time)
                    }
                    )
            res = data
        except Deployment.DoesNotExist:
            res = None
        return res


class DeploymentAPI(Resource):

    def delete(self, deploy_id):
        res_code = 204
        deploys = Deployment.objects(deploy_id=deploy_id)
        if deploys.count() > 0:
            deploys.delete()
        else:
            res_code = 404
        return "", res_code

deployment_api.add_resource(DeploymentListAPI, '/deployments')
deployment_api.add_resource(DeploymentAPI, '/deployments/<deploy_id>')
deployment_api.add_resource(DeploymentDetailAPI, '/deploy_detail/<initiator>')
deployment_api.add_resource(DeploymentTimeApi, '/deploy_time/<start_time>/<end_time>')
