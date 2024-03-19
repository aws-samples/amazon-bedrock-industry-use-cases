import os
import json
import logging

from typing import List, Annotated

from serpapi import GoogleSearch
from aws_lambda_powertools.event_handler.openapi.params import Query

logger = logging.getLogger()
logger.setLevel(logging.INFO)

API_KEY = os.environ.get('API_KEY')


def get_flights(
    departure_id: Annotated[str, Query(description="Parameter defines the departure airport code or location kgmid. An airport code is an uppercase 3-letter code. For example, CDG is Paris Charles de Gaulle Airport and AUS is Austin-Bergstrom International Airport.")], 
    arrival_id: Annotated[str, Query(description="Parameter defines the arrival airport code or location kgmid. An airport code is an uppercase 3-letter code. For example, CDG is Paris Charles de Gaulle Airport and AUS is Austin-Bergstrom International Airport.")], 
    outbound_date: Annotated[str, Query(description="Parameter defines the outbound date. The format is YYYY-MM-DD. e.g. 2024-02-08")], 
    return_date: Annotated[str, Query(description="Parameter defines the return date. The format is YYYY-MM-DD. e.g. 2024-02-08")],
) -> List[dict]:
    
    params = {
        "engine": "google_flights",
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "currency": "USD",
        "hl": "en",
        "api_key": API_KEY
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    if results.get('error'):
        output = results['error'] + "Ask the user for more information related to the context received about the function."
    elif results.get("best_flights"):
        output = results.get("best_flights")
    elif results.get("other_flights"):
        output = results.get("other_flights")
    else:
        output = results + "Unknown Error."
    return output


def get_hotels(
    q: Annotated[str, Query(description="Parameter defines the location. e.g. Bali Resorts")], 
    check_in_date: Annotated[str, Query(description="Parameter defines the check-in date. The format is YYYY-MM-DD. e.g. 2024-02-10")], 
    check_out_date: Annotated[str, Query(description="Parameter defines the check-out date. The format is YYYY-MM-DD. e.g. 2024-02-10")], 
    adults: Annotated[str, Query(description="Parameter defines the number of adults")] = "",
    country_search: Annotated[str, Query(description="Parameter defines the country to use for the Google Hotels search. It's a two-letter country code. (e.g., us for the United States, uk for United Kingdom, or fr for France) Head to the Google countries page for a full list of supported Google countries.")] = "us"
) -> List[dict]:
    
    params = {
      "engine": "google_hotels",
      "q": q,
      "check_in_date": check_in_date,
      "check_out_date": check_out_date,
      "adults": adults,
      "currency": "USD",
      "gl": country_search.lower(),
      "hl": "en",
      "api_key": API_KEY
    }
    
    search = GoogleSearch(params)
    results = search.get_dict()
    if results.get('error'):
        output = results['error'] + "Ask the user for more information related to the context received about the function."
    elif results.get("properties"):
        output = results.get("properties")[0:2] if len(results) > 2 else results.get("properties")
    else:
        output = results + "Unknown Error."
        
    return output


def lambda_handler(event, context):
    responses = []
    api_path = event['apiPath']
    logger.info('API Path')
    logger.info(api_path)
    
    if api_path == '/get_flights':
        parameters = event['parameters']
        departure_id = ""
        arrival_id = ""
        outbound_date = ""
        return_date = ""
        for parameter in parameters:
            if parameter["name"] == "departure_id":
                departure_id = parameter["value"]
            if parameter["name"] == "arrival_id":
                arrival_id = parameter["value"]
            if parameter["name"] == "outbound_date":
                outbound_date = parameter["value"]
            if parameter["name"] == "return_date":
                return_date = parameter["value"]
        body = get_flights(departure_id, arrival_id, outbound_date, return_date)
    elif api_path == '/get_hotels':
        parameters = event['parameters']
        q = ""
        check_in_date = ""
        check_out_date = ""
        adults = ""
        country_search = ""
        for parameter in parameters:
            if parameter["name"] == "location":
                q = parameter["value"]
            if parameter["name"] == "check_in_date":
                check_in_date = parameter["value"]
            if parameter["name"] == "check_out_date":
                check_out_date = parameter["value"]
            if parameter["name"] == "adults":
                adults = parameter["value"]
            if parameter["name"] == "country_search":
                country_search = parameter["value"]
        body = get_hotels(q, check_in_date, check_out_date, adults, country_search)
    else:
        body = {"{} is not a valid api, try another one.".format(api_path)}
        
    response_body = {
        'application/json': {
            'body': json.dumps(body)
        }
    }
    
    action_response = {
        'actionGroup': event['actionGroup'],
        'apiPath': event['apiPath'],
        'httpMethod': event['httpMethod'],
        'httpStatusCode': 200,
        'responseBody': response_body
    }
    
    responses.append(action_response)
    
    api_response = {
        'messageVersion': '1.0', 
        'response': action_response}
    
    return api_response