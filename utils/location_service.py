
import requests
from flask import request
import logging

def get_client_ip():
    """Get client IP from request"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr

def get_location_from_ip(ip):
    """Get location information from IP using ip-api.com"""
    try:
        response = requests.get(f'http://ip-api.com/json/{ip}')
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'success':
                return {
                    'city': data.get('city'),
                    'country': data.get('country'),
                    'latitude': data.get('lat'),
                    'longitude': data.get('lon'),
                    'region': data.get('regionName')
                }
    except Exception as e:
        logging.error(f"Error getting location from IP: {e}")
    return None
