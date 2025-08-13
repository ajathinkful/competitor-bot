from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import os
from dotenv import load_dotenv

load_dotenv()  # Loads SLACK_BOT_TOKEN and SLACK_APP_TOKEN from .env

# Initializes your Slack app with your bot token
app = App(token=os.environ["SLACK_BOT_TOKEN"])

# Slash command handler
@app.command("/competitor")
def handle_competitor_command(ack, respond, command):
    ack()
    user_input = command["text"]
    respond(f"Got it! You said: {user_input}")

# Starts your app in Socket Mode
if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
