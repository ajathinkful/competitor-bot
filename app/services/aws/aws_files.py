import logging
from io import BytesIO

from botocore.exceptions import ClientError

from app.services.aws import AWSService
from app.services.file_service import FileService


class AWSFilesService(AWSService, FileService):
    def __init__(self):
        super().__init__()
        self.s3_client = self.session.client(service_name="s3", region_name="us-east-1")

    @property
    def gdrive_battlecards(self):
        return "gdrive-battlecards"

    def save_bytes_to_s3(self, bytes_to_store: BytesIO, s3_path: str, bucket_name: str):
        bytes_to_store.seek(0)
        self.s3_client.upload_fileobj(bytes_to_store, bucket_name, s3_path)

    def list_files(self, bucket_name: str):
        """
        Create a generator that retrieves all files in the bucket.

        :param bucket_name:
        :return:
        """
        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")

            for page in paginator.paginate(Bucket=bucket_name):
                if "Contents" in page:
                    for obj in page["Contents"]:
                        yield obj["Key"]
        except Exception:
            logging.error(f"Unable to list files in {bucket_name}")
            raise

    def get_file_content(self, bucket_name: str, s3_path: str) -> bytes:
        try:
            response = self.s3_client.get_object(Bucket=bucket_name, Key=s3_path)
            return response["Body"].read()
        except Exception as e:
            logging.error(f"Unable to get file content for {s3_path}: {e}")
            raise

    def does_file_exist(self, bucket: str, file_path: str) -> bool:
        try:
            _ = self.s3_client.head_object(Bucket=bucket, Key=file_path)
            return True
        except ClientError as err:
            if err.response["Error"]["Code"] == "404":
                return False

        return False

    def upload(
        self, bucket: str, file_path: str, record: bytes, metadata: dict
    ) -> None:
        self.s3_client.put_object(
            Bucket=bucket,
            Key=file_path,
            Body=record,
            Metadata=metadata,
        )
