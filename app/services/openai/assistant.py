import logging
from typing import List
from openai.types.beta import Assistant
from .mixin import OpenAIMixin
from openai import OpenAI


class OpenAIAssistant:
    def __init__(self, client: OpenAI):
        self.openai_client = client

    def get(self, assistant_id: str) -> Assistant:
        try:
            return self.openai_client.beta.assistants.retrieve(
                assistant_id=assistant_id,
            )
        except Exception:
            logging.error("Error while getting assistant, %s", assistant_id)
            raise

    @OpenAIMixin.paginate_decorator
    def list(self, **kwargs) -> List[Assistant]:
        try:
            return self.openai_client.beta.assistants.list(**kwargs)  # type: ignore
        except Exception as e:
            logging.error("Error while listing assistants: %s", e)
            raise

    def update(
        self,
        assistant_id: str,
        vector_store_ids: List[str],
    ) -> Assistant:
        try:
            return self.openai_client.beta.assistants.update(
                assistant_id=assistant_id,
                tools=[{"type": "file_search"}],
                tool_resources={"file_search": {"vector_store_ids": vector_store_ids}},
            )
        except Exception:
            logging.error("Error while modifying assistant, %s", assistant_id)
            raise
