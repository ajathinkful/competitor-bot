- What is a "competitor bot standalone?"
    Basically its a slack bot/app that you can add to your slack workspace. This one allows you to summon it
    to a channel with a slash command and ask it questions about how your company compares to competing companies based on files you have uploaded to a shared folder on google drive.

- What you'll need:
    Openai api account with a quota (min is $5 at the time I wrote this).
    slack workspace
    slack api account
    gcp account (for service account)
    aws account for s3 and IAM
    Postman (for api calls for s3 and Vector Store)


- How do I create a slack bot?
    Josh Plumley wrote a really good guide that I will try to summarize below:
    Quick Start (Slack API Side)
    ---
    1. Clone this repo that you are reading.
    2. Go to https://api.slack.com/apps . Login with Slack
    3. Select `Create New App` . Select `From an App Manifest` .
    4. (Conditional) You may be given a selection of workspaces to develop your bot in. Choose your Slack workspace.
    5. Enter the following `App Manifest` below as a JSON file. Replace the `<<` and `>>` bracketed values with the values you want the app to have.
    ```json
    {
        "display_information": {
            "name": "<<Logical App Name Human Readable>>"
        },
        "features": {
            "bot_user": {
                "display_name": "<<Name You Want Bot To Have In Slack>>",
                "always_online": true
            },
            "slash_commands": [
                {
                    "command": "<<Unique Slash Command like /itwontbethis >>",
                    "description": "Local T2 Bot Slash Command",
                    "should_escape": false
                }
            ]
        },
        "oauth_config": {
            "scopes": {
                "bot": [
                    "chat:write",
                    "commands",
                    "users:read",
                    "users:read.email"
                ]
            }
        },
        "settings": {
            "interactivity": {
                "is_enabled": true
            },
            "org_deploy_enabled": true,
            "socket_mode_enabled": true,
            "token_rotation_enabled": false
        }
    }
    ```
    6. Review the summary of your app. If you fed it the manifest above, it should have all the recommended `OAuth`, `Features`, and `Settings` you need. (If you didn't edit the values above, it'll yell at you! They placeholders contain illegal characters. **Please change them.**)
    7. Click `Create`.
    8. (Optional But Not Really) Find an icon to give your bot.
    9. Create an App Level Token, under Settings -> Basic Information -> App-Level Tokens. Give it all three of the following scopes:
        - `connections:write`
        - `authorizations:read`
        - `app_configurations:write`
    10. Request to have your bot installed into the Opto workspace, under Settings -> Install App.
        - You should have to approve your own request in Slack
    11. Find the following values at the following locations. They'll become environment variables later:
        - `SLACK_SIGNING_SECRET=` , under Settings -> Basic Information -> App Credentials -> Signing Secret
        - `SLACK_APP_TOKEN=xapp-`, under Settings -> Basic Information -> App-Level Tokens. (as above in step 9)
        - `T2_SLACK_BOT_TOKEN=xoxb-`, under Settings -> Install App.
    12. Once your bot has been installed into the Opto workspace, you have to summon it into the channels you want it to reply to. I'd recommend making your own! One more variable is only available after the bot is installed to a workspace.

    At this point, your bot should be ready to go. You should be able to go to the channels and even enter the slash command you entered above, such as `/itwontbethis`, and Slackbot should reply with `dispatch_failed` errors.

- Set up:
    - make a .env
    - these are the variables you will need:
        SLACK_SIGNING_SECRET=
        SLACK_APP_TOKEN=
        SLACK_BOT_TOKEN=
        SLACK_SLASH_CMD=

        AWS_ACCESS_KEY_ID=
        AWS_SECRET_ACCESS_KEY=
        BUCKET_NAME=
        S3_FOLDER_PREFIX=

        GOOGLE_APPLICATION_CREDENTIALS=( .json file discussed further below)
        GDRIVE_NAME=
        FOLDER_ID=

        VECTOR_STORE_ID=
        OPENAI_API_KEY=
        ASSISTANT_ID=

