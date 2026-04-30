import os.path
from dotenv import load_dotenv
import uuid
import json
import datetime
from notion_client import Client
import pprint

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()
client = Client(auth=os.environ.get("NOTION_TOKEN"))

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
RANGE_NAME = "todo!A2:H"
DATA_FILE_PATH = os.environ.get("DATA_FILE_PATH")

def get_color(text):
    if text == "not started" or text == "high":
        return "red"
    elif text == "in progress" or text == "medium":
        return "yellow"
    elif text == "complete" or text == "low":
        return "green"

def main():
    creds = None
        
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    if os.path.exists(DATA_FILE_PATH):
        with open(DATA_FILE_PATH, "r") as data_file:
            data = json.load(data_file)
    else:
        data = {}

    try:
        service = build("sheets", "v4", credentials=creds)

        # Call the Sheets API
        sheet = service.spreadsheets()
        result = (
                sheet.values()
                .get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME)
                .execute()
        )
        sheets_values = result.get("values", [])
        notion_to_add = {}

        if not sheets_values:
            print("No data found.")
            return

        for row in sheets_values:
            try:
                sync_id = row[6]
                if sync_id == "":
                    row.append(uuid.uuid4().hex)
                    service.spreadsheets().values().update(spreadsheetId=SPREADSHEET_ID, range=f"todo!G{sheets_values.index(row) + 2}", valueInputOption="RAW", body={"values": [[sync_id]]}).execute()
                if len(row) < 8:
                    row.append(datetime.datetime.now().isoformat())
                    service.spreadsheets().values().update(spreadsheetId=SPREADSHEET_ID, range=f"todo!H{sheets_values.index(row) + 2}", valueInputOption="RAW", body={"values": [[row[7]]]}).execute()
                if sync_id not in data.keys():
                        data[sync_id] = {
                            "checked": row[0],
                            "name": row[1],
                            "status": row[2],
                            "due": row[3],
                            "priority": row[4],
                            "effort": row[5],
                            "last_updated": row[7]
                        }
                        notion_to_add[sync_id] = data[sync_id]
                else:
                    item_properties = data[sync_id]
            except:
                break
    except HttpError as err:
        print(err)

    # fetch notion

    notion_database = client.databases.retrieve(os.environ.get("DATABASE_ID"))
    notion_database_items = client.data_sources.query(data_source_id=notion_database["data_sources"][0]["id"])
    sheets_to_add = []

    for database_item in notion_database_items["results"]:
        item_properties = database_item["properties"]
        print(item_properties)
        sync_id = item_properties["sync_id"]['rich_text'][0]['plain_text']
        if not sync_id in data.keys():
            data[sync_id] = {
                "checked": str(item_properties["Checkbox"]['checkbox']).upper(),
                "name": item_properties["Name"]['title'][0]['text']['content'],
                "status": item_properties["status"]['status']['name'],
                "due": item_properties["due"]['date']['start'].replace("-", "/"),
                "priority": item_properties["priority"]['select']['name'],
                "effort": item_properties["effort"]['select']['name'],
                "last_updated": datetime.datetime.now().isoformat()
            }
            sheets_to_add.append(data[sync_id])

    with open(DATA_FILE_PATH, "w") as data_file:
            json.dump(data, data_file, indent=4)
    
    for item_sync_id in notion_to_add:
        client.pages.create(parent={"database_id": os.environ.get("DATABASE_ID")}, properties={
            'last_updated': {
                'type': 'rich_text', 
                'rich_text': [
                    {
                        'type': 'text', 
                        'text': {
                            'content': notion_to_add[item_sync_id]['last_updated'], 
                            'link': None
                        }, 
                        'annotations': {
                            'bold': False, 
                            'italic': False, 
                            'strikethrough': False, 
                            'underline': False, 
                            'code': False, 
                            'color': 'default'
                        }, 
                        'plain_text': notion_to_add[item_sync_id]['last_updated'], 
                        'href': None
                    }
                ]
            }, 
            'due': {
                'type': 'date', 
                'date': {
                    'start': datetime.datetime.strptime(notion_to_add[item_sync_id]['due'], "%m/%d/%Y").date().isoformat(),
                    'end': None, 
                    'time_zone': None
                }
            }, 
            'status': {
                'type': 'status', 
                'status': {
                    'name': notion_to_add[item_sync_id]['status'], 
                    'color': get_color(notion_to_add[item_sync_id]['status'])
                }
            }, 
            'effort': {
                'type': 'select', 
                'select': {
                    'name': notion_to_add[item_sync_id]['effort'], 
                    'color': get_color(notion_to_add[item_sync_id]['effort'])
                }
            }, 
            'sync_id': {
                'type': 'rich_text', 
                'rich_text': [
                    {
                        'type': 'text', 
                        'text': {
                            'content': item_sync_id, 
                            'link': None
                        }, 
                        'annotations': {
                            'bold': False, 
                            'italic': False, 
                            'strikethrough': False, 
                            'underline': False, 
                            'code': False, 'color': 
                            'default'
                        }, 
                        'plain_text': item_sync_id, 
                        'href': None
                    }
                ]
            }, 
            'Checkbox': {
                'type': 'checkbox', 
                'checkbox': notion_to_add[item_sync_id]['checked'] == "TRUE"
            }, 
            'priority': {
                'type': 'select', 
                'select': {
                    'name': notion_to_add[item_sync_id]['priority'], 
                    'color': get_color(notion_to_add[item_sync_id]['priority'])
                }
            }, 
            'Name': {
                'id': 'title', 
                'type': 'title', 
                'title': [
                    {
                        'type': 'text', 
                        'text': {
                            'content': notion_to_add[item_sync_id]['name'], 
                            'link': None
                        }, 
                        'annotations': {
                            'bold': False, 
                            'italic': False, 
                            'strikethrough': False, 
                            'underline': False, 
                            'code': False, 
                            'color': 'default'
                        }, 
                        'plain_text': notion_to_add[item_sync_id]['name'], 
                        'href': None
                    }
                ]
            }
        }
    )

if __name__ == "__main__":
    main()