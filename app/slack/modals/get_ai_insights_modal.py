from typing import Dict


def get_ai_insights_modal_view(model_choice: str | None = None) -> Dict:
    opts: Dict = {
        "type": "modal",
        "callback_id": "ai_modal_view",
        "title": {"type": "plain_text", "text": "Get AI Insights"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "blocks": [
            {
                "type": "input",
                "block_id": "model_choice",
                "element": {
                    "type": "static_select",
                    "placeholder": {"type": "plain_text", "text": "Select a model"},
                    "action_id": "model_select",
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "competitor bot"},
                            "value": "competitor",
                        }
                        
                    ],
                },
                "label": {
                    "type": "plain_text",
                    "text": "Which Model?",
                },
            },
            {
                "type": "input",
                "block_id": "question",
                "element": {
                    "type": "plain_text_input",
                    "multiline": True,
                    "action_id": "question_input",
                    "initial_value": "Please parse this document according to your system instructions"
                    if model_choice == "invoice"
                    else "",
                },
                "label": {"type": "plain_text", "text": "Question?"},
            },
        ],
    }

    # Find the matching option and set it as initial_option
    if model_choice:
        for option in opts["blocks"][0]["element"]["options"]:
            if option["value"] != model_choice:
                continue
            opts["blocks"][0]["element"]["initial_option"] = {
                "text": option["text"],
                "value": option["value"],
            }
            break

    # If no initial option is found, set the default option
    if "initial_option" not in opts["blocks"][0]["element"]:
        opts["blocks"][0]["element"]["initial_option"] = {
            "text": {
                "type": "plain_text",
                "text": "competitor bot",
            },
            "value": "competitor",
        }

    return opts
