from google.cloud import storage
import logging

def get_gcp_data(bucket_name: str, prefixes: list[str]) -> dict[str, bytes]:
    """
    Downloads files from GCS bucket and folders (prefixes).
    Returns dict mapping filename to bytes content.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    filenames_to_bytes = {}

    for prefix in prefixes:
        blobs = bucket.list_blobs(prefix=prefix)
        for blob in blobs:
            if not blob.name.endswith("/"):  # skip folders
                content = blob.download_as_bytes()
                filenames_to_bytes[blob.name] = content

    return filenames_to_bytes


def ingest_competitor_ai_data(purge_all_vs_files=False, replace_existing_ai_file=False):
    try:
        assistant_name = "competitor"
        openai_service = OpenAIService(assistant_name)
        ai_config = openai_service.get_ai_assistant_config(assistant_name)
        bucket = ai_config.get("s3_bucket_vector_store_files")  # rename this to GCP bucket if you want
        folders = ai_config.get("s3_folder_prefix", [])
        name = ai_config.get("name")

        if not (bucket and folders and name):
            print(f"No GCP bucket or folder tied to {assistant_name}")
            return

        # Fetch files from GCS
        filenames_to_bytes = get_gcp_data(bucket, folders)

        if purge_all_vs_files:
            openai_service.ai_vector_store.delete_all_files(assistant_name)

        if replace_existing_ai_file:
            filenames_to_objects = upload_ai_files(filenames_to_bytes, assistant_name)
        else:
            filenames_to_objects = upload_missing_ai_files(filenames_to_bytes, assistant_name)

        filenames_to_objects_for_upload = determine_files_to_upload_to_vs(filenames_to_objects, assistant_name)

        if filenames_to_objects_for_upload:
            statuses = openai_service.ai_vector_store.create_files(
                filenames_to_objects_for_upload,
                openai_service.ai_config["vector_store_id"],
            )
            slack_service.send_message(
                SlackChannels.TOTAL_RECALL_ALERTS_CHANNEL_ID,
                message=f"{assistant_name} vector store refreshed with {len(filenames_to_objects_for_upload)} files.",
            )
        else:
            slack_service.send_message(
                SlackChannels.TOTAL_RECALL_ALERTS_CHANNEL_ID,
                message=f"No new files to add to {assistant_name} vector store",
            )

    except Exception as e:
        logging.error(str(e))
        slack_service.send_message(
            SlackChannels.TOTAL_RECALL_ALERTS_CHANNEL_ID,
            f"Unexpected error while refreshing vector store for {assistant_name}: {e}"
        )
