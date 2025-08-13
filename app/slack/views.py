import logging
from typing import Dict
import json

from slack_bolt import Ack


from app.services.slack import slack_service

from ..services.openai.openai_service import OpenAIService




@slack_service.slack_app.view("ai_modal_view")
def handle_get_ai_submission(ack, body, view, client):
    ack()
    user_id = body["user"]["id"]
    values = body["view"]["state"]["values"]
    question = values["question"]["question_input"]["value"]
    model = values["model_choice"]["model_select"]["selected_option"]["value"]
    # files = values["file_block_id"]["file_input_action_id_1"]["files"]
    # file_urls = [f["url_private_download"] for f in files]

    openai_serv = OpenAIService(model)

    ai_response = openai_serv.ask_ai_assistant_question(question, [])

    full_response_blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*You asked the {model} assistant:*"},
        },
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_preformatted",
                    "elements": [{"type": "text", "text": question}],
                }
            ],
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Response:*"}},
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_preformatted",
                    "elements": [{"type": "text", "text": ai_response}],
                }
            ],
        },
    ]

    full_response_blocks.extend(
        [
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Could this response be better?",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Create an issue",
                        "emoji": True,
                    },
                    "action_id": "create_an_issue_action",
                },
            },
        ]
    )

    slack_service.send_message(
        user_or_ch_id=user_id,
        blocks=full_response_blocks,
        as_user=True,
    )
