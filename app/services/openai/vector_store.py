import logging
import time
from typing import List, Literal, Optional, Dict

from openai.types import FileObject
from openai.types import VectorStore

from .file import OpenAIFile
from .mixin import OpenAIMixin
from app.utils import chunker
from openai import OpenAI, NOT_GIVEN, NotGiven, BaseModel
from openai.types.vector_stores import (
    VectorStoreFile,
    VectorStoreFileDeleted,
)


class OpenAiFileStatus(BaseModel):
    file_name: str
    file_id: str
    transfer_status: Optional[str] = None


class OpenAIVectorStore:
    def __init__(self, client: OpenAI):
        self.openai_client = client
        self.ai_file = OpenAIFile(client)

    @OpenAIMixin.paginate_decorator
    def list(self, **kwargs) -> List[VectorStore]:
        try:
            return self.openai_client.vector_stores.list(**kwargs)  # type: ignore
        except Exception as e:
            logging.error("Failed to list vector stores %s", e)
            raise

    def create(self, name: str) -> VectorStore:
        try:
            vs = self.openai_client.vector_stores.create(name=name)
            return vs
        except Exception:
            logging.error("Failed to create vector store %s", name)
            raise

    def get_by_name(self, name: str) -> List[VectorStore]:
        try:
            return [v for v in self.list() if v.name == name]

        except Exception:
            logging.error("Failed to get vector store by name, %s", name)
            raise

    def delete_file(
        self, file_id: str, vector_store_id
    ) -> VectorStoreFileDeleted | None:
        try:
            deleted_vector_store_file = self.openai_client.vector_stores.files.delete(
                vector_store_id=vector_store_id,
                file_id=file_id,
            )
            return deleted_vector_store_file
        except Exception as e:
            logging.warning(str(e))
            return None

    def delete_all_files(self, vector_store_id: str):
        for f in self.list_files(vector_store_id):
            self.delete_file(f.id, vector_store_id)

    @OpenAIMixin.paginate_decorator
    def list_files(
        self,
        vector_store_id: str,
        status_filter: Literal["in_progress", "completed", "failed", "cancelled"]
        | NotGiven = NOT_GIVEN,
        limit: int = 100,
        order: Literal["asc", "desc"] | NotGiven = NOT_GIVEN,
        **kwargs,
    ) -> List[VectorStoreFile]:
        try:
            return self.openai_client.vector_stores.files.list(
                # type: ignore
                vector_store_id=vector_store_id,
                limit=limit,
                order=order,
                filter=status_filter,
                **kwargs,
            )

        except Exception:
            logging.error("Failed to list vector store files for, %s", vector_store_id)
            raise

    def get_file(self, file_id: str, vector_store_id: str) -> VectorStoreFile:
        try:
            vector_store_file = self.openai_client.vector_stores.files.retrieve(
                vector_store_id=vector_store_id, file_id=file_id
            )
            return vector_store_file

        except Exception:
            logging.error(
                "Failed to get vector store file for %s %s", file_id, vector_store_id
            )
            raise

    def create_files_from_ai_files(
        self,
        vector_store_id: str,
        ai_files: List[FileObject],
        _attempt: int = 0,
        _max_attempts: int = 5,
        _cumulative_statuses: Optional[Dict[str, OpenAiFileStatus]] = None,
    ) -> List[OpenAiFileStatus]:
        id_to_ai_files = {f.id: f for f in ai_files}

        chunk_size = 50
        for files_chunk in chunker([f.id for f in id_to_ai_files.values()], chunk_size):
            _vector_store_file_batch = (
                self.openai_client.vector_stores.file_batches.create(
                    vector_store_id=vector_store_id,
                    file_ids=files_chunk,
                )
            )
            time.sleep(2)

        max_secs = 100
        start = time.time()
        elapsed_secs = 0.0
        while elapsed_secs <= max_secs:
            in_progress = [
                vs
                for vs in self.list_files(vector_store_id, status_filter="in_progress")
                if vs.id in id_to_ai_files
            ]

            if len(in_progress) == 0:
                break

            elapsed_secs = time.time() - start
            time.sleep(5)

        id_to_ai_file_status = _cumulative_statuses or {
            vs.id: OpenAiFileStatus(
                transfer_status="completed",
                file_name=id_to_ai_files[vs.id].filename,
                file_id=vs.id,
            )
            for vs in id_to_ai_files.values()
        }
        in_progress = [
            vs for vs in self.list_files(vector_store_id, status_filter="in_progress")
        ]
        failed = [vs for vs in self.list_files(vector_store_id, status_filter="failed")]
        for vs in in_progress + failed:
            if vs.id in id_to_ai_files:
                self.delete_file(vs.id, vector_store_id)
                id_to_ai_file_status[vs.id] = OpenAiFileStatus(
                    transfer_status=vs.status,
                    file_name=id_to_ai_files[vs.id].filename,
                    file_id=vs.id,
                )

        incomplete = [
            id_to_ai_files[f.file_id]
            for f in id_to_ai_file_status.values()
            if f.transfer_status != "completed"
        ]
        if incomplete and _attempt <= _max_attempts:
            logging.warning("Retrying %s vector store uploads", len(incomplete))
            return self.create_files_from_ai_files(
                vector_store_id,
                incomplete,
                _attempt=_attempt + 1,
                _max_attempts=_max_attempts,
                _cumulative_statuses=id_to_ai_file_status,
            )

        return list(id_to_ai_file_status.values())

    def create_files(
        self,
        files_to_info: Dict[str, FileObject] | Dict[str, bytes],
        vector_store_id: str,
    ) -> List[OpenAiFileStatus]:
        """
        Create vector store files given a dict of filenames to bytes (or file object)
         per file for a given assistant name

        This first creates the file in openai and then places that file
        in the vector store. If the file object is provided, then it is not recreated.
        It is just used to upload to the vector store

        A list of `OpenAiFileStatus` are returned

        :param files_to_info:
        :param vector_store_id:
        :return:
        """

        ai_files = []
        for file_name, file_bytes_or_name in files_to_info.items():
            if isinstance(file_bytes_or_name, bytes):
                ai_file = self.ai_file.create_file(file_name, file_bytes_or_name)
                ai_files.append(ai_file)
            else:
                ai_files.append(file_bytes_or_name)

        return self.create_files_from_ai_files(vector_store_id, ai_files)
