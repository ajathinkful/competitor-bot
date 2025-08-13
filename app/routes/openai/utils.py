import json
import logging
import os
import typing
from typing import Dict

from openai.types import FileObject
from pydantic import BaseModel

from app.services.aws import aws_file_service
from app.services.openai.openai_service import OpenAIService
from app.services.openai.vector_store import OpenAiFileStatus
# from app.services.snowflake import SecurityMasterSnowflakeService


def create_response(
    vector_store_file_statuses: typing.List[OpenAiFileStatus],
) -> Dict:
    """
    Create a response dict that summarizes the vector store file upload statues

    :param vector_store_file_statuses:
    :return: a dict with 'total' and 'errored_files"
    """
    status = {
        "total": len(vector_store_file_statuses),
        "errored_files": [],
    }
    for completed in vector_store_file_statuses:
        if completed.transfer_status:
            if completed.transfer_status not in status:
                status[completed.transfer_status] = 1
            else:
                status[completed.transfer_status] += 1  # type: ignore

        if completed.transfer_status == "failed":
            logging.error("%s failed to transfer to vector store", completed.file_name)
            status["errored_files"].append(completed.file_name)  # type: ignore

    return status


def get_aws_data(bucket: str, folders: typing.List[str]) -> Dict[str, bytes]:
    """
    Get aws data from a bucket and the provided folders as a dict where the
    key is the file path and the value is a bytes object.


    :param bucket:
    :param folders:
    :return:
    """
    list_gen = aws_file_service.list_files(bucket)
    filepath_to_bytes: Dict[str, bytes] = {}
    while True:
        try:
            aws_file_path = next(list_gen)
            if any([aws_file_path.startswith(folder) for folder in folders]):
                _, ext = os.path.splitext(aws_file_path)
                content = aws_file_service.get_file_content(bucket, aws_file_path)

                if ext in [
                    ".html",
                    ".doc",
                    ".docx",
                    ".gdoc",
                    "",
                    ".pdf",
                    ".pptx",
                    ".ppt",
                    ".xlsx",
                ]:
                    if ext in [".gdoc"]:
                        aws_file_path = aws_file_path.replace(ext, ".docx")
                    elif ext == "":
                        aws_file_path += ".docx"

                    filepath_to_bytes[aws_file_path] = content

        except StopIteration:
            break

    return filepath_to_bytes


def get_response_block(
    status: Dict, assistant_name: str, sources: typing.List[str]
) -> typing.List:
    """
    Create a response block for sending a message in slack.


    :param status:
    :param assistant_name:
    :param sources:
    :return:
    """
    return [
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_section",
                    "elements": [
                        {
                            "type": "text",
                            "text": f"{assistant_name} assistant's vector store has been refreshed with files from: ",
                        },
                    ],
                },
                {
                    "type": "rich_text_preformatted",
                    "elements": [
                        {
                            "type": "text",
                            "text": ",\n".join(sources),
                        },
                    ],
                },
                {
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": "Status: "}],
                },
                {
                    "type": "rich_text_preformatted",
                    "elements": [{"type": "text", "text": json.dumps(status)}],
                },
            ],
        }
    ]


# class SMSSPVData(BaseModel):
#     assistant_name: str
#     files_to_info: Dict[str, bytes | FileObject]
#     skipped_spv_count: int
#     skipped_sms_count: int


# def get_sms_fund_data(fund_name: str) -> Dict[str, bytes]:
#     records = []
#     with SecurityMasterSnowflakeService() as d:
#         prefix = "sms_"
#         df = d.select_sms(fund_name=fund_name)
#         df["vs_filename"] = prefix + df["id"] + ".json"
#         records.extend(json.loads(df.to_json(orient="records")))

#     return {r["vs_filename"]: json.dumps(r).encode("utf-8") for r in records}


# def get_sms_and_spv_data() -> Dict[str, bytes]:
#     """
#     Get all sms and spv data as a dict where the key is the filename
#     and the value is a bytes object of the row in json format.

