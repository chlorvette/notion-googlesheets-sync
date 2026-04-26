import os.path
from dotenv import load_dotenv
import uuid
import json
import datetime
from notion_client import Client

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
        values = result.get("values", [])

        if not values:
            print("No data found.")
            return

        for row in values:
            try:
                if row[6] == "":
                    row.append(uuid.uuid4().hex)
                    update_result = (
                        service.spreadsheets().values().update(
                            spreadsheetId=SPREADSHEET_ID,
                            range=f"todo!G{values.index(row) + 2}",
                            valueInputOption="RAW",
                            body={"values": [[row[6]]]}
                        )
                        .execute()
                    )
                if len(row) < 8:
                    row.append(datetime.datetime.now().isoformat())
                    update_result = (
                        service.spreadsheets().values().update(
                            spreadsheetId=SPREADSHEET_ID,
                            range=f"todo!H{values.index(row) + 2}",
                            valueInputOption="RAW",
                            body={"values": [[row[7]]]}
                        )
                        .execute()
                    )
                print(f"{row[0]}, {row[1]}, {row[2]}, {row[3]}, {row[4]}, {row[5]}, {row[6]}, {row[7]}")
                if row[6] not in data.keys():
                        data[row[6]] = {
                            "checked": row[0],
                            "name": row[1],
                            "status": row[2],
                            "due": row[3],
                            "priority": row[4],
                            "effort": row[5],
                            "last_updated": row[7]
                        }
            except:
                break
    except HttpError as err:
        print(err)
    
    with open(DATA_FILE_PATH, "w") as data_file:
        json.dump(data, data_file, indent=4)

    

if __name__ == "__main__":
    main()