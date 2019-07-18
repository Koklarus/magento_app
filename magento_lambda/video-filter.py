import boto3
import json
import os
from time import sleep
import logging
import ast

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3') 
sqs = boto3.client('sqs')

jobFound = False
non_compliant = set(ast.literal_eval(os.environ['LabelsFilter']))
DestinationBucket = os.environ['DestinationBucket']
region = os.environ['Region']

def handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        logger.info("Starting labels detection triggered by S3 object creation: \n {0}".format(event))
        detect_labels(bucket, key)
    
def detect_labels(bucket, key, max_labels=10, min_confidence=70, region=region):
	finish = False
	rekognition = boto3.client("rekognition", region)
	request = rekognition.start_label_detection(Video={'S3Object': {'Bucket': bucket, 'Name': key}})
	jobId = request['JobId']
	while finish == False:
		response = rekognition.get_label_detection(JobId=jobId, MaxResults=10,NextToken='', SortBy='TIMESTAMP')
		logger.info("Job ID {0} Status: \n {1}".format(jobId,response))
		sleep(2)
		if response['Labels']:
			found_keys = set([item['Label']['Name'] for item in response['Labels']])
			logger.info("Rekognition labels found: \n {0}".format(response['Labels']))
			if set(non_compliant).intersection(found_keys):
				logger.info("Following non-compliant patterns have been detected: \n {0}".format(non_compliant.intersection(found_keys)))
				s3_client.delete_object(Bucket = bucket, Key = key)
				logger.info("Video {0} has been removed from initial bucket {1} ".format(key, bucket))
			else:
				logger.info("Following patterns have been detected: \n {0}".format(found_keys))
				logger.info("Video {0} has passed compliance check.".format(key))
				s3_resource.meta.client.copy({'Bucket': bucket, 'Key': key}, DestinationBucket, key)
				logger.info("Video {0} has been moved to publicly accessable bucket {1} ".format(key, DestinationBucket))
				s3_client.delete_object(Bucket = bucket, Key = key)
				logger.info("Video {0} has been removed from initial bucket {1} ".format(key, bucket))
			finish = True