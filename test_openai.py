# # test_openai.py

# from app.services.openai.openai_service import OpenAIService  # adjust import path if needed

# def main():
#     openai_service = OpenAIService("competitor")
#     response = openai_service.ask_ai_assistant_question("How does Jupiter Computing Solutions do vs Zeon Tech?")
#     print("Response from assistant:")
#     print(response)

# if __name__ == "__main__":
#     main()
from openai import OpenAI
import os
from app.services.get_secret import get_secret


client = OpenAI(api_key=get_secret('OPENAI_API_KEY'))

# Step 1: Create a new thread
thread = client.beta.threads.create()

# Step 2: Add a message to the thread
client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content="How does Jupiter Computing Solutions compare to Zeon Tech?"
)

# Step 3: Run the assistant
run = client.beta.threads.runs.create_and_poll(
    thread_id=thread.id,
    assistant_id="asst_KdL0y9tMk3NAArtcTNwGHFzU"
)

# Step 4: Get response
if run.status == "completed":
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    for msg in messages.data:
        print(msg.role, msg.content)
else:
    print(f"Run failed: {run.status}")
    print(run)
    print("Detailed error →", run.last_error)  # <‑‑ add this

