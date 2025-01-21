import requests
import base64
import json
import datetime
from decimal import Decimal
from signer.api_signer import sign
from secret_manager.gcp_secret_manager import access_secret

### FUNCTIONS
def broadcast_tx(path, access_token, signature, timestamp, request_body):

    try:
        resp_tx = requests.post(
            f"https://api.fordefi.com{path}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "x-signature": base64.b64encode(signature),
                "x-timestamp": timestamp.encode(),
            },
            data=request_body,
        )
        resp_tx.raise_for_status()
        return resp_tx

    except requests.exceptions.HTTPError as e:
        error_message = f"HTTP error occurred: {str(e)}"
        if resp_tx.text:
            try:
                error_detail = resp_tx.json()
                error_message += f"\nError details: {error_detail}"
            except json.JSONDecodeError:
                error_message += f"\nRaw response: {resp_tx.text}"
        raise RuntimeError(error_message)
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Network error occurred: {str(e)}")


def evm_tx_native(evm_chain, vault_id, destination, custom_note, value):

    value_in_wei = str(int(Decimal(value) * Decimal('1000000000000000000')))
    print(f"⚙️ Preparing tx for {value}!")

    """
    Native ETH or BNB transfer

    """

    request_json = {
        "signer_type": "api_signer",
        "vault_id": vault_id,
        "note": custom_note,
        "type": "evm_transaction",
        "details": {
            "type": "evm_transfer",
            "gas": {
                "type": "priority",
                "priority_level": "medium"
            },
            "to": destination,
            "asset_identifier": {
                "type": "evm",
                "details": {
                    "type": "native",
                    "chain": f"evm_{evm_chain}_mainnet"
                }
            },
            "value": {
                "type": "value",
                "value": value_in_wei
            }
        }
    }
    
    return request_json

### Core logic
def transfer_native_gcp(chain, vault_id, destination, value, note):
    """
    Execute a native token transfer (BNB/ETH) using Fordefi API
    
    Args:
        chain (str): Chain identifier (e.g., "bsc", "eth")
        vault_id (str): Fordefi vault ID
        destination (str): Destination wallet address
        value (str): Amount to transfer in native units (e.g., "0.0001")
        note (str): Transaction note
    
    Returns:
        dict: Response from the Fordefi API
    """
    # Set config
    GCP_PROJECT_ID = 'inspired-brand-447513-i8'
    FORDEFI_API_USER_TOKEN = 'USER_API_TOKEN'
    USER_API_TOKEN = access_secret(GCP_PROJECT_ID, FORDEFI_API_USER_TOKEN, 'latest')
    path = "/api/v1/transactions"

    # Building transaction
    request_json = evm_tx_native(
        evm_chain=chain,
        vault_id=vault_id,
        destination=destination,
        custom_note=note,
        value=value
    )
    request_body = json.dumps(request_json)
    timestamp = datetime.datetime.now().strftime("%s")
    payload = f"{path}|{timestamp}|{request_body}"

    # Sign transaction with API Signer
    signature = sign(payload=payload, project=GCP_PROJECT_ID)

    # Broadcast tx
    resp_tx = broadcast_tx(path, USER_API_TOKEN, signature, timestamp, request_body)
    return resp_tx.json()