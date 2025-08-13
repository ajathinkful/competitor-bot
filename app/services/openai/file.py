import io
import logging
from typing import List

from app.services.openai.mixin import OpenAIMixin
from openai import OpenAI
from openai.types import FileObject, FileDeleted


class OpenAIFile:
    def __init__(self, client: OpenAI):
        self.openai_client = client

    def create_file(self, name: str, obj_bytes: bytes) -> FileObject:
        bytes_file = io.BytesIO(obj_bytes)
        bytes_file.name = name

        message_file = self.openai_client.files.create(
            file=bytes_file,
            purpose="assistants",
        )

        return message_file

    def get(self, file_id: str) -> FileObject:
        return self.openai_client.files.retrieve(file_id=file_id)

    @OpenAIMixin.paginate_decorator
    def list(self, **kwargs) -> List[FileObject]:  # type: ignore
        try:
            return self.openai_client.files.list(**kwargs)  # type: ignore
        except Exception as e:
            logging.error(e)
            logging.error("Error while listing files %s", e)

    def delete(self, file_id: str) -> FileDeleted | None:
        try:
            return self.openai_client.files.delete(file_id)
        except Exception as e:
            logging.warning(str(e))
            return None
