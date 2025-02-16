import datetime
import json
import secrets
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
import base64
from aiohttp import ClientSession
from typing import List

from integrations.integration_item import IntegrationItem
from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

CLIENT_ID = 'a504fe7c-139f-4c91-9924-85fb0372e6e0'
CLIENT_SECRET = '3223a737-792d-46f9-af33-b4c25323fe89'
REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'
SCOPE = "crm.objects.contacts.read crm.objects.contacts.write crm.schemas.contacts.read crm.schemas.contacts.write"
AUTHORIZATION_URL = f'https://app.hubspot.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fintegrations%2Fhubspot%2Foauth2callback&scope={SCOPE}'
TOKEN_URL = 'https://api.hubapi.com/oauth/v1/token'


async def authorize_hubspot(user_id, org_id):
    state = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    
    encoded_state = base64.urlsafe_b64encode(json.dumps(state).encode('utf-8')).decode('utf-8')
    authorization_url = f'{AUTHORIZATION_URL}&state={encoded_state}&scope={SCOPE}'
    
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', json.dumps(state), expire=600)
    
    return authorization_url

async def oauth2callback_hubspot(request: Request):
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error_description'))
    
    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode('utf-8'))
    
    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')
    
    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')
    
    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={
                'grant_type': 'authorization_code',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'redirect_uri': REDIRECT_URI,
                'code': code
            }
        )
        
        response_json = response.json()
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f'Failed to get access token: {response_json}')
        
        await delete_key_redis(f'hubspot_state:{org_id}:{user_id}')
        await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(response_json), expire=600)
        
        return HTMLResponse(content='<script>window.close()</script>', status_code=200)

async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='HubSpot credentials not found.')
    
    credentials = json.loads(credentials)
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')
    
    return credentials

def create_integration_item_metadata_object(response_json: dict, item_type: str, parent_id=None, parent_name=None) -> IntegrationItem:
    parent_id = None if parent_id is None else parent_id + '_Base'
    return IntegrationItem(
        id=response_json.get('id', None) + '_' + item_type,
        name=response_json.get('name', None),
        type=item_type,
        parent_id=parent_id,
        parent_path_or_name=parent_name,
    )

async def get_items_hubspot(credentials) -> List[IntegrationItem]:
    access_token = credentials.get("access_token")

    if not access_token:
        raise Exception("Missing HubSpot access token!")

    url = "https://api.hubapi.com/crm/v3/objects/contacts?properties=firstname,lastname,email,phone"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        async with ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                text = await response.text()
                print(f"HubSpot API Response: {text[:500]}...")  

                if response.status != 200:
                    raise Exception(f"Error fetching contacts ({response.status}): {text}")

                data = await response.json()
                contacts = data.get("results", [])

                formatted_contacts = [
                    create_integration_item_metadata_object(
                        response_json={
                            "id": contact.get("id", "Unknown"),
                            "name": contact.get("properties", {}).get("firstname", "Unnamed Contact"),
                        },
                        item_type="contact"
                    )
                    for contact in contacts
                ]

                print(f"Processed {len(formatted_contacts)} contacts from HubSpot")
                return formatted_contacts

    except Exception as e:
        print(f"HubSpot API Request Failed: {e}")
        raise Exception(f"Failed to connect to HubSpot: {e}")



