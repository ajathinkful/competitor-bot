import logging
import typing

from fastapi import APIRouter, Depends
from app.services.get_secret import get_secret
import openai

# from app.admin import scheduler
from app.models.requests.openai import validate_assistant_name
from app.services.openai.openai_service import OpenAIService
# from app.services.slack import slack_service
# from app.slack.channels import SlackChannels
from app.routes.openai.utils import (
    get_response_block,
    create_response,
    # get_sms_and_spv_data,
    upload_missing_ai_files,
    determine_files_to_upload_to_vs,
    get_aws_data,
    upload_ai_files,
)

router = APIRouter(prefix="/openai")

# @scheduler.scheduled_job(
#     "cron",
#     day_of_week="mon-sun",
#     hour="5",
#     timezone="America/New_York",
#     args=["competitor"],
# )
@router.post("/assistants/{assistant_name}/add_ai_data_to_ingest_to_vector_store")
def add_ai_data_to_ingest_to_vector_store(
    assistant_name: str = Depends(validate_assistant_name),
    purge_all_vs_files: bool = False,
    replace_existing_ai_file: bool = False,
):
    """
    Adds gdrive ai data to ingest to vector store for a given assistant
    :param assistant_name:
    :param purge_all_vs_files:
    :param replace_existing_ai_file:
    :return:
    """
    try:
        logging.info(f"Starting vector store refresh for assistant: {assistant_name}")

        openai_service = OpenAIService(assistant_name)
        ai_config = openai_service.get_ai_assistant_config(assistant_name)
        logging.debug(f"AI Config: {ai_config}")

        pre_s3_file_upload_to_vs = ai_config.get("pre_s3_file_upload_to_vs")

        if purge_all_vs_files:
            logging.info(f"Purging all vector store files for {assistant_name}")
            openai_service.ai_vector_store.delete_all_files(assistant_name)

        bucket = ai_config.get("s3_bucket_vector_store_files")
        folders: typing.List[str] = ai_config.get("s3_folder_prefix", [])
        name = ai_config.get("name")

        logging.info(f"Bucket: {bucket}")
        logging.info(f"Folders: {folders}")
        logging.info(f"Assistant name from config: {name}")

        if bucket and folders and name:
            filenames_to_bytes = get_aws_data(bucket, folders)
            logging.info(f"Fetched {len(filenames_to_bytes)} files from S3 bucket '{bucket}' and folders '{folders}'")

            if pre_s3_file_upload_to_vs:
                filenames_to_bytes = pre_s3_file_upload_to_vs(filenames_to_bytes)
                logging.info("Applied pre-upload processing to files")

            if replace_existing_ai_file:
                logging.info("Replacing existing AI files")
                filenames_to_objects = upload_ai_files(
                    filenames_to_bytes, assistant_name
                )
            else:
                logging.info("Uploading missing AI files only")
                filenames_to_objects = upload_missing_ai_files(
                    filenames_to_bytes, assistant_name
                )

            filenames_to_objects_for_upload = determine_files_to_upload_to_vs(
                filenames_to_objects, assistant_name
            )
            logging.info(f"Number of files to upload to vector store: {len(filenames_to_objects_for_upload)}")

            if filenames_to_objects_for_upload:
                statuses = openai_service.ai_vector_store.create_files(
                    filenames_to_objects_for_upload,
                    openai_service.ai_config["vector_store_id"],
                )
                resp = create_response(statuses)
                resp.update(
                    {
                        "already_exist": len(filenames_to_bytes)
                        - len(filenames_to_objects_for_upload)
                    }
                )
                logging.info(f"Vector store refresh response: {resp}")

                # Uncomment and adapt Slack notifications if needed
                # slack_service.send_message(
                #     SlackChannels.TOTAL_RECALL_ALERTS_CHANNEL_ID,
                #     message=f"{assistant_name} vector store refreshed:",
                #     blocks=get_response_block(
                #         resp,
                #         assistant_name,
                #         sources=[f"s3://{bucket}/{folder}" for folder in folders],
                #     ),
                # )
            else:
                logging.info("No new files to add to vector store")
                # slack_service.send_message(
                #     SlackChannels.TOTAL_RECALL_ALERTS_CHANNEL_ID,
                #     message=f"No new files to add to {assistant_name} vector store",
                # )

            return {
                "message": "Transfer status details sent to vector store",
                "details": resp if 'resp' in locals() else "No files uploaded"
            }

        else:
            msg = f"No AWS bucket or folder tied to {assistant_name}"
            logging.warning(msg)
            return {"message": msg}

    except Exception as e:
        logging.exception("Exception during vector store refresh")
        return {
            "status": f"Unexpected error while refreshing vector store for {assistant_name}",
            "error": str(e),
            "type": type(e).__name__,
        }

@router.delete("/assistants/{assistant_name}/clear_vector_store")
def clear_vector_store(
    assistant_name: str = Depends(validate_assistant_name),
):
    """
    Deletes all files in the shared vector store (used across assistants),
    and reports how many files were deleted.
    """
    try:
        logging.info(f"Clearing shared vector store for assistant: {assistant_name}")

        openai_service = OpenAIService(assistant_name)

        # Get the shared vector store ID
        vector_store_id = get_secret("VECTOR_STORE_ID")
        if not vector_store_id or not vector_store_id.startswith("vs_"):
            raise ValueError("Invalid or missing VECTOR_STORE_ID in .env")

        # Get current files in the vector store
        files = list(openai_service.ai_vector_store.list_files(vector_store_id))
        file_count = len(files)
        logging.info(f"Found {file_count} files in vector store '{vector_store_id}'")

        # Delete them
        openai_service.ai_vector_store.delete_all_files(vector_store_id)

        logging.info(f"Successfully cleared {file_count} files from vector store '{vector_store_id}' for assistant: {assistant_name}")
        return {
            "message": f"Deleted {file_count} files from shared vector store '{vector_store_id}' (assistant: {assistant_name})"
        }

    except Exception as e:
        logging.exception(f"Error clearing vector store for {assistant_name}")
        return {
            "status": "error",
            "message": f"Failed to clear vector store for '{assistant_name}'",
            "error": str(e),
            "type": type(e).__name__,
        }
    
@router.delete("/assistants/{assistant_name}/clear_all_openai_files")
def clear_all_openai_files(
    assistant_name: str = Depends(validate_assistant_name),
):
    try:
        logging.info(f"Clearing ALL OpenAI Files for assistant: {assistant_name}")

        # Get your API key
        api_key = get_secret("OPENAI_API_KEY")
        client = openai.Client(api_key=api_key)

        # List and delete
        files_response = client.files.list()
        files = list(files_response.data)
        file_count = len(files)

        deleted_ids = []
        for f in files:
            try:
                client.files.delete(f.id)
                deleted_ids.append(f.id)
                logging.info(f"Deleted OpenAI file: {f.id}")
            except Exception as e:
                logging.warning(f"Failed to delete file {f.id}: {e}")

        logging.info(f"Deleted {len(deleted_ids)} OpenAI Files for assistant: {assistant_name}")
        return {
            "message": f"Deleted {len(deleted_ids)} OpenAI Files for assistant: {assistant_name}",
            "deleted_file_ids": deleted_ids
        }

    except Exception as e:
        logging.exception(f"Error clearing OpenAI Files for {assistant_name}")
        return {
            "status": "error",
            "message": f"Failed to clear OpenAI Files for '{assistant_name}'",
            "error": str(e),
            "type": type(e).__name__,
        }


