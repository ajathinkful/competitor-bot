import json
import logging
import os
from typing import Dict, List

from boto3 import client, Session
from botocore.exceptions import ClientError

# from app.utils import remove_external_email_addresses


class AWSService:
    def __init__(self):
        self.ses_client = client("ses", region_name="us-east-2")
        self.ssm_contacts_client = client("ssm-contacts", region_name="us-east-2")
        self.session = Session(
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            aws_session_token=self.session_token,
        )
        self.s3_client = self.session.client("s3", region_name="us-east-2")

    @property
    def access_key_id(self):
        return os.getenv("AWS_ACCESS_KEY_ID")

    @property
    def session_token(self):
        return os.getenv("AWS_SESSION_TOKEN")

    @property
    def secret_access_key(self):
        return os.getenv("AWS_SECRET_ACCESS_KEY")