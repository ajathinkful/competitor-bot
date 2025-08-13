# openai_service.py

from app.services.openai.assistant import OpenAIAssistant
from app.services.openai.file import OpenAIFile
from app.services.openai.vector_store import OpenAIVectorStore
from typing import List, Optional, Dict
import requests
import logging
import io
import fitz

import os

from openai import OpenAI

from app.services.slack import slack_service
from app.services.get_secret import get_secret


class OpenAIService:
    def __init__(self, assistant_name: str):
        self.ai_config = self.get_ai_assistant_config(assistant_name)
        api_key = self.ai_config.get("api_key")
        self.openai_client = OpenAI(api_key=api_key)

        self.ai_vector_store = OpenAIVectorStore(self.openai_client)
        self.ai_file = OpenAIFile(self.openai_client)
        self.ai_assistant = OpenAIAssistant(self.openai_client)

    def get_ai_assistant_config(self, model_name: str):
        if model_name == "competitor":
            return {
                "assistant_id": get_secret('ASSISTANT_ID'),
                "vector_store_id": get_secret('VECTOR_STORE_ID'),
                "api_key": get_secret('OPENAI_API_KEY'),
                "name": "competitor",
                "system_instructions": """
                    You are a business analyst. Use internal files and public data to generate insights on competitors and compare them to Jupiter Computing Solutions pgh.
                """,
                "s3_bucket_vector_store_files": "competitor-bot-bucket",
                "s3_folder_prefix": ["competitor-bot/"],
            }
        raise ValueError(f"Unknown assistant model: {model_name}")
    
    def get_open_ai_attachments(
        self,
        openai_client: OpenAI,
        assistant_id: str,
        file_urls: Optional[List[str]] = None,
    ) -> List[Dict]:
        attachments: list[dict[str, list[dict[str, str]] | str]] = []
        if file_urls:
            assistant = openai_client.beta.assistants.retrieve(assistant_id)

            if "file_search" not in [a.type for a in assistant.tools]:
                tools = assistant.tools
                tools.append({"type": "file_search"})  # type: ignore
                self.openai_client.beta.assistants.update(assistant_id, tools=tools)  # type: ignore

            attachments = []
            for file_url in file_urls or []:
                resp = requests.get(
                    file_url,
                    headers={
                        "Authorization": f"Bearer {slack_service.slack_bot_token}"
                    },
                )
                message_file = self.ai_file.create_file(
                    name=os.path.split(resp.url)[-1],
                    obj_bytes=resp.content,
                )
                attachments.append(
                    {"file_id": message_file.id, "tools": [{"type": "file_search"}]}
                )

        return attachments

    @staticmethod
    def get_response_from_openai(context: str, user_content: str):
        try:
            prep = f"""
            {context}
            ====
            {user_content}
            """
            openai_key = get_secret('OPENAI_API_KEY')
            response = OpenAI(api_key=openai_key).chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": prep}],
                temperature=0.7,
                max_tokens=2000,
                top_p=0.8,
                frequency_penalty=0.0,
                presence_penalty=0.0,
            )

            logging.debug(response.choices[0].message.content)
            return response.choices[0].message.content

        except Exception as e:
            logging.warning(e)

    def ask_ai_assistant_pdf_question(self, question: str, raw_file_urls: List[str]):
        """Process the PDF(s) and ask a question about their contents.

        Args:
            question (str): The question to ask about the PDFs
            raw_file_urls (List[str]): List of URLs to PDF files

        Returns:
            str: Combined response from the AI assistant
        """
        combined_text = ""

        for raw_file_url in raw_file_urls:
            logging.info(f"Processing file: {raw_file_url}")

            try:
                # Download file from Slack
                file_info_response = requests.get(
                    raw_file_url,
                    headers={
                        "Authorization": f"Bearer {slack_service.slack_bot_token}"
                    },
                    allow_redirects=True,
                )
            except Exception as e:
                error_msg = f"Error downloading file {raw_file_url}: {str(e)}"
                logging.error(error_msg)
                return error_msg

            try:
                # Extract text from PDF
                pdf_stream = io.BytesIO(file_info_response.content)
                pdf_document = fitz.open(stream=pdf_stream, filetype="pdf")

                # Extract text from all pages
                for page_num in range(len(pdf_document)):
                    page = pdf_document[page_num]
                    combined_text += f"\n--- Page {page_num + 1} ---\n{page.get_text()}"

                pdf_document.close()

            except Exception as e:
                error_msg = f"Error processing PDF {raw_file_url}: {str(e)}"
                logging.error(error_msg)
                return error_msg

        # Create a single message with all content - Assistants API will handle context window management
        message = {
            "role": "user",
            "content": f"{question}\n\nDocument content:\n{combined_text}",
        }

        ## TODO(jarrilla): Ideally, we would have some retry logic here, but according to docs, assistant API auto-manages context window
        ## Would still like to stress-test this before finalizing this decision.
        return self.run_ai_assistant_thread(message)

    # this comes from Skynet, as does setup in code (or you can do in the OpenAI ui)
    # PR: https://github.com/optoinvest/skynet/pull/16

    def ask_ai_assistant_question(
        self,
        question: str,
        file_urls: Optional[List[str]] = None,
    ):
        if len(question) >= 256000:
            logging.warning("Question is too long. Truncating question...")
            question = question[:255999]

        message = {"role": "user", "content": question}
        if file_urls:
            attachments = self.get_open_ai_attachments(
                self.openai_client, self.ai_config["assistant_id"], file_urls
            )
            message["attachments"] = attachments  # type: ignore

        return self.run_ai_assistant_thread(message)

    # Helper method to run an assistant thread and return the response
    def run_ai_assistant_thread(self, message: Dict):
        thread = self.openai_client.beta.threads.create(messages=[message])  # type: ignore
        run = self.openai_client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=self.ai_config["assistant_id"],
        )

        logging.debug(f"Thread run status: {run.status}")
        
        if run.status == "completed":
            messages = list(
                self.openai_client.beta.threads.messages.list(
                    thread_id=thread.id, run_id=run.id
                )
            )
            message_content = messages[0].content[0].text  # type: ignore
            annotations = message_content.annotations
            citations = []
            for index, annotation in enumerate(annotations):
                message_content.value = message_content.value.replace(
                    annotation.text, f"[{index}]"
                )
                if file_citation := getattr(annotation, "file_citation", None):
                    cited_file = self.openai_client.files.retrieve(
                        file_citation.file_id
                    )
                    citations.append(f"[{index}] {cited_file.filename}")

            answer = message_content.value + "\n".join(citations)

            question = message.get("content", "No content")
            logging.info(f"Q: {question}\nA: {answer}")

            return answer

        else:
            # Log detailed info on failure
            logging.error(f"Assistant thread run failed with status: {run.status}")
            # Optionally you can also log thread and run IDs for easier tracing
            logging.error(f"Thread ID: {thread.id}, Run ID: {run.id}")
            return f"Error: Assistant run status {run.status}"


    # @staticmethod
    # def log_qa(ai_assistant: str, question: str, answer: str):
    #     history_log_prefix = ElasticService.ai_assistant_history_log_prefix
    #     logging.info(
    #         "%s: %s",
    #         history_log_prefix,
    #         json.dumps(
    #             {"ai_assistant": ai_assistant, "question": question, "answer": answer}
    #         ),
    #     )
