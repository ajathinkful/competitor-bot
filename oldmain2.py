from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from app.routes import transfer
from app.routes.openai import openai
from app.slack import commands
from app.slack import views


from app.services.slack import slack_service
from threading import Thread

app = FastAPI()

app.include_router(transfer.router)
app.include_router(openai.router)

# slack_service.run_bolt_app()

