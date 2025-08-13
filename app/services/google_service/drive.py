import logging
import os

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.services.file_service import FileService
from app.services.google_service.google_service import GoogleService


class GoogleDriveService(GoogleService):
    def __init__(self):
        super().__init__()
        self.drive_service = build("drive", "v3", credentials=self.creds)

    def list_drives(self):
        next_page = True
        req_data = {"pageSize": 10}
        while next_page:
            resp = self.drive_service.drives().list(**req_data).execute()
            next_page = resp.get("nextPageToken", None)
            req_data["pageToken"] = next_page
            for drive in resp.get("drives", []):
                yield drive

    def list_files(self, drive_id: str, query: str, next_page_token: str):
        return (
            self.drive_service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, parents, shortcutDetails, md5Checksum, modifiedTime, sha1Checksum, sha256Checksum)",
                pageToken=next_page_token,
                spaces="drive",
                corpora="allDrives",
                driveId=drive_id,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
        )

    # Recursive generator with pagination to get all files with full paths
    def get_all_files_with_paths(self, folder_id="root", drive_id=None, parent_path=""):
        query = f"'{folder_id}' in parents"
        next_page_token = None
        while True:
            results = self.list_files(drive_id, query, next_page_token)
            items = results.get("files", [])

            for item in items:
                current_path = f"{parent_path}/{item['name']}"

                if item["mimeType"] == "application/vnd.google-apps.folder":
                    yield from self.get_all_files_with_paths(
                        folder_id=item["id"],
                        drive_id=drive_id,
                        parent_path=current_path,
                    )
                elif item["mimeType"] == "application/vnd.google-apps.shortcut":
                    target_id = item["shortcutDetails"]["targetId"]
                    target_mime_type = item["shortcutDetails"]["targetMimeType"]

                    if target_mime_type == "application/vnd.google-apps.folder":
                        yield from self.get_all_files_with_paths(
                            folder_id=target_id,
                            drive_id=drive_id,
                            parent_path=current_path,
                        )
                    else:
                        item.update({"directory": parent_path})
                        yield item
                else:
                    item.update({"directory": parent_path})
                    yield item

            next_page_token = results.get("nextPageToken")
            if not next_page_token:
                break

    @staticmethod
    def get_common_ext_from_mime_type(mime_type):
        mime_extension_map = {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/vnd.google-apps.document": ".gdoc",
            "application/vnd.google-apps.spreadsheet": ".gsheet",
            "application/vnd.google-apps.presentation": ".gslides",
            "application/vnd.google-apps.drawing": ".gdraw",
            "application/vnd.google-apps.form": ".gform",
            "application/vnd.google-apps.map": ".gmap",
            "application/vnd.google-apps.script": ".gs",
            "application/vnd.google-apps.site": ".gsite",
            "application/vnd.google-apps.folder": "",
            "application/pdf": ".pdf",
            "text/html": ".html",
            "application/octet-stream": "",
        }

        if mime_type not in mime_extension_map:
            logging.warning(
                "Google %s does not yet have a mapped extension.", mime_type
            )

        return mime_extension_map.get(mime_type, "")

    def copy_drive_to_service(
        self, drive_name: str, bucket_name: str, prefix: str, service: FileService
    ) -> int:
        """
        Transfer files from a drive to a file service

        :param drive_name:
        :param bucket_name:
        :param prefix:
        :param service:
        :return: The number of transferred files
        """
        transferred_file_ct = 0
        try:
            for drive in self.list_drives():
                if drive["name"] != drive_name:
                    continue

                logging.info(f"Processing drive: {drive['name']}")

                for file in self.get_all_files_with_paths(
                    drive_id=drive["id"], folder_id=drive["id"]
                ):
                    # Some people are putting directory separators in the file
                    # name. This causes the data to be placed in unnecessary folders
                    # later
                    item_name = file["name"].replace("/", "-")

                    # If this is a shortcut to a file, we need the original
                    # id to export
                    target_id = file.get("shortcutDetails", {}).get(
                        "targetId", file["id"]
                    )
                    target_mime_type = file.get("shortcutDetails", {}).get(
                        "targetMimeType", file["mimeType"]
                    )

                    ext = self.get_common_ext_from_mime_type(target_mime_type)
                    _key = os.path.join(
                        prefix, file["directory"].removeprefix("/"), item_name
                    ).strip()
                    _key = _key.removesuffix(ext) + ext
                    logging.debug(f"Processing file: {_key}")

                    if service.does_file_exist(bucket_name, _key):
                        logging.debug(
                            "WARNING: Doc already exists and I just avoid conflicts on principle"
                        )
                        continue

                    logging.info("%s not on remote, will create", _key)

                    # google docs 'files' need to be exported, and don't have a native checksum
                    if "md5Checksum" in file:
                        record = (
                            self.drive_service.files()
                            .get_media(fileId=target_id)
                            .execute()
                        )
                    else:
                        try:
                            record = (
                                self.drive_service.files()
                                .export(fileId=target_id, mimeType="text/plain")
                                .execute()
                            )
                        except HttpError as error:
                            # this can happen if google's cache is not synchronized.
                            # we can't control that, so we simply skip. This is very
                            # annoying
                            logging.warning(f"warning: {error}")
                            continue

                    service.upload(
                        bucket=bucket_name,
                        file_path=_key,
                        record=record,
                        metadata={"modifiedTime": file["modifiedTime"]},
                    )
                    transferred_file_ct += 1

        except HttpError as error:
            logging.error(f"An error occurred: {error}")

        return transferred_file_ct

    def copy_my_drive_folder_to_service(
        self,
        folder_id: str,
        bucket_name: str,
        prefix: str,
        service: FileService,
        dry_run: bool = False 
    ) -> int:
        """
        Copies a specific folder from My Drive (not Shared Drive) to a remote service.
        """
        transferred_file_ct = 0
        try:
            for file in self.get_all_files_with_paths(folder_id=folder_id, drive_id=None):
                item_name = file["name"].replace("/", "-")
                target_id = file.get("shortcutDetails", {}).get("targetId", file["id"])
                target_mime_type = file.get("shortcutDetails", {}).get("targetMimeType", file["mimeType"])
                ext = self.get_common_ext_from_mime_type(target_mime_type)

                _key = os.path.join(prefix, file["directory"].removeprefix("/"), item_name).strip()
                _key = _key.removesuffix(ext) + ext

                if service.does_file_exist(bucket_name, _key):
                    continue

                if "md5Checksum" in file:
                    record = self.drive_service.files().get_media(fileId=target_id).execute()
                else:
                    try:
                        record = self.drive_service.files().export(fileId=target_id, mimeType="text/plain").execute()
                    except HttpError as error:
                        logging.warning(f"Export error: {error}")
                        continue

                if dry_run:
                    print(f"[DRY RUN] Would upload file: {_key} (size: {len(record)} bytes)")
                else:
                    service.upload(
                        bucket=bucket_name,
                        file_path=_key,
                        record=record,
                        metadata={"modifiedTime": file["modifiedTime"]},
                    )
                transferred_file_ct += 1

        except HttpError as error:
            logging.error(f"Drive error: {error}")

        return transferred_file_ct

    
