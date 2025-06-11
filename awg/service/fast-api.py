import os
import httpx
from typing import Dict, List
from pydantic import BaseModel
from settings import FAST_API_URL

class ClientInfo(BaseModel):
    public_key: str
    endpoint: str | None = None
    latest_handshake: str | None = None
    transfer: str | None = None

class ActiveClientsResponse(BaseModel):
    status: str
    clients: List[ClientInfo]

async def get_active_clients() -> Dict:
    """
    Fetches active clients data from the WireGuard server
    Returns the response as a dictionary
    """

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(FAST_API_URL + "/active_clients")
            response.raise_for_status()
            
            # Parse response into Pydantic model for validation
            data = response.json()
            validated_data = ActiveClientsResponse(**data)
            
            print(validated_data.dict())
            return validated_data.dict()
            
        except httpx.HTTPError as e:
            return {
                "status": "error",
                "message": f"Failed to fetch active clients: {str(e)}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}"
            }