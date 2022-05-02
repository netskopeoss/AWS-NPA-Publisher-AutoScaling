import boto3
from datetime import datetime, timezone
import json
import requests
import os
from os import listdir
from os.path import isfile, join
import base64
from utils.logger import Logger
import time

# Set up  logger
LOG_LEVEL = os.getenv('LOGLEVEL', 'info')
logger = Logger(loglevel=LOG_LEVEL)


AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
tenant_fqdn = os.environ['tenant_fqdn']
#secret_name = os.environ['api_token'].split("/")[1]
secret_name = os.environ['api_token']

def lambda_handler(event, context):
    logger.info('Got event ' + json.dumps(event))
    try: 
        if (event['source'] != 'aws.autoscaling'):
            logger.info('Got non-autoscalling event..')
            return
        
        autoscalling_groupname=event['detail']['AutoScalingGroupName']
        EC2InstanceId=event['detail']['EC2InstanceId']
        account_id=event['account']
        LifecycleHookName=event['detail']['LifecycleHookName']
        LifecycleActionToken=event['detail']['LifecycleActionToken']
        token = json.loads(get_secret(secret_name))['token']
     
        publisher_name = autoscalling_groupname + "-" + account_id + '-' + EC2InstanceId 
        
        if (event['detail-type'] == 'EC2 Instance-terminate Lifecycle Action'):
            logger.info('Got Instance-terminate event..')
            #getting publisher id
            api_url='/api/v2/infrastructure/publishers'
            publisher_id=0
            resp = call_netskope_api ('get', api_url, token, '')
            publishers=resp['data']['publishers']
            for publisher in publishers:
                if (publisher['publisher_name']==publisher_name):
                    publisher_id=publisher['publisher_id']
                    break
            if publisher_id==0:
                logger.error('Got event to deprovision non-existing publisher '+ publisher_name+ '. Exiting..')
                return
        
            api_url='/api/v2/steering/apps/private'
            resp = call_netskope_api ('get', api_url, token, '')
            if (resp['status'] != 'success'):
                logger.error('Got error while calling '+ api_url)
                logger.error('Response '+ json.dumps(resp))
                return
            
            private_apps=resp['data']['private_apps']
            for app in private_apps:
                if app['app_name'].find(autoscalling_groupname) == -1:
                    continue
                logger.info('Found the private app '+ app['app_name'] + ' using publisher group ' + autoscalling_groupname)
                private_app_id = app['app_id']
                api_url='/api/v2/steering/apps/private/' + str(private_app_id)
                service_publisher_assignments = app['service_publisher_assignments']
                i=0
                publisher_used=0
                for pub in service_publisher_assignments:
                    if pub['publisher_id']==publisher_id:
                        logger.info('Publisher '+ publisher_name+ ' is in use by the application '+app['app_name'])
                        publisher_used=1
                        del service_publisher_assignments[i]
                    i=i+1
                if publisher_used==0:
                    logger.info('Publisher '+ publisher_name+ ' is not in use by the  '+app['app_name'])
                    continue
                payload={'publishers' : service_publisher_assignments}
                resp = call_netskope_api ('patch', api_url, token, payload) 
                if (resp['status'] != 'success'):
                    logger.error('Got error while calling '+ str(api_url))
                    logger.error('Response '+ json.dumps(resp))
                    return
                logger.info('Updated the private app '+ app['app_name'] + ' to remove publisher ' + publisher_name)
            api_url='/api/v2/infrastructure/publishers/'+str(publisher_id)
            resp = call_netskope_api ('delete', api_url, token, '')
            if (resp['status'] != 'success'):
                logger.error('Got error while calling '+ api_url)
                logger.error('Response '+ json.dumps(resp))
                return
            logger.info('Successfully deleted publisher '+ publisher_name)
            autoscaling = boto3.client('autoscaling')
            response = autoscaling.complete_lifecycle_action(
                AutoScalingGroupName=autoscalling_groupname, 
                LifecycleActionResult='CONTINUE',
                LifecycleHookName=LifecycleHookName, 
                InstanceId=EC2InstanceId, 
                LifecycleActionToken=LifecycleActionToken
            )
            return
        if (event['detail-type'] == 'EC2 Instance-launch Lifecycle Action'):
            logger.info('Got Instance-launch event..')
            logger.info('Creating a new publisher ')
            api_url='/api/v2/infrastructure/publishers'
            payload={'name' : publisher_name}
            resp = call_netskope_api ('post', api_url, token, payload)
            if (resp['status'] != 'success'):
                if (resp['message'].find('may exist already')!=-1):
                    logger.info('Publisher already exists. Continue with provisioning it..')
                    resp = call_netskope_api ('get', api_url, token, '')
                    publishers=resp['data']['publishers']
                    for publisher in publishers:
                        if (publisher['publisher_name']==publisher_name):
                            publisher_id=publisher['publisher_id']
                            break
                else:
                    logger.errpr('Got error while calling '+ api_url)
                    logger.error('Response '+ json.dumps(resp))
                    return
            else: 
                publisher_id=resp['data']['id']
            logger.info('Publisher id is '+str(publisher_id))
            logger.info('Getting registration token...')
            
            api_url='/api/v2/infrastructure/publishers/'+str(publisher_id)+'/registration_token'
            resp = call_netskope_api ('post', api_url, token, '')
            if (resp['status'] != 'success'):
                logger.error('Got error while calling '+ api_url)
                logger.error('Response '+ json.dumps(resp))
                return
            reg_token=resp['data']['token']
            
            ssm_client = boto3.client('ssm')
            #response = ssm_client.describe_instance_information(InstanceInformationFilterList=[{'key': 'InstanceIds','valueSet': [EC2InstanceId]}])
            instance_ready=0
            for i in range(10):
                response = ssm_client.describe_instance_information( Filters=[
                    {'Key': 'InstanceIds','Values': [EC2InstanceId]}])
                if response['ResponseMetadata']['HTTPStatusCode'] != 200:
                    logger.error('Got error while calling describe_instance_information, but keep retrying')
                    logger.error('Response '+ json.dumps(resp))
                if len(response['InstanceInformationList'])==0:
                    logger.info('Instance is not registered in SSM. Waiting and retrying..')
                    time.sleep(30)
                    continue
                else:
                    if response['InstanceInformationList'][0]['PingStatus']=='Online':
                        logger.info('Instance is registered in SSM. Continue provisioning')
                        instance_ready=1
                        break
                    else:
                        time.sleep(30)
                        continue
            if instance_ready ==0:
                logger.info('Instance is not registered in SSM. Exiting..')
                return
            command="sudo /home/ubuntu/npa_publisher_wizard -token " + "\""+ reg_token + "\""
            response = ssm_client.send_command(
                InstanceIds=[EC2InstanceId],
                DocumentName="AWS-RunShellScript",
                Comment='Registering NPA publisher',
                Parameters={'commands':[command]}
                )
    
            command_id = response['Command']['CommandId']
            time.sleep(5)
            output = ssm_client.get_command_invocation(CommandId=command_id,InstanceId=EC2InstanceId)
            logger.info('Successfully provisioned the publisher. Check SSM RunCommand if there are any issues.')
           
           
            autoscaling = boto3.client('autoscaling')
            response = autoscaling.complete_lifecycle_action(
                AutoScalingGroupName=autoscalling_groupname, 
                LifecycleActionResult='CONTINUE',
                LifecycleHookName=LifecycleHookName, 
                InstanceId=EC2InstanceId, 
                LifecycleActionToken=LifecycleActionToken
            )
            if (response['ResponseMetadata']['HTTPStatusCode'] != 200):
                logger.error('Got error calling complete_lifecycle_action '+ json.dumps(response))
                logger.error('Cannot add publisher'+ publisher_name)
                return
          
            api_url='/api/v2/steering/apps/private'
            resp = call_netskope_api ('get', api_url, token, '')
            if (resp['status'] != 'success'):
                logger.error('Got error while calling '+ api_url)
                logger.error('Response '+ json.dumps(resp))
                return
            
            private_apps=resp['data']['private_apps']
            for app in private_apps:
                if app['app_name'].find(autoscalling_groupname) == -1:
                    continue
                logger.info('Found the private app '+ app['app_name'] + ' using publisher group ' + autoscalling_groupname)
                private_app_id = app['app_id']
                api_url='/api/v2/steering/apps/private/' + str(private_app_id)
                service_publisher_assignments = app['service_publisher_assignments']
                if_publisher_already_used=0
                for pub in service_publisher_assignments:
                    if pub['publisher_id']==publisher_id:
                        if_publisher_already_used=1
                        logger.info('Publisher '+ publisher_name+ ' is already in use by the application '+app['app_name'])
                        break
                if if_publisher_already_used==1:
                    continue
                service_publisher_assignments.append({'publisher_id':publisher_id})
                payload={'publishers' : service_publisher_assignments}
                print(json.dumps(payload))
                resp = call_netskope_api ('patch', api_url, token, payload) 
                if (resp['status'] != 'success'):
                    logger.error('Got error while calling '+ str(api_url))
                    logger.error('Response '+ json.dumps(resp))
                    return
                logger.info('Updated the private app '+ app['app_name'] + ' to use publisher ' + publisher_name)
            return
        logger.info('Got unknown autoscaling event. Exiting...')
            
    except Exception as e:
         logger.error('Got exception '+ str(e))
         logger.error('Exiting with error')
        
  

