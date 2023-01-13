# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import boto3 # type: ignore
import json
import os
import urllib3 # type: ignore
from aws_lambda_powertools import Tracer # type: ignore
from aws_lambda_powertools import Logger # type: ignore
import distutils
from distutils import util

tracer = Tracer(service="aws-account-closure-notifier")
logger = Logger(service="aws-account-closure-notifier")
sns_client = boto3.client('sns')

SLACK_ENDPOINT = os.environ.get('SLACK_ENDPOINT')
SLACK_NOTIFICATION = distutils.util.strtobool(os.environ.get("SLACK_NOTIFICATION", "false"))
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")

@tracer.capture_method
def send_sns_notification(message_detail):
    """
    Function to send SNS Notification to target SNS topic

    Parameters:
        message_detail (dict): The CloudTrail message object
    """
    try:
        response=sns_client.publish(
            TopicArn = SNS_TOPIC_ARN,
            Subject = f"AWS {message_detail.get('eventName')} Notification",
            Message = f"{message_detail.get('eventName')} action has been made for Account" \
                        f" {message_detail.get('requestParameters').get('accountId')}\n\n" \
                        f"Action: {message_detail.get('eventName')} \n" \
                        f"   Target Account: {message_detail.get('requestParameters').get('accountId')}\n" \
                        f"   Calling Principal: {message_detail.get('userIdentity').get('principalId').split(':')[1]} \n" \
                        f"   TimeStamp: {message_detail.get('eventTime')}")
        logger.info(f"Successfully sent SNS notification for {message_detail.get('eventName')} event of account {message_detail.get('requestParameters').get('accountId')}")
    except Exception as error:
        logger.exception(f"Failed to send SNS notification: {error}")

@tracer.capture_method
def send_slack_notification(message_detail):
    """
    Function to send Slack Notification to target Slack Webhook

    Parameters:
        message_detail (dict): The CloudTrail message object
    """
    message_body = json.dumps(
            {
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"AWS {message_detail.get('eventName')} Notification"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Action:*\n{message_detail.get('eventName')}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Target Account:*\n{message_detail.get('requestParameters').get('accountId')}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Calling Principal:*\n{message_detail.get('userIdentity').get('principalId').split(':')[1]}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*TimeStamp:*\n{message_detail.get('eventTime')}"
                            }
                        ]
                    }
                ]
            }
        )
    
    try:
        http = urllib3.PoolManager()
        response = http.request(
            'POST',
            SLACK_ENDPOINT,
            headers={'Content-Type': 'application/json'},
            body=message_body
        )
        logger.debug(f"Response: {response}")
    except Exception as error:
        logger.exception(f"Failed to send SLACK notification: {error}")

@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    """
    Lambda handler for the Account Closure Notifier function

    This Lambda will send a notification to SNS/Slack when CloudTrail receives an event 
    signifying an account closure or an account leaving the organization.

    Parameters:
        event (dict): The Lambda event object
        context (dict): The Lambda context object   
    """
    message_detail = event['detail']

    if message_detail['eventName'] in ["CloseAccount", "RemoveAccountFromOrganization"]:
        logger.info(f"Received CloudWatch event of {message_detail['eventName']} API for Account ID {message_detail['requestParameters']['accountId']}")
        logger.info(f"Sending SNS Notification for received event {message_detail['eventName']}")
        send_sns_notification(message_detail)
        if SLACK_NOTIFICATION:
            logger.info(f"Sending SLACK Notification for received event {message_detail['eventName']}")
            send_slack_notification(message_detail)
    else:
        logger.info("Event received is not associated with CloseAccount/RemoveAccountFromOrganization API call")
