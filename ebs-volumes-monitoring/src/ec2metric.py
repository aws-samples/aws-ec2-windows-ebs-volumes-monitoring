import boto3
from datetime import datetime, timedelta

cloudwatch = boto3.client('cloudwatch')
ec2 = boto3.resource('ec2')

# get UTC time of 1 hr difference
T1 = datetime.utcnow() - timedelta(hours=1)
T2 = datetime.utcnow()


def generate_metric_output(cw_namespace: str, cw_metric_name: str, cw_dimensions: list, cw_starttime: datetime, cw_endtime: datetime): 
    return cloudwatch.get_metric_statistics(
                              Namespace =cw_namespace,
                              MetricName = cw_metric_name,
                              Dimensions = cw_dimensions,
                              StartTime = cw_starttime,
                              EndTime = cw_endtime,
                              Period = 600,
                              Statistics = ['Minimum'] )


def generate_alarm(alrm_names: str, alrm_comp_operand: str, alrm_comp_alaram_actions: list, 
                                alrm_metric: str, alrm_namespace: str,alrm_statistics: str, alrm_dimensions: str, alrm_thresholds: list):
    try:
        for alarm_name,threshold_value in zip(alrm_names, alrm_thresholds):
            print("alaram_name", alarm_name)
            print("threshold_value", threshold_value)

            cloudwatch.put_metric_alarm(
                AlarmName= alarm_name,
                ComparisonOperator=alrm_comp_operand,
                ActionsEnabled=True,
                AlarmActions=alrm_comp_alaram_actions,
                MetricName =alrm_metric,
                Namespace = alrm_namespace,
                Statistic = alrm_statistics,
                Dimensions=alrm_dimensions, 
                Period = 43200,
                EvaluationPeriods= 1,
                DatapointsToAlarm= 1,
                Threshold = threshold_value,
                TreatMissingData= 'missing' )
        
        return True, None
    except Exception as e:
        return False, str(e)
        

def lambda_handler(event, context):
    try:

        CW_AGENT_NAME_SPACE = 'CWAgent'
        FREE_MEGA_BYTE_PARAMETER = 'FreeStorageSpaceInMB'
        FREE_STORAGE_SPACE_PARAMETER = 'FreeStorageSpaceInPercent'
        response_data = []

        SERVERS = event['hostname']
        sns_topic_name=event['sns_topic_name']
        print("Instance Name = ",SERVERS)
        instances = ec2.instances.filter(Filters=[{'Name': 'tag:Name', 'Values': [SERVERS]}])
        paginator = cloudwatch.get_paginator('list_metrics')      

        for each_instance in instances:
            for i in each_instance.tags:
                if i['Key'] == 'Name':
                    print(i['Value'])
                    server_name=i['Value']
                
            response = paginator.paginate(MetricName='FreeStorageSpaceInPercent',Namespace='CWAgent', Dimensions=[{'Name': 'instance'},{'Name': 'InstanceId', 'Value': each_instance.instance_id}])
            
            for each in response:
                metric_data_response= each['Metrics']
                
                if metric_data_response:
                    print(metric_data_response.__len__)
            
                    i=0
                    while i < len(metric_data_response):
                      
                        dimension_list = metric_data_response[i]['Dimensions']
                        
                        volume_name = list((dimension_list)[0].values())[1]
                        print(volume_name)
                        
                        storage_space = generate_metric_output(
                            cw_namespace= CW_AGENT_NAME_SPACE, 
                            cw_metric_name= FREE_STORAGE_SPACE_PARAMETER, 
                            cw_dimensions = dimension_list,
                            cw_starttime = T1,
                            cw_endtime = T2 )
        
                        try:
                
                            storage_space_datapoints = storage_space['Datapoints']
                            storage_volume = round(list((storage_space_datapoints)[0].values())[1])
                               
                            free_storage = generate_metric_output(
                                cw_namespace= CW_AGENT_NAME_SPACE, 
                                cw_metric_name= FREE_MEGA_BYTE_PARAMETER, 
                                cw_dimensions = dimension_list,
                                cw_starttime = T1,
                                cw_endtime = T2 )
                                
                            free_storage_datapoints = (free_storage['Datapoints'])
                            free_volume =   round(list((free_storage_datapoints)[0].values())[1])
            
                            total_volume_left = ( (storage_volume/ free_volume)*100/1024 )
            
                            if storage_volume == 0 or free_volume == 0:
            
                                Total = 0
                                print('This Server %s  %s Drive Size has 0MB'  % (host,volume_name))
            
                            if total_volume_left < 500:
                                Threshold_warning = 30
                                Threshold_critical= 20
                            else:
                                Threshold_warning= 15
                                Threshold_critical=10
                            
                            response, error = generate_alarm(
                                alrm_names=['%s-Warning-DiskFreeSpace-Alert_volume-%s,instance-%s' % (server_name, volume_name, each_instance.instance_id), '%s-CRITICAL-DiskFreeSpace-Alert_volume-%s,instance-%s' % (server_name, volume_name, each_instance.instance_id)],
                                alrm_comp_operand= 'LessThanThreshold', 
                                alrm_comp_alaram_actions= [sns_topic_name],
                                alrm_metric= FREE_STORAGE_SPACE_PARAMETER, 
                                alrm_namespace= CW_AGENT_NAME_SPACE, 
                                alrm_statistics= 'Minimum',
                                alrm_dimensions= dimension_list, 
                                alrm_thresholds= [Threshold_warning, Threshold_critical] )
                            
                            if error:
                                print(f"Error at generating alarms logged as {error}")

                        except Exception as e:
                            print(f"Error generated !!! - {str(e)}")
            
                        i += 1
                            
        
        print({"status_code": 'successfully completed'})

    except Exception as e:
        print(f"Error generated !!! - {str(e)}")
