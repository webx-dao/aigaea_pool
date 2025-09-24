import os
import sys
import json
from dotenv import find_dotenv, load_dotenv, get_key, set_key

load_dotenv(find_dotenv('.env'))

def get_envsion(key, format=True):
    if format:
        value = []
        valueStr = get_key(find_dotenv('.env'), key_to_get=key)
        if valueStr != None:
            value = valueStr.split(',')
    else:
        value = get_key(find_dotenv('.env'), key_to_get=key)
    return value

def set_envsion(key, value, format=True):
    if format:
        valueStr = ','.join(value)
    else:
        valueStr = value
    return set_key(find_dotenv('.env'), key_to_set=key, value_to_set=valueStr)


EMAIL_MODE = os.getenv("EMAIL_MODE", default="email")  # 邮件模式
EMAIL_TO = get_envsion("EMAIL_TO")  # 接收人
## EMAIL配置
EMAIL_BLACKLIST = {}
EMAIL_HOST = os.getenv("EMAIL_HOST", default="smtp.qq.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", default=587))
EMAIL_USERNAME = get_envsion("EMAIL_USERNAME")  # 发件人
EMAIL_PASSWORD=os.getenv("EMAIL_PASSWORD", default='')
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
## SES配置
SES_SENDER = os.getenv("SES_SENDER", default="")
SES_REGION = os.getenv("SES_REGION", default="")
SES_ACCESS_KEY = os.getenv("SES_ACCESS_KEY", default="")
SES_SECRET_ACCESS_KEY = os.getenv("SES_SECRET_ACCESS_KEY", default="")
MAIL_CONFIG = {
    "mode": EMAIL_MODE,
    "host": EMAIL_HOST,
    "port": EMAIL_PORT,
    "userlist": EMAIL_USERNAME,
    "password": EMAIL_PASSWORD,
    "sender": SES_SENDER,
    "region": SES_REGION,
    "accesskey": SES_ACCESS_KEY,
    "secretkey": SES_SECRET_ACCESS_KEY,
}

# WEB3
WEB3_RPC_FIXED=os.getenv("WEB3_RPC_FIXED", default="https://base.drpc.org")
WEB3_RPC=os.getenv("WEB3_RPC", default="https://mainnet.base.org")
WEB3_EXPLORER=os.getenv("WEB3_EXPLORER", default="https://basescan.org")
WEB3_CHAINID=int(os.getenv("WEB3_CHAINID", default=8453))
CONTRACT_USDC=os.getenv("CONTRACT_USDC", default="0x833589fcd6edb6e08f4c7c32d4f71b54bda02913")
WEB3_SENDER_PRIKEY=os.getenv("WEB3_SENDER_PRIKEY", default="")  # 冷钱包私钥
if len(WEB3_SENDER_PRIKEY) != 64:
    print(f"WEB3_SENDER_PRIKEY Data anomalies")
    exit