- Here are some usful setup instructions for the Google Service account, S3 Account, and OpenAI API account:
    
    GCP:
        - When you make a GCP account it should make a default project/shouldn't be hard to get to a default project called "My First
        Project". 
        - Try to find Service Accounts in the menu (should be under IAM and admin)
        - Click the “Create Service Account” button
        - Enter a name like gdrive-to-s3-bot (Optional) Add a description like Access Google Drive for S3 sync
        - Click “Create and Continue”
        - Permissions Step — You Can Skip
        - When it asks to grant roles:
        Just click “Continue” without assigning any roles — for accessing Google Drive as a shared user, no project-level permissions are needed.
        - Create Key: After you create the account: 
        - Go to the service account’s “Keys” tab
        - Click “Add Key” > “Create New Key”, Choose JSON, Click Create
        - Save the .json file — this is your service account credentials file

        - How to use this Service Account key JSON:
            Save the JSON file somewhere safe in your project
            e.g., service_account_key.json

            Use it in your Python code to authenticate to Google APIs
            For example, in your existing GoogleService class you can load this JSON to create credentials like this:
            GOOGLE_APPLICATION_CREDENTIALS=[Your Service Account key here].json

        - Now that you have a service account you're going to want to share the email associated with that service account with 
        a folder in your google drives that contains information about company competitors. (I will attach info for a fictional company so you can test with the slack bot.)
    
    AWS:
        - create an IAM user for s3
        -  Step 1: Specify User Details
            Go to IAM in the AWS Console.

            Click “Users” → “Add users”.

            Username: e.g., gdrive-to-s3-bot

            Access type:  Check "Access key - Programmatic access"

            (This generates the access key and secret key you'll put in your .env)

            do not select “Provide user access to the AWS Management Console.”

        - Step 2: Set Permissions
            Choose one of:

             Attach existing policies directly

            Search for AmazonS3FullAccess
        
        - Step 3: Review and Create
            Review the user info.

            Click Create user.

            You’ll get:

            Access key ID

            Secret access key

            Copy and save these immediately — AWS won’t show the secret key again.

        - Step 4 Make a s3 bucket and make note of the prefix
    
    OpenAI:
        -  you must add billing to use OpenAI's Assistants API (as of July 2025)
        I reccomend doing the minimum amount if you'd like to test https://platform.openai.com/settings/organization/billing/overview
        - I forgot the order but I think you'll want to create a vector store first that way
        you can attach it to an assistant when you create an assistant (you'll have to do both anyways)
        here are some links for setting those up.
        https://platform.openai.com/storage/vector_stores
        https://platform.openai.com/assistants

- Once everything is set up you can start the app locally with poetry run main2

- On successful start you should see something like this in the terminal window:
    $ poetry run main2
    INFO:     Started server process 
    INFO:     Waiting for application startup.
    INFO:     Application startup complete.
    INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
     - INFO - A new session has been established (session id: 
     - INFO - Bolt app is running!
     - INFO - Starting to receive messages from a new connection (session id: 

- You will first have to populate your s3 bucket and vector stores using Postman
Here are the most useful HTTP reqs you can use for this:
    POST http://127.0.0.1:8080/gdrive-battlecards-to-s3
    POST http://127.0.0.1:8080/openai/assistants/competitor/add_ai_data_to_ingest_to_vector_store
    DELETE http://127.0.0.1:8080/openai/assistants/competitor/clear_vector_store
    DELETE http://127.0.0.1:8080/openai/assistants/competitor/clear_all_openai_files

- now you can go into slack and run your slash command followed by ai example: "/competitor ai"

- The modal will open and you can select competitor bot from the drop down and ask a question.
for example: "Who are our competitors/what are their products?"


- For the future:
    - currently the slack bot only accepts word docs from the shared folder (I have seen it work with different file types/will be improved on in the future.)
    - It could be deployed such that a scheduler  (left some commented-out code for inspiration) can upload/update the s3 and vector store.
    - i have seen it work with a shared drive via google work space vs what we currently have (a shared folder)
    - currently costs min $5 due to openai api usage. currently using free plans for aws s3 and gcp.

