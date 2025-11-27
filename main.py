from fastapi import FastAPI, Query
from typing import Optional
from datetime import datetime, timedelta
from stackapi import StackAPI
import re
from fastapi import FastAPI, Body
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from datetime import datetime
import os

app = FastAPI()

def fetch_stackoverflow_questions(
    tagged: str = 'artificial-intelligence',
    max_pages: int = 1,
    pagesize: int = 5,
    sort: str = 'creation',
    order: str = 'desc',
    fromdate: int = int((datetime.utcnow() - timedelta(days=7)).timestamp()),
    todate: int = int(datetime.utcnow().timestamp())
) -> dict:
    """
    Fetch recent Stack Overflow questions by tag.
    Returns a list of dicts with 'title', 'link', 'content', 'date' and 'score'.
    """
    SITE = StackAPI('stackoverflow')
    SITE.max_pages = max_pages
    params = {
        'sort': sort,
        'order': order,
        'tagged': tagged,
        'filter': 'withbody',
        'pagesize': pagesize,
        'fromdate': fromdate,
        'todate': todate
    }

    response = SITE.fetch('questions', **params)
    results = []
    for item in response['items']:
        body_html = item.get('body', '')
        body_text = re.sub('<[^<]+?>', '', body_html)
        results.append({
            'title': item['title'].replace('"', "'"),
            'link': item['link'],
            'content': body_text[:1000].replace('"', "'"),  # truncate
            'date': datetime.utcfromtimestamp(item['creation_date']).date(),
            'score': item['score']
        })
    return {"results": results}

def save_agent_response_to_blob(agent_response: str) -> str:
    """
    Saves the agent response as a JSON blob in Azure Blob Storage.
    """
    # Step 1: Load environment variables
    load_dotenv()
    connect_str = os.getenv("STORAGE_ACCOUNT_CONNECTION_STRING")
    container_name = "agent-responses"

    # Step 2: Create a unique blob name
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    blob_name = f"response-{timestamp}.json"

    # Step 3: Connect to Azure Blob Storage
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    container_client = blob_service_client.get_container_client(container_name)

    # Step 4: Create container if it doesn't exist
    try:
        container_client.create_container()
    except Exception:
        pass  # Assume container already exists

    # Step 5: Upload the agent response
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(agent_response, overwrite=True)

    print(f"✅ Agent response saved to blob: {blob_name}")
    return blob_name

@app.get("/questions")
def get_questions(
    tagged: Optional[str] = Query("artificial-intelligence"),
    pagesize: Optional[int] = Query(5),
    sort: Optional[str] = Query("creation"),
    order: Optional[str] = Query("desc"),
    days: Optional[int] = Query(7)
):
    """
    Endpoint to fetch recent Stack Overflow questions by tag.
    Example: /questions?tagged=python&pagesize=3&days=2
    """
    fromdate = int((datetime.utcnow() - timedelta(days=days)).timestamp())
    todate = int(datetime.utcnow().timestamp())
    return fetch_stackoverflow_questions(
        tagged=tagged,
        pagesize=pagesize,
        sort=sort,
        order=order,
        fromdate=fromdate,
        todate=todate
    )

@app.post("/save-response")
def save_response(agent_response: str = Body(..., embed=True)):
    """
    Endpoint to save agent response to Azure Blob Storage.
    Example request:
    {
        "agent_response": "Hello world"
    }
    """
    blob_name = save_agent_response_to_blob(agent_response)
    return {"blob_name": blob_name}