#     The filename takes the 'id' column and prefixes either 'spv_' or
#     'sms_'. The suffix '.json.' is also added.

#     :return:
#     """
#     records = []
#     with SecurityMasterSnowflakeService() as d:
#         prefix = "sms_"
#         df = d.select_sms()
#         df["vs_filename"] = prefix + df["id"] + ".json"
#         records.extend(json.loads(df.to_json(orient="records")))

#         prefix = "spv_"
#         df = d.select_spv()
#         df["vs_filename"] = prefix + df["entity_id"] + ".json"
#         records.extend(json.loads(df.to_json(orient="records")))

#     return {r["vs_filename"]: json.dumps(r).encode("utf-8") for r in records}


def upload_ai_files(
    filenames_to_bytes: Dict[str, bytes], assistant_name: str
) -> Dict[str, FileObject]:
    """
    Upload files to openai. This removes all pre-existing files that match
     filenames in `filenames_to_bytes` first and then uploads

    :param filenames_to_bytes:
    :param assistant_name:
    :return: A dict of fileobjects where the key is the filename

    """
    openai_service = OpenAIService(assistant_name)
    filename_to_obj: Dict[str, FileObject] = {}
    existing_ai_files = {a.filename: a for a in openai_service.ai_file.list()}
    for filename, file_bytes in filenames_to_bytes.items():
        # openai removes the base path, but we keep it here by replacing
        # with a "__"
        filename = filename.replace(os.path.sep, "__")
        if filename in existing_ai_files:
            openai_service.ai_file.delete(
                existing_ai_files[filename].id,
            )
        file_obj = openai_service.ai_file.create_file(filename, file_bytes)
        filename_to_obj[filename] = file_obj
    return filename_to_obj


def upload_missing_ai_files(
    filenames_to_bytes: Dict[str, bytes], assistant_name: str
) -> Dict[str, FileObject]:
    """
    Upload files to openai. Only files that do not exist will be uploaded.

    :param filenames_to_bytes:
    :param assistant_name:
    :return: A dict of fileobjects where the key is the filename

    """
    openai_service = OpenAIService(assistant_name)
    filename_to_obj: Dict[str, FileObject] = {}
    existing_ai_files = {a.filename: a for a in openai_service.ai_file.list()}
    for filename, file_bytes in filenames_to_bytes.items():
        # openai removes the base path, but we keep it here by replacing
        # with a "__"
        filename = filename.replace(os.path.sep, "__")
        if filename not in existing_ai_files:
            file_obj = openai_service.ai_file.create_file(filename, file_bytes)
            filename_to_obj[filename] = file_obj
        else:
            filename_to_obj[filename] = existing_ai_files[filename]

    return filename_to_obj


def determine_files_to_upload_to_vs(
    filenames_to_objects: Dict[str, FileObject],
    assistant_name: str,
    purge_incomplete=True,
) -> Dict[str, FileObject]:
    """
    Determine which files need to be uploaded to the vector store

    If any "in_progress" or "failed" files are detected, they are removed
    from the vector store automatically

    :param filenames_to_objects:
    :param assistant_name:
    :param purge_incomplete:
    :return:
    """
    openai_service = OpenAIService(assistant_name)
    vector_store_id = openai_service.ai_config["vector_store_id"]
    existing_vs_id_to_files = {
        f.id: f for f in openai_service.ai_vector_store.list_files(vector_store_id)
    }
    already_in_vs = []
    for filename, file_obj in filenames_to_objects.items():
        if file_obj.id in existing_vs_id_to_files:
            if (
                purge_incomplete
                and existing_vs_id_to_files[file_obj.id].status != "completed"
            ):
                openai_service.ai_vector_store.delete_file(file_obj.id, assistant_name)
                continue

            already_in_vs.append(filename)

    for filename in already_in_vs:
        filenames_to_objects.pop(filename)

    return filenames_to_objects
