import hashlib
import json
import sys
import os

def sha256(data):
    hash_object = hashlib.sha256()
    hash_object.update(json.dumps(data).replace(' ', '').encode())
    hex_dig = hash_object.hexdigest()
    return hex_dig

def get_file_content(file_name):
    if not os.path.exists(file_name):
        print(f"ERROR: {file_name} file does not exist")
        sys.exit()
    with open(file_name, 'r') as f:
        data = [line.strip() for line in f.readlines()]

    return data

def get_data_for_token(name):
    # print("name: ",name)
    if name == '':
        file = f'data/token.txt'
    else:
        file = f'data/token-{name}.txt'
    datas = get_file_content(file)
    return datas
