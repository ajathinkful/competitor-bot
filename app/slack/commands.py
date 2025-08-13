import logging

from app.services.openai.openai_service import OpenAIService
from app.services.slack import slack_service

from app.slack.subcommands.ai.ai import handle_ai_subcommand

from app.utils import (
    is_valid_url,
)


@slack_service.slack_app.command(slack_service.slash_cmd)
def handle_get_command(ack, body, client, say):
    ack()
    command_parts = body.get("text", "").strip().lower()
    command_text, command_args = slack_service.command_parser(command_parts)

    # Extract the username and the text portion of the command
    user_id = body["user_id"]
    user_info = client.users_info(user=user_id)
    username = user_info["user"]["profile"]["display_name_normalized"]
    email = user_info["user"]["profile"]["email"]
    channel_id = body["channel_id"]
    response_url = body["response_url"]

    # This is only used for debugging really.
    logging.info("> @%s: `%s %s`\n", username, slack_service.slash_cmd, command_parts)
    slack_service.send_ephemeral_message(
        response_url,
        f"`{slack_service.slash_cmd} {command_parts}`",
    )

    match command_text:
        case "ai":
            handle_ai_subcommand(command_args, client, body)

