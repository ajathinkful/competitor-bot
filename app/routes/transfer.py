from fastapi import APIRouter
from pydantic import BaseModel
import logging
from app.services.get_secret import get_secret


from app.services.google_service import google_drive_service
from app.services.aws import aws_file_service

# from scheduler import scheduler or your preffered scheduler setup

router = APIRouter()

logging.basicConfig(
    level=logging.INFO,  
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class TransferJob(BaseModel):
    bucket_name: str
    gdrive_name: str
    s3_folder_prefix: str

    
# @scheduler.scheduled_job(
#     "cron",
#     day="*",
#     hour="5",
#     timezone="America/New_York",
# )
@router.post("/gdrive-battlecards-to-s3")
def run_transfer_job():
    folder_id = get_secret('FOLDER_ID')
    transfer_job = TransferJob(
        bucket_name=get_secret('BUCKET_NAME'),
        gdrive_name="Competitor Battlecards",
        s3_folder_prefix="competitor-bot/battlecards",
    )

    try:
        transferred_file_ct = google_drive_service.copy_my_drive_folder_to_service(
            
            bucket_name=transfer_job.bucket_name,
            prefix=transfer_job.s3_folder_prefix,
            service=aws_file_service,
            folder_id=folder_id,
            dry_run=False
        )

        # msg = f"Transfer of {transferred_file_ct} files from {transfer_job.gdrive_name} to {transfer_job.bucket_name} complete."
        # slack_service.send_message(
        #     SlackChannels.TOTAL_RECALL_ALERTS_CHANNEL_ID,
        #     message=msg,
        # )
        # return msg

        msg = f"✅ Transferred {transferred_file_ct} file(s) from Google Drive folder ID '{folder_id}' to S3 bucket '{transfer_job.bucket_name}' under prefix '{transfer_job.s3_folder_prefix}'."
        print(msg)
        return {"message": msg} 


    except Exception as e:
        msg = f"Unexpected error transferring from {transfer_job.gdrive_name} to {transfer_job.bucket_name}: {e}"
        logging.error(msg)
        return msg



