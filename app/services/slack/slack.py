import logging
import os
import re
import typing
from typing import Dict, Optional, List

import requests

# renamed to avoid conflict with the fastapi
from slack_bolt import App as SlackApp
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.web import SlackResponse

from app.utils import chunker


class SlackService:
    def __init__(self):
        self.slash_cmd = "/" + (os.getenv("SLACK_SLASH_CMD") or "make")
        self.slack_app = SlackApp(
            token=self.slack_bot_token, signing_secret=self.slack_signing_secret
        )
        self.slack_user_app = SlackApp(token=self.slack_user_token)
        self.socket_mode_handler = SocketModeHandler(
            self.slack_app, self.slack_app_token
        )

    @property
    def slack_bot_token(self):
        return os.getenv("SLACK_BOT_TOKEN")

    @property
    def slack_user_token(self):
        return os.getenv("SLACK_USER_TOKEN")

    @property
    def slack_signing_secret(self):
        return os.getenv("SLACK_SIGNING_SECRET")

    @property
    def slack_app_token(self):
        return os.getenv("SLACK_APP_TOKEN")

    def run_bolt_app(self):
        self.socket_mode_handler.start()

    @staticmethod
    def markdown_to_slack_blocks(markdown_text: str):
        """

        Args:
            markdown_text:  The markdown content to be sent to Slack.

        Returns: List[Dict]: Slack blocks suitable for use in `chat_postMessage`

        """
        # Slack limit per block: 3000 characters. We'll use a soft limit around 2900.
        SOFT_LIMIT = 2900

        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", markdown_text)

        # Split on double newlines or paragraph breaks
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        blocks = []
        current_block = ""

        for para in paragraphs:
            if len(current_block) + len(para) + 2 < SOFT_LIMIT:
                current_block += para + "\n\n"
            else:
                blocks.append(
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": current_block.strip()},
                    }
                )
                current_block = para + "\n\n"

        # Add the last block if any content remains
        if current_block.strip():
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": current_block.strip()},
                }
            )

        return blocks

    def send_message(
        self,
        user_or_ch_id: str,
        message: Optional[str] = None,
        backup_message: Optional[str] = None,
        **kwargs,
    ):
        """
        Send a message from either the bot or the user token with optional spoofed appearance.

        :param user_or_ch_id: Channel or user ID
        :param message: The text of the message
        :param backup_message: Fallback message text
        :param kwargs: all remaining kwargs are sent to `chat_postMessage`
        """
        blocks = kwargs.pop("blocks", [])

        if not message and not blocks and backup_message:
            message = backup_message

        try:
            if len(blocks) > 50:
                for grp in chunker(blocks, 50):
                    self.send_message(user_or_ch_id, message, blocks=grp)
            else:
                self.slack_app.client.chat_postMessage(
                    channel=user_or_ch_id,
                    text=message,
                    blocks=blocks,
                    **kwargs,
                )
        except SlackApiError as slack_error:
            msg = (
                "Looks like I'm not in this chat.\n"
                "If you don't like ephemeral messages, invite me!\n"
                "In the meantime, here is a message..."
            )
            if kwargs.get("response_url"):
                self.send_ephemeral_message(
                    response_url=kwargs["response_url"],
                    message=f"{msg}\n{message}",
                    blocks=blocks,
                )
            else:
                logging.error("Error sending slack message: %s", slack_error)
        except Exception as e:
            logging.error("Unknown error sending slack message: %s", e)
            raise e

    @staticmethod
    def send_ephemeral_message(
        response_url: str, message: Optional[str] = None, blocks: Optional[List] = None
    ) -> requests.Response | None:
        try:
            resp = requests.post(
                response_url,
                json={"text": message, "blocks": blocks},
            )
            return resp
        except Exception as e:
            logging.error("Failed to send ephemeral message %s", e)
            return None

    # @property
    # def help_text(self):
    #     return get_help_text(self.slash_cmd)

    def get_user_id_by_email(self, email):
        try:
            response = self.slack_app.client.users_lookupByEmail(email=email)
            return response["user"]["id"]
        except Exception as e:
            logging.error("Error retrieving user ID for name %s: %s", email, e)
            raise

    # def get_user_id_by_name(self, name):
    #     try:
    #         user = LinearAPIService().get_user(name)
    #         email = user.get("email")
    #         if email:
    #             response = self.slack_app.client.users_lookupByEmail(email=email)
    #             return response["user"]["id"]
    #     except Exception as e:
    #         logging.error("Error retrieving user ID for name %s: %s", name, e)
    #         raise

    def get_user_info(self, user_id: str):
        try:
            response = self.slack_app.client.users_info(user=user_id)
            return response["user"]
        except Exception as e:
            logging.error("Error retrieving user info for id %s: %s", user_id, e)
            raise

    def get_all_users(self, emails_only=True, is_deleted=False, is_bot=False):
        """
        Get all users in slack

        :param emails_only:
        :param is_deleted:
        :param is_bot:
        :return:
        """
        try:
            response = self.slack_app.client.users_list()
            users = response["members"]
            if not is_deleted:
                users = [user for user in users if not user.get("deleted")]
            if not is_bot:
                users = [user for user in users if not user.get("is_bot")]
            if emails_only:
                return [user.get("profile", {}).get("email") for user in users]
            return users
        except Exception as e:
            logging.error("Error retrieving user info for all users: %s", e)
            raise

    @staticmethod
    def command_parser(command_parts):
        if len(command_parts.split(" ")) > 1:
            command_text = command_parts.split(" ")[0].lower()
            command_args = " ".join(command_parts.split(" ")[1:])
            logging.debug(command_text, command_args, "<--- args")
        else:
            command_text = command_parts
            command_args = ""
            logging.debug(command_text, "<-- no args")

        return command_text, command_args

    # @staticmethod
    # def get_user_manager_info(user_id, client) -> Dict[str, str] | None:
    #     user_info = client.users_info(user=user_id)
    #     user_email = user_info.get("user", {}).get("profile", {}).get("email")
    #     manager = get_optonauts_manager(user_email)
    #     return manager

    # @staticmethod
    # def open_travel_modal(ack, body, client):
    #     ack()
    #     try:
    #         user_id = body["user_id"]
    #         manager = SlackService.get_user_manager_info(user_id, client)
    #         manager_email = (
    #             "No Manager" if not manager else manager.get("email", "Unknown")
    #         )
    #         travel_modal_view = get_travel_modal_view(manager_email)
    #         client.views_open(trigger_id=body["trigger_id"], view=travel_modal_view)
    #     except Exception as e:
    #         logging.error(e)

    # @staticmethod
    # def open_onboarding_modal(ack, body, client):
    #     ack()
    #     try:
    #         client.views_open(trigger_id=body["trigger_id"], view=onboarding_modal_view)
    #     except Exception as e:
    #         logging.info(e)

    # @staticmethod
    # def open_fund_deployment_modal(body: Dict, client: WebClient):
    #     try:
    #         client.views_open(
    #             trigger_id=body["trigger_id"], view=fund_deployment_modal_view
    #         )
    #     except Exception as e:
    #         logging.info(e)

    def search_slack_messages(
        self,
        search_text: str,
        channel_name: str,
        sender_name: Optional[str] = None,
        limit: Optional[int] = 10,
    ) -> List[SlackResponse]:
        """
        Search the messages of a channel.
        Most recent `limit` results are returned

        :param search_text:
        :param channel_name:
        :param sender_name:
        :param limit:
        :return:
        """
        page = 1
        page_count = 1
        matches = []
        while page <= page_count:
            query_str = f"{search_text} in:#{channel_name}"
            if sender_name:
                query_str += f" from:@{sender_name}"
            response = self.slack_user_app.client.search_messages(
                query=query_str, page=page, sort="timestamp"
            )
            page_count = (
                response.data.get("messages").get("pagination").get("page_count")
            )
            if response.data.get("ok"):
                pg_matches = response.data.get("messages").get("matches")
                matches.extend(pg_matches)
                page += 1
            else:
                raise Exception(f"Search slack failed: {response}")

            if limit and len(matches) >= limit:
                return matches[:limit]

        return matches

    # def get_conversation_history(
    #     self,
    #     channel_id: str,
    #     oldest: str,
    #     latest: str,
    #     ignore_bots=True,
    # ) -> List[Dict[str, str]]:
    #     """
    #     Get sorted history between oldest and latest for a channel

    #     :param channel_id:
    #     :param oldest:
    #     :param latest:
    #     :param ignore_bots:
    #     :return: a list of dicts containing
    #         'username', 'text', 'user_id', and 'epoch_utc'

    #     """
    #     try:
    #         oldest = str(
    #             typing.cast(pendulum.DateTime, pendulum.parse(oldest)).timestamp()
    #         )
    #         latest = str(
    #             typing.cast(pendulum.DateTime, pendulum.parse(latest)).timestamp()
    #         )
    #     except ParserError:
    #         logging.error(
    #             "oldest and latest must be valid datetime strings, not %s %s",
    #             oldest,
    #             latest,
    #         )
    #         raise

    #     msgs = []
    #     user_id_to_info = {}
    #     try:
    #         next_cursor = None
    #         while True:
    #             response = self.slack_user_app.client.conversations_history(
    #                 cursor=next_cursor,
    #                 channel=channel_id,
    #                 oldest=oldest,
    #                 latest=latest,
    #             )
    #             for msg in response.data["messages"]:
    #                 if msg.get("bot_id") and ignore_bots:
    #                     continue
    #                 if msg.get("text"):
    #                     user_id = msg.get("user")
    #                     if not user_id:
    #                         pass
    #                     if user_id not in user_id_to_info:
    #                         user_info = self.get_user_info(user_id)
    #                         name = user_info.get("real_name") or user_info.get(
    #                             "name", "unknown"
    #                         )
    #                         user_id_to_info[user_id] = name

    #                     msgs.append(
    #                         {
    #                             "username": user_id_to_info.get(user_id, "unknown"),
    #                             "user_id": user_id or "unknown",
    #                             "epoch_utc": msg.get("ts", "unknown"),
    #                             "text": msg["text"],
    #                         }
    #                     )

    #             next_cursor = None
    #             if response.data["has_more"] and response.data["response_metadata"]:
    #                 next_cursor = response.data["response_metadata"].get("next_cursor")
    #             if not next_cursor:
    #                 break

    #         msgs = sorted(msgs, key=lambda x: x["epoch_utc"])
    #         return msgs

    #     except Exception as e:
    #         logging.error(
    #             "Error getting conversations history for %s: %s", channel_id, e
    #         )
    #         raise

    def get_all_channels(self, exclude_archive=True, is_member_only=True) -> List[Dict]:
        channels = []
        try:
            next_cursor = None
            while True:
                response = self.slack_user_app.client.conversations_list(
                    cursor=next_cursor,
                    exclude_archive=exclude_archive,
                )
                if is_member_only:
                    channels.extend(
                        [
                            channel
                            for channel in response["channels"]
                            if channel["is_member"]
                        ]
                    )
                else:
                    channels.extend(response["channels"])
                next_cursor = response.data["response_metadata"].get("next_cursor")
                if not next_cursor:
                    break

            return channels

        except Exception as e:
            logging.error(f"Error getting all channels: {e}")
            raise

    def get_channel_id(self, channel_name: str) -> str:
        try:
            next_cursor = None
            while True:
                response = self.slack_user_app.client.conversations_list(
                    cursor=next_cursor,
                )
                for channel in response["channels"]:
                    if channel["name"] == channel_name:
                        return channel["id"]
                next_cursor = response.data["response_metadata"].get("next_cursor")
                if not next_cursor:
                    raise ValueError(f"Channel {channel_name} not found")

        except Exception as e:
            logging.error(f"Error fetching channel ID: {e}")
            raise

    def get_last_n_messages(self, limit: int, channel_name: str):
        try:
            channel_id = self.get_channel_id(channel_name)
            next_cursor = None
            all_messages = []
            while True:
                response = self.slack_user_app.client.conversations_history(
                    channel=channel_id, limit=20, cursor=next_cursor
                )
                msgs = response.data.get("messages", [])
                sorted_msgs = sorted(
                    msgs, key=lambda msg: float(msg["ts"]), reverse=True
                )
                all_messages.extend(sorted_msgs)

                all_messages.extend(response.data.get("messages", []))
                if len(all_messages) >= limit:
                    return all_messages[:limit]

                next_cursor = response.data["response_metadata"].get("next_cursor")

        except Exception as e:
            logging.error(f"Error getting last {limit} messages: {e}")
            raise

