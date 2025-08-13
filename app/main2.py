from dotenv import load_dotenv
load_dotenv()

import uvicorn
from fastapi import FastAPI
from multiprocessing import Process

from app.routes import transfer
from app.routes.openai import openai
from app.services.slack import slack_service
from app.slack import commands
from app.slack import views
from threading import Thread

import logging

logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more verbosity
    format="%(asctime)s - %(levelname)s - %(message)s"
)


app = FastAPI()
app.include_router(transfer.router)
app.include_router(openai.router)


def start_slack_bolt():
    slack_service.run_bolt_app()  # blocking call, must run in main thread of this process


def main():
    # Start Slack Bolt app in a new process (so it can use signal.signal)
    slack_process = Process(target=start_slack_bolt)
    slack_process.start()

    # Run Uvicorn with FastAPI app in the main process
    uvicorn.run("app.main2:app", host="0.0.0.0", port=8080, log_level="info")


if __name__ == "__main__":
    main()
