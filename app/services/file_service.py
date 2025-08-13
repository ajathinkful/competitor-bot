from abc import ABC, abstractmethod


class FileService(ABC):
    @abstractmethod
    def does_file_exist(self, location: str, file_path: str):
        pass

    @abstractmethod
    def upload(self, bucket: str, file_path: str, record: bytes, metadata: dict):
        pass