def call_netskope_api(method, api_url, token, req_payload):
    #from http.client import HTTPConnection  # py3

    #log = logging.getLogger('urllib3')
    #log.setLevel(logging.DEBUG)
    
    # logging from urllib3 to console
    #ch = logging.StreamHandler()
    #ch.setLevel(logging.DEBUG)
    #log.addHandler(ch)
    
    # print statements from `http.client.HTTPConnection` to console/stdout
    #HTTPConnection.debuglevel = 1
    get_url = 'https://' + tenant_fqdn + api_url
    req_headers = {'Netskope-Api-Token' : token, 'accept' : "application/json"}
    logger.info('Calling Netskope API for ' + api_url )
    action = getattr(requests, method)
    r = action(headers=req_headers, json=req_payload, url=get_url)
    print(r.json())
    return (r.json())

def get_secret(secret_name):

    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=AWS_REGION
    )

    # In this sample we only handle the specific exceptions for the 'GetSecretValue' API.
    # See https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
    # We rethrow the exception by default.

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'DecryptionFailureException':
            # Secrets Manager can't decrypt the protected secret text using the provided KMS key.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InternalServiceErrorException':
            # An error occurred on the server side.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            # You provided an invalid value for a parameter.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            # You provided a parameter value that is not valid for the current state of the resource.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'ResourceNotFoundException':
            # We can't find the resource that you asked for.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
    else:
        # Decrypts secret using the associated KMS CMK.
        # Depending on whether the secret is a string or binary, one of these fields will be populated.
        secret = get_secret_value_response['SecretString']
    return(secret)
    