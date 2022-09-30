from dataclasses import field
from operator import contains
from time import sleep
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import argparse
import os
from config import  SCOPE, CREDENTIALS_FILE, TOKEN_FILE
import logging
import time

SCOPES = [SCOPE]

LOGS_FOLDER = os.path.join(os.path.dirname(__file__), "logs")
print(LOGS_FOLDER)
SUCCESS_FILE = os.path.join(LOGS_FOLDER, "success.log")
ERROR_FILE = os.path.join(LOGS_FOLDER, "error.log")
LOG_FILE = os.path.join(LOGS_FOLDER, "log.log")

class Logger():
    def __init__(self, file_name, formatter = None):
        self.logger = logging.getLogger(file_name)
        self.logger.setLevel(logging.DEBUG)
        handle = logging.FileHandler(file_name, "a")
        handle.setLevel(logging.DEBUG)
        if formatter:
            handle.setFormatter(formatter)
        self.logger.addHandler(handle)
    
    def info(self, message):
        self.logger.info(message)
    
    def error(self, message):
        self.logger.error(message)
        
logger_error = Logger(ERROR_FILE)
logger_success = Logger(SUCCESS_FILE)
logger_log = Logger(LOG_FILE)

COUNT = 1

def get_list_by_type(service, type, supportDrive, parent_id = None, name = None):
    q = "trashed=false"
    if type == "folder":
        q += " and mimeType='application/vnd.google-apps.folder'"
    elif type == "file":
        q += " and mimeType!='application/vnd.google-apps.folder'"
        
    if parent_id:
        q += " and '{}' in parents".format(parent_id)
        
    if name:
        q += " and name = '{}'".format(name)
        
    list_types = service.files().list(q=q, fields='files(id, name, mimeType)', orderBy="createdTime", supportsAllDrives=supportDrive).execute() 
    return list_types.get("files")

def get_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    
    service = build('drive', 'v3', credentials=creds)
    return service

def check_id(id):
    if id:
        return True
    return False

def copy_files(service,fileId, folder_parent_id_target):
    if(check_id(fileId) == False):
        return
    request_body = { 'parents' : [ folder_parent_id_target ]}
    service.files().copy(fileId=fileId, body=request_body, supportsAllDrives=True).execute()
    pass

def getFolderId(data_array,id,type):
    for item in data_array:
        if id in item:
            return item.split(".")[type]
    return None

def run_service(service, folder_shared_parent_id, folder_parent_id_target, data_sucess, data_error ):
    share_folders = get_list_by_type(service, "folder", True, folder_shared_parent_id)
    share_files = get_list_by_type(service, "file", True, folder_shared_parent_id)
    
    for f in share_files:
        check_success_file = getFolderId(data_sucess, f["id"], 0)
        check_error_file = getFolderId(data_error, f["id"],0)
        if check_error_file == None and check_success_file:
            continue
        
        try:
            copy_files(service, f["id"], folder_parent_id_target)
            logger_success.info("{}.{}.{}".format(f["id"],folder_shared_parent_id,folder_parent_id_target))
        except:
            logger_error.error("{}.{}.{}".format(f["id"],folder_shared_parent_id,folder_parent_id_target))
    
    for f in share_folders:
        name_folder = {
            'name': f["name"],
            'mimeType': "application/vnd.google-apps.folder",
            'parents': [folder_parent_id_target]
        }
        check_success_folder_target = getFolderId(data_sucess, f["id"],2)
        
        if check_success_folder_target:
            pass
        else:
            folder = service.files().create(body=name_folder, fields="id").execute()
            check_success_folder_target = folder.get("id")
        run_service(service, f["id"], check_success_folder_target, data_sucess, data_error)
        
def get_args_from_cli():
    parser = argparse.ArgumentParser(description='Input!')
    parser.add_argument("folder_id_clone", help= "print your folder parent share id(required) otherwise get default = INPUT_PARENT_ID",nargs="?")
    parser.add_argument("turn_on_off_flag",help="Turn on if you wish to run again after error(optional)", nargs="?", default=False)
    parser.add_argument("folder_id_target", help= "print your save folder parent id(optional)", nargs="?")

    args = parser.parse_args()
    
    return args

def read_file_log(path):
    with open(path) as datas: 
        datas = datas.readlines()
    return datas



def main():
    print("Clone folder from google drive")
    service = get_service()
    args = get_args_from_cli()
    
    folder_id_clone = args.folder_id_clone
    folder_id_target = args.folder_id_target
    turn_on_off_flag = args.turn_on_off_flag
    
    shared_parent_folder = service.files().get(fileId=folder_id_clone, supportsAllDrives=True, fields="*").execute()
    folder_shared_parent_id = shared_parent_folder.get("id")
    parent_name = shared_parent_folder.get("name")
    
    request_target_folder = {
        'name': parent_name,
        'mimeType': "application/vnd.google-apps.folder"
    }
    
    if folder_id_target:
        request_target_folder["parents"] = [folder_id_target]

    data_log = read_file_log(LOG_FILE)
        
    folder_parent_id_target = ""
    if len(data_log):
        folder_parent_id_target = data_log[0].strip()
    else:
        folder_parent_target = service.files().create(body=request_target_folder, fields="id").execute()
        folder_parent_id_target = folder_parent_target.get("id")
        logger_log.info(folder_parent_id_target)
        
    flagOK = False
    while flagOK == False:
        try:
            flagOK = True
            data_success = read_file_log(SUCCESS_FILE)
            data_error = read_file_log(ERROR_FILE)
            
            data_success = [f.strip() for f in data_success]
            data_error = [f.strip() for f in data_error]
            run_service(service, folder_shared_parent_id, folder_parent_id_target, data_success, data_error)
                 
        except:
            if turn_on_off_flag == False:
                raise Exception("Finishing")
            flagOK = False
        if flagOK == False:
            print("Sleep! Keep continue after 1 day!")
            time.sleep(86400)
            print("Start again!")
    
if __name__ == '__main__':
    main()