"""
Special authentication handling for Salesforce Streaming API (CometD).
JWT Bearer tokens don't work with Streaming API - we need Username-Password OAuth.
"""

import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


def get_streaming_token(instance_url: str, client_id: str, username: str, password: str) -> Optional[tuple[str, str]]:
    """
    Get OAuth token suitable for Streaming API using Username-Password flow.
    JWT Bearer tokens don't work with CometD - must use Username-Password OAuth.
    
    Args:
        instance_url: Salesforce instance URL (e.g., https://login.salesforce.com)
        client_id: Connected App Consumer Key
        username: Salesforce username
        password: Salesforce password + security token
        
    Returns:
        Tuple of (access_token, instance_url) or None
    """
    token_url = f"{instance_url}/services/oauth2/token"
    
    data = {
        'grant_type': 'password',
        'client_id': client_id,
        'username': username,
        'password': password
    }
    
    try:
        logger.info(f"Getting Streaming API token via Username-Password OAuth for {username}")
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        instance = token_data.get('instance_url')
        
        logger.info("✓ Successfully obtained Streaming API token")
        return (access_token, instance)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get Streaming API token: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                logger.error(f"Response: {e.response.json()}")
            except:
                logger.error(f"Response: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None


def get_soap_session_id(instance_url: str, username: str, password: str) -> Optional[tuple[str, str]]:
    """
    Get SOAP session ID for Streaming API using SOAP login.
    Alternative to OAuth when Connected App is not configured for Username-Password flow.
    
    Args:
        instance_url: Salesforce instance URL
        username: Salesforce username  
        password: Salesforce password + security token
        
    Returns:
        Tuple of (session_id, server_url) or None
    """
    soap_url = f"{instance_url}/services/Soap/u/57.0"
    
    soap_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                  xmlns:urn="urn:enterprise.soap.sforce.com">
    <soapenv:Body>
        <urn:login>
            <urn:username>{username}</urn:username>
            <urn:password>{password}</urn:password>
        </urn:login>
    </soapenv:Body>
</soapenv:Envelope>"""
    
    headers = {
        'Content-Type': 'text/xml; charset=UTF-8',
        'SOAPAction': 'login'
    }
    
    try:
        logger.info(f"Getting SOAP session ID for {username}")
        response = requests.post(soap_url, data=soap_envelope, headers=headers)
        response.raise_for_status()
        
        # Parse SOAP response
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.text)
        
        # Find sessionId and serverUrl
        ns = {'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
              'urn': 'urn:enterprise.soap.sforce.com'}
        
        session_id = root.find('.//urn:sessionId', ns)
        server_url = root.find('.//urn:serverUrl', ns)
        
        if session_id is not None and server_url is not None:
            sid = session_id.text
            url = server_url.text.split('/services')[0]  # Get base URL
            logger.info("✓ Successfully obtained SOAP session ID")
            return (sid, url)
        else:
            logger.error("Could not parse sessionId from SOAP response")
            return None
            
    except Exception as e:
        logger.error(f"SOAP login failed: {e}")
        return None
