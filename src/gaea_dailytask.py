import re
import os
import time
import uuid
import requests
import asyncio
import random
import base64
import hashlib
import json
import datetime
from datetime import datetime as dt
from decimal import Decimal
from loguru import logger
from web3 import Web3

from src.gaea_client import GaeaClient
from utils.contract_abi import contract_abi_usdc
from utils.decorators import helper
from utils.email import send_normal_mail, send_mail
from config import get_envsion, set_envsion
from config import WEB3_RPC, WEB3_RPC_FIXED, WEB3_EXPLORER, WEB3_CHAINID, CONTRACT_USDC, WEB3_SENDER_PRIKEY

class GaeaDailyTask:
    def __init__(self, client: GaeaClient) -> None:
        self.client = client

    # --------------------------------------------------------------------------
    # 添加新的公共函数
    def build_base_transaction(self, web3_obj, sender_address, config_chainid):
        """
        构建基础交易参数
        """
        # 获取上个区块Gas
        latest_block = web3_obj.eth.get_block('latest')
        base_fee_per_gas = latest_block['baseFeePerGas']
        priority_fee_per_gas = web3_obj.eth.max_priority_fee  # 获取推荐的小费
        max_fee_per_gas = int(base_fee_per_gas * 1.1) + priority_fee_per_gas  # 增加缓冲
        
        logger.debug(f"Base Fee Per Gas: {base_fee_per_gas} wei")
        logger.debug(f"Max Priority Fee Per Gas: {priority_fee_per_gas} wei")
        logger.debug(f"Max Fee Per Gas: {max_fee_per_gas} wei")
        
        return {
            "chainId": config_chainid,
            "from": sender_address,
            # "nonce": web3_obj.eth.get_transaction_count(sender_address),
            "nonce": web3_obj.eth.get_transaction_count(sender_address, 'pending'),
            "maxFeePerGas": max_fee_per_gas,
            "maxPriorityFeePerGas": priority_fee_per_gas,
            # "gas": base_fee_per_gas * priority_fee_per_gas,
            # "gas": 20000000,  # 最大 Gas 用量
        }

    # 发送交易（重试5次，每次2秒）
    def send_transaction_with_retry(self, web3_obj, transaction, web3_prikey, max_retries=5, retry_interval=2):
        attempt = 0
        while attempt < max_retries:
            try:
                logger.debug(f"transaction: {transaction}")
                # === 动态更新 Gas 参数 ===
                latest_block = web3_obj.eth.get_block('latest')
                base_fee = latest_block['baseFeePerGas']
                # 重试时增加优先费（每次增加10%）
                priority_fee = max(web3_obj.eth.max_priority_fee, 100)  # 设置下限
                if attempt > 0:
                    priority_fee = int(priority_fee * (1 + 0.1 * attempt))  # gas递增
                    transaction['nonce'] = web3_obj.eth.get_transaction_count(transaction['from'], 'pending')  # 更新nonce
                max_fee = base_fee + priority_fee
                # 确保 max_fee 不低于 base_fee
                max_fee = max(max_fee, base_fee + 1)
                # 更新交易参数
                transaction.update({
                    "maxFeePerGas": max_fee,
                    "maxPriorityFeePerGas": priority_fee,
                })
                logger.debug(f"update transaction 1: {transaction}")
                
                # === 估算 Gas ===
                try:
                    gas_limit = web3_obj.eth.estimate_gas(transaction)
                except Exception as e:
                    logger.error(f"Failed to eth.estimate_gas: {str(e)}")
                    gas_limit = 200000
                logger.debug(f"gas_limit: {gas_limit}")
                transaction["gas"] = gas_limit
                logger.debug(f"update transaction 2: {transaction}")
                
                # 使用私钥签名交易
                signed_transaction = web3_obj.eth.account.sign_transaction(transaction, web3_prikey)
                logger.debug(f"signed_transaction: {signed_transaction}")
                # 发送交易
                try:
                    # 发送交易
                    if str(signed_transaction).find("raw_transaction") > 0:
                        tx_hash = web3_obj.eth.send_raw_transaction(signed_transaction.raw_transaction)
                    elif str(signed_transaction).find("signed_transaction") > 0:
                        tx_hash = web3_obj.eth.send_raw_transaction(signed_transaction.raw_transaction)
                    logger.info(f"交易已发送 tx_hash: {tx_hash.hex()}")
                    # 等待交易完成
                    receipt = web3_obj.eth.wait_for_transaction_receipt(tx_hash)
                    logger.debug(f"等待交易完成 receipt: {receipt}")
                    tx_bytes = f"0x{tx_hash.hex()}"
                    
                    if receipt['status'] == 1:
                        logger.success(f"交易成功 tx_hash: {tx_bytes}")
                        return True, {"tx_hash": tx_bytes}
                    else:
                        logger.error(f"交易失败 tx_hash: {tx_bytes}")
                        return False, {"tx_hash": tx_bytes}
                except ValueError as e:
                    logger.warning(f"Failed to transaction ValueError ETH : {str(e)}")
                    try:
                        if e.args[0].get('message') in 'intrinsic gas too low':
                            result = False, {"tx_hash": tx_bytes, "msg": e.args[0].get('message')}
                        else:
                            result = False, {"tx_hash": tx_bytes, "msg": e.args[0].get('message'), "code": e.args[0].get('code')}
                    except Exception as e:
                        result = False, {"tx_hash": tx_bytes, "msg": str(e)}
                    return result
            except Exception as e:
                error_msg = str(e)
                if "replacement transaction underpriced" in error_msg:
                    logger.warning(f"优先费不足，将增加... (尝试 {attempt+1})")
                elif "max fee per gas" in error_msg:
                    logger.warning(f"基础费不足，将更新... (尝试 {attempt+1})")
                elif "nonce too low" in error_msg:
                    logger.warning(f"Nonce 过低，将获取最新 nonce... (尝试 {attempt+1})")
                    # 获取最新 nonce 并更新交易
                    transaction['nonce'] = web3_obj.eth.get_transaction_count(transaction['from'], 'pending')
                else:
                    logger.error(f"Failed to send transaction: {e} (尝试 {attempt+1})")
                
                attempt += 1
                if attempt < max_retries:
                    logger.debug(f"Retrying in {retry_interval} seconds...")
                    time.sleep(retry_interval)
                else:
                    logger.error(f"Max retries reached. Failed to eth.send_raw_transaction: {str(e)}")
                    return False, {"tx_hash": "send_raw_transaction", "msg": str(e)}

    # --------------------------------------------------------------------------

    async def get_account_balances(self):
        try:
            # -------------------------------------------------------------------------- balance
            web3_obj = Web3(Web3.HTTPProvider(WEB3_RPC))
            # 连接rpc节点
            if not web3_obj.is_connected():
                logger.error(f"Unable to connect to the network: {WEB3_RPC}")
                if not WEB3_RPC_FIXED:
                    raise Exception("Web3 rpc not found")
                web3_obj = Web3(Web3.HTTPProvider(WEB3_RPC_FIXED))
                if not web3_obj.is_connected():
                    logger.error(f"Unable to connect to the network: {WEB3_RPC_FIXED}")
                    raise Exception("Failed to eth.is_connected.")
            
            current_timestamp = int(time.time())
            logger.debug(f"current_timestamp: {current_timestamp}")

            # 钱包地址
            check_address = Web3.to_checksum_address(self.client.address)
            logger.debug(f"check_address: {check_address}")
            
            # USDC 合约地址
            usdc_contract_address = Web3.to_checksum_address(CONTRACT_USDC)
            usdc_contract = web3_obj.eth.contract(address=usdc_contract_address, abi=contract_abi_usdc)
            
            # ETH 余额
            if self.client.type == 'wallet':
                eth_balance = web3_obj.eth.get_balance(check_address)
                eth_balance_fmt = web3_obj.from_wei(eth_balance, 'ether')
                logger.debug(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} balance: {eth_balance_fmt:.6f} ETH")
            else:
                eth_balance_fmt = 0
            # USDC 余额
            usdc_balance = usdc_contract.functions.balanceOf(check_address).call()
            usdc_balance_fmt = web3_obj.from_wei(usdc_balance, 'mwei')
            logger.debug(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} balance: {usdc_balance_fmt:.2f} USDC")

            logger.success(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} - Balance: {eth_balance_fmt:.6f} ETH / {usdc_balance_fmt:.2f} USDC")
            
            return eth_balance_fmt, usdc_balance_fmt
        except Exception as error:
            logger.error(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} get_account_balances except: {error}")
            return 0,0

    async def transfer_usdc_clicker(self, usd_amount: int) -> None:
        try:
            if len(WEB3_SENDER_PRIKEY) not in [64,66]:
                logger.debug(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} transfer_usdc_clicker ERROR: Incorrect private key")
                raise Exception(f"Incorrect private key")
            
            if usd_amount <= 0:
                logger.debug(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} transfer_usdc_clicker ERROR: eth_amount <= 0")
                raise Exception(f"eth_amount <= 0")
            # -------------------------------------------------------------------------- transfer
            web3_obj = Web3(Web3.HTTPProvider(WEB3_RPC))
            # 连接rpc节点
            if not web3_obj.is_connected():
                logger.error(f"Unable to connect to the network: {WEB3_RPC}")
                if not WEB3_RPC_FIXED:
                    raise Exception("Web3 rpc not found")
                web3_obj = Web3(Web3.HTTPProvider(WEB3_RPC_FIXED))
                if not web3_obj.is_connected():
                    logger.error(f"Unable to connect to the network: {WEB3_RPC_FIXED}")
                    raise Exception("Failed to eth.is_connected.")
            
            current_timestamp = int(time.time())
            logger.debug(f"current_timestamp: {current_timestamp}")

            # 钱包地址
            check_address = Web3.to_checksum_address(self.client.address)
            logger.debug(f"check_address: {check_address}")
            
            # 发送地址
            sender_address = web3_obj.eth.account.from_key(WEB3_SENDER_PRIKEY).address
            sender_balance_eth = web3_obj.eth.get_balance(sender_address)
            sender_balance_eth_fmt = web3_obj.from_wei(sender_balance_eth, 'ether')
            logger.debug(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} sender_address: {sender_address[:10]} balance: {sender_balance_eth_fmt} ETH")
            
            # USDC 合约地址
            usdc_address = Web3.to_checksum_address(CONTRACT_USDC)
            usdc_contract = web3_obj.eth.contract(address=usdc_address, abi=contract_abi_usdc)
            # USDC 发送地址余额
            sender_balance_usdc = usdc_contract.functions.balanceOf(sender_address).call()
            logger.debug(f"sender_balance_usdc: {sender_balance_usdc}")
            
            # USDC余额不足
            if usd_amount > sender_balance_usdc:
                # logger.error(f"Ooops! Insufficient USDC balance.")
                raise Exception("Insufficient USDC balance.")
            
            # 使用公共函数构建基础交易参数
            base_transaction = self.build_base_transaction(web3_obj, sender_address, WEB3_CHAINID)

            # 构建交易 - USDC转账
            transaction = usdc_contract.functions.transfer( check_address, usd_amount ).build_transaction(base_transaction)
            logger.debug(f"usdc.transfer transaction: {transaction}")

            # 发送交易
            tx_success, _ = self.send_transaction_with_retry(web3_obj, transaction, WEB3_SENDER_PRIKEY)
            if tx_success == False:
                logger.error(f"Ooops! Failed to send_transaction.")
            else:
                # logger.info(f"The usdc.transfer transaction send successfully! - transaction: {transaction}")
                logger.success(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} transfer successfully! - usd: {usd_amount/1000000:.1f}")
            return tx_success
        except Exception as error:
            logger.error(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} transfer_usdc_clicker except: {error}")
            return False

    async def transfer_eth_clicker(self, eth_amount: int) -> None:
        try:
            if len(WEB3_SENDER_PRIKEY) not in [64,66]:
                logger.debug(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} transfer_eth_clicker ERROR: Incorrect private key")
                raise Exception(f"Incorrect private key")
            
            if eth_amount <= 0:
                logger.debug(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} transfer_eth_clicker ERROR: eth_amount <= 0")
                raise Exception(f"eth_amount <= 0")
            # -------------------------------------------------------------------------- transfer
            web3_obj = Web3(Web3.HTTPProvider(WEB3_RPC))
            # 连接rpc节点
            if not web3_obj.is_connected():
                logger.error(f"Unable to connect to the network: {WEB3_RPC}")
                if not WEB3_RPC_FIXED:
                    raise Exception("Web3 rpc not found")
                web3_obj = Web3(Web3.HTTPProvider(WEB3_RPC_FIXED))
                if not web3_obj.is_connected():
                    logger.error(f"Unable to connect to the network: {WEB3_RPC_FIXED}")
                    raise Exception("Failed to eth.is_connected.")
            
            current_timestamp = int(time.time())
            logger.debug(f"current_timestamp: {current_timestamp}")

            # 钱包地址
            check_address = Web3.to_checksum_address(self.client.address)
            logger.debug(f"check_address: {check_address}")
            
            # 发送地址
            sender_address = web3_obj.eth.account.from_key(WEB3_SENDER_PRIKEY).address
            sender_balance_eth = web3_obj.eth.get_balance(sender_address)
            sender_balance_eth_fmt = web3_obj.from_wei(sender_balance_eth, 'ether')
            logger.debug(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} sender_address: {sender_address[:10]} balance: {sender_balance_eth_fmt} ETH")
            
            # USDC余额不足
            if eth_amount > sender_balance_eth:
                # logger.error(f"Ooops! Insufficient USDC balance.")
                raise Exception("Insufficient USDC balance.")
            
            # 使用公共函数构建基础交易参数
            base_transaction = self.build_base_transaction(web3_obj, sender_address, WEB3_CHAINID)

            # 构建交易 - ETH转账
            try:
                # 使用现代Web3.py语法进行ETH转账
                transaction = {
                    'to': check_address,
                    'value': eth_amount,
                    'gas': 21000,  # ETH转账的标准gas限制
                    **base_transaction
                }
                # 估算gas，确保交易能成功
                try:
                    estimated_gas = web3_obj.eth.estimate_gas(transaction)
                    transaction['gas'] = max(21000, int(estimated_gas * 1.2))  # 增加20%的缓冲
                    logger.debug(f"Estimated gas for ETH transfer: {estimated_gas}, using: {transaction['gas']}")
                except Exception as gas_error:
                    logger.warning(f"Could not estimate gas, using default. Error: {gas_error}")
                    transaction['gas'] = 25000  # 合理的默认值
            except Exception as build_error:
                logger.error(f"Failed to build ETH transaction: {build_error}")
                raise Exception(f"Failed to build ETH transaction: {build_error}")
            logger.debug(f"eth.transfer transaction: {transaction}")

            # 发送交易
            tx_success, _ = self.send_transaction_with_retry(web3_obj, transaction, WEB3_SENDER_PRIKEY)
            if tx_success == False:
                logger.error(f"Ooops! Failed to send_transaction.")
            else:
                # logger.info(f"The eth.transfer transaction send successfully! - transaction: {transaction}")
                logger.success(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} transfer successfully! - eth: {eth_amount/1000000000000000000:.3f}")
            return tx_success
        except Exception as error:
            logger.error(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} transfer_eth_clicker except: {error}")
            return False

    # --------------------------------------------------------------------------

    @helper
    async def daily_onchain_balance(self):
        try:
            address = self.client.address
            logger.info(f"id: {self.client.id} name: {self.client.name} address: {address}")
            # -------------------------------------------------------------------------- balance eth/usdc
            eth_balance,usdc_balance = await self.get_account_balances()
            logger.debug(f"eth_balance: {eth_balance}, usdc_balance: {usdc_balance}")

            return "SUCCESS"
        except Exception as error:
            logger.error(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} daily_onchain_balance except: {error}")
            return f"ERROR: {error}"

    @helper
    async def daily_onchain_listen(self):
        try:
            address = self.client.address
            address_link = f"<a href='{WEB3_EXPLORER}/address/{address}'>{address[:6]}***{address[-6:]}</a>"
            logger.info(f"id: {self.client.id} name: {self.client.name} address: {address}")
            # -------------------------------------------------------------------------- balance eth/usdc
            eth_balance,usdc_balance = await self.get_account_balances()
            # logger.debug(f"eth_balance: {eth_balance}, usdc_balance: {usdc_balance}")

            # -------------------------------------------------------------------------- email
            
            # -------------------------------------------------------------------------- transfer ETH
            client_eth = float(self.client.eth) if isinstance(self.client.eth, str) else self.client.eth
            client_ethmax = 0.05
            logger.debug(f"eth_balance: {eth_balance:.6f} client_eth: {client_eth} client_ethmax: {client_ethmax}")
            if eth_balance < client_eth:
                eth_balance_float = float(eth_balance) if isinstance(eth_balance, Decimal) else eth_balance
                logger.debug(f"eth_balance_float: {eth_balance_float}")
                eth_amount = int((client_ethmax - eth_balance_float) * 1000000000000000000)
                # eth_amount = int(0.05 * 1000000000000000000)
                logger.info(f"id: {self.client.id} name: {self.client.name} address: {address[:10]} eth_balance: {eth_balance} < {client_eth}, transfer eth: {eth_amount/1000000000000000000:.3f}")
                if eth_amount>0:
                    # 发送ETH
                    result = await self.transfer_eth_clicker(eth_amount)
                    if result:
                        # 发送邮件
                        send_mail(self.client.name, f"Name: {self.client.name}<br> Address: {address_link}<br> Balance: {eth_balance_float:.3f} < {client_eth} ETH<br> Transfer: {eth_amount/1000000000000000000:.3f} ETH")
                    else:
                        raise Exception("transfer_eth_clicker failed")
            
            # -------------------------------------------------------------------------- transfer USDC
            client_usdc = float(self.client.usdc) if isinstance(self.client.usdc, str) else self.client.usdc
            client_usdcmax = float(self.client.usdcmax) if isinstance(self.client.usdcmax, str) else self.client.usdcmax
            logger.debug(f"usdc_balance: {usdc_balance:.2f} client_usdc: {client_usdc} client_usdcmax: {client_usdcmax}")
            if usdc_balance < client_usdc:
                usdc_balance_float = float(usdc_balance) if isinstance(usdc_balance, Decimal) else usdc_balance
                logger.debug(f"usdc_balance_float: {usdc_balance_float}")
                usd_amount = int((client_usdcmax - usdc_balance_float) * 1000000)
                # usd_amount = int(client_usdcmax * 1000000)
                logger.info(f"id: {self.client.id} name: {self.client.name} address: {address[:10]} usdc_balance: {usdc_balance} < {client_usdc}, transfer usdc: {usd_amount/1000000:.1f}")
                if usd_amount>0:
                    # 发送USDC
                    result = await self.transfer_usdc_clicker(usd_amount)
                    if result:
                        # 发送邮件
                        send_mail(self.client.name, f"Name: {self.client.name}<br> Address: {address_link}<br> Balance: {usdc_balance_float:.1f} < {client_usdc} USDC<br> Transfer: {usd_amount/1000000:.1f} USDC")
                    else:
                        raise Exception("transfer_usdc_clicker failed")
            
            return "SUCCESS"
        except Exception as error:
            logger.error(f"id: {self.client.id} name: {self.client.name} address: {address[:10]} daily_onchain_listen except: {error}")
            return f"ERROR: {error}"

    @helper
    async def daily_clicker_alltask(self):
        try:
            return "SUCCESS"
        except Exception as error:
            logger.debug(f"id: {self.client.id} name: {self.client.name} address: {self.client.address[:10]} daily_clicker_alltask except: {error}")
            return f"ERROR: {error}"
