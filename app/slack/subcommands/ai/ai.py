import logging
from typing import Dict

import slack_sdk

from app.services.slack import slack_service
from app.slack.modals.get_ai_insights_modal import get_ai_insights_modal_view


def handle_ai_subcommand(
    command_args: str,
    client: slack_sdk.web.client.WebClient,
    body: Dict,
):
    response_url = body["response_url"]

    try:
        logging.info(command_args)
        modal_view = get_ai_insights_modal_view(command_args)
        client.views_open(trigger_id=body["trigger_id"], view=modal_view)

        slack_service.send_ephemeral_message(
            response_url, message="Request made. Please wait a few moments..."
        )
    except Exception as e:
        logging.error(e)
