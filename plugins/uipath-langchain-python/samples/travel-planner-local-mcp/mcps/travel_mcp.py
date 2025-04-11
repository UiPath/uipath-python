# demo.py
import json
from datetime import datetime

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("travel-planner-local-mcp")


@mcp.tool()
def get_weather(location: str):
    """Get the current weather for a specific location.

    Args:
        location: City name or common abbreviation

    Returns:
        Detailed weather information for the requested location
    """
    weather_data = {
        "san francisco": {
            "temp": "60°F",
            "condition": "Foggy",
            "humidity": "75%",
            "wind": "15 mph",
        },
        "sf": {
            "temp": "60°F",
            "condition": "Foggy",
            "humidity": "75%",
            "wind": "15 mph",
        },
        "new york": {
            "temp": "72°F",
            "condition": "Partly Cloudy",
            "humidity": "68%",
            "wind": "8 mph",
        },
        "nyc": {
            "temp": "72°F",
            "condition": "Partly Cloudy",
            "humidity": "68%",
            "wind": "8 mph",
        },
        "miami": {
            "temp": "88°F",
            "condition": "Sunny",
            "humidity": "80%",
            "wind": "10 mph",
        },
        "chicago": {
            "temp": "65°F",
            "condition": "Windy",
            "humidity": "60%",
            "wind": "25 mph",
        },
        "las vegas": {
            "temp": "95°F",
            "condition": "Clear",
            "humidity": "20%",
            "wind": "5 mph",
        },
        "seattle": {
            "temp": "55°F",
            "condition": "Rainy",
            "humidity": "85%",
            "wind": "12 mph",
        },
        # Adding ski resort destinations
        "aspen": {
            "temp": "28°F",
            "condition": "Snowy",
            "humidity": "65%",
            "wind": "12 mph",
            "snow_depth": "24 inches",
        },
        "vail": {
            "temp": "25°F",
            "condition": "Light Snow",
            "humidity": "70%",
            "wind": "8 mph",
            "snow_depth": "30 inches",
        },
        "park city": {
            "temp": "30°F",
            "condition": "Snowy",
            "humidity": "60%",
            "wind": "15 mph",
            "snow_depth": "22 inches",
        },
        "lake tahoe": {
            "temp": "32°F",
            "condition": "Heavy Snow",
            "humidity": "75%",
            "wind": "10 mph",
            "snow_depth": "28 inches",
        },
        "whistler": {
            "temp": "22°F",
            "condition": "Powder Snow",
            "humidity": "80%",
            "wind": "6 mph",
            "snow_depth": "35 inches",
        },
        "zermatt": {
            "temp": "20°F",
            "condition": "Fresh Powder",
            "humidity": "65%",
            "wind": "9 mph",
            "snow_depth": "40 inches",
        },
    }

    location = location.lower()
    if location in weather_data:
        data = weather_data[location]
        if "snow_depth" in data:
            return f"Current weather in {location.title()}: {data['temp']}, {data['condition']} with {data['humidity']} humidity and {data['wind']} winds. Current snow depth: {data['snow_depth']}."
        else:
            return f"Current weather in {location.title()}: {data['temp']}, {data['condition']} with {data['humidity']} humidity and {data['wind']} winds."
    else:
        return f"Weather data for {location} not available. Forecasting sunny and 75°F based on seasonal averages."


@mcp.tool()
def get_coolest_cities():
    """Get a list of cool cities to visit with descriptions of what makes them interesting.

    Returns:
        JSON formatted data about top travel destinations
    """
    cool_cities = [
        {
            "name": "New York City",
            "highlights": "Vibrant culture, Broadway shows, Central Park, world-class dining",
            "best_season": "Fall",
        },
        {
            "name": "San Francisco",
            "highlights": "Golden Gate Bridge, tech hub, diverse food scene, unique neighborhoods",
            "best_season": "Summer",
        },
        {
            "name": "Tokyo",
            "highlights": "Blend of traditional and ultramodern, amazing food, efficient transit",
            "best_season": "Spring",
        },
        {
            "name": "Paris",
            "highlights": "Art, architecture, romance, cuisine, fashion",
            "best_season": "Spring/Fall",
        },
        {
            "name": "Barcelona",
            "highlights": "Stunning architecture, beaches, tapas, vibrant nightlife",
            "best_season": "Spring/Fall",
        },
    ]
    return json.dumps(cool_cities, indent=2)


@mcp.tool()
def get_attractions(city: str):
    """Get top tourist attractions for a specific city.

    Args:
        city: Name of the city or ski resort area

    Returns:
        List of top attractions with brief descriptions
    """
    attractions_by_city = {
        "san francisco": [
            "Golden Gate Bridge - Iconic suspension bridge with fantastic views",
            "Alcatraz Island - Historic federal prison with audio tours",
            "Fisherman's Wharf - Popular waterfront with restaurants and sea lions",
            "Chinatown - Oldest and largest Chinatown outside of Asia",
            "Golden Gate Park - Large urban park with museums and gardens",
        ],
        "new york": [
            "Empire State Building - Iconic 102-story skyscraper with observation decks",
            "Statue of Liberty - Famous copper statue on Liberty Island",
            "Central Park - Massive urban park with various attractions",
            "Times Square - Vibrant intersection known for bright advertisements",
            "Metropolitan Museum of Art - One of the world's largest art museums",
        ],
        "london": [
            "Tower of London - Historic castle and former prison on the Thames",
            "British Museum - World-class collection of art and antiquities",
            "Buckingham Palace - Home of the British monarchy",
            "London Eye - Giant observation wheel with panoramic views",
            "Westminster Abbey - Gothic church and site of royal coronations",
        ],
        # Adding ski resort attractions
        "aspen": [
            "Aspen Mountain (Ajax) - Challenging terrain with breathtaking views of Aspen",
            "Snowmass - Family-friendly mountain with diverse terrain for all skill levels",
            "Aspen Art Museum - Contemporary art in a striking building designed by Shigeru Ban",
            "Wheeler Opera House - Historic venue offering performances and cultural events",
            "Maroon Bells - Iconic twin peaks offering spectacular photography opportunities",
        ],
        "vail": [
            "Back Bowls - Seven legendary powder bowls spanning over 3,000 acres",
            "Vail Village - Charming European-inspired pedestrian village with shops and dining",
            "Blue Sky Basin - Remote skiing experience with natural terrain features",
            "Betty Ford Alpine Gardens - Highest botanical garden in North America",
            "Colorado Ski & Snowboard Museum - Historical exhibits on ski culture and Winter Olympics",
        ],
        "park city": [
            "Park City Mountain Resort - Largest ski resort in the United States",
            "Main Street - Historic district with Victorian buildings, galleries and restaurants",
            "Utah Olympic Park - 2002 Winter Olympics venue with museum and activities",
            "Deer Valley Resort - Luxury ski-only resort with impeccable grooming",
            "High West Distillery - Award-winning distillery and restaurant in a historic building",
        ],
        "lake tahoe": [
            "Heavenly Mountain Resort - Panoramic lake views with skiing across California and Nevada",
            "Emerald Bay State Park - Stunning natural bay with Fannette Island and Vikingsholm",
            "Squaw Valley (Palisades Tahoe) - Olympic venue with challenging terrain",
            "Northstar California - Family-friendly resort with excellent tree skiing",
            "Lake Tahoe Gondola - Scenic ride offering spectacular views of the lake and mountains",
        ],
        "whistler": [
            "Peak 2 Peak Gondola - Record-breaking gondola connecting Whistler and Blackcomb mountains",
            "Whistler Village - Vibrant pedestrian village with shops, restaurants and nightlife",
            "Whistler Olympic Plaza - 2010 Winter Olympics venue with activities and events",
            "Audain Art Museum - Contemporary art museum featuring Indigenous works",
            "Vallea Lumina - Enchanting night walk through an illuminated forest",
        ],
        "zermatt": [
            "Matterhorn Glacier Paradise - Highest cable car station in Europe with glacier viewing",
            "Gornergrat Railway - Scenic mountain railway offering spectacular Matterhorn views",
            "Zermatt Village - Car-free alpine village with traditional chalets and luxury shops",
            "Matterhorn Museum - Underground museum showcasing Zermatt's mountaineering history",
            "Schwarzsee - Beautiful mountain lake reflecting the Matterhorn, accessible by gondola",
        ],
    }

    city = city.lower()
    if city in attractions_by_city:
        return attractions_by_city[city]
    else:
        return f"No attraction data available for {city}. Please check another popular destination like San Francisco, New York, London, or ski resorts like Aspen, Vail, Whistler, or Zermatt."


@mcp.tool()
def convert_currency(amount: float, from_currency: str, to_currency: str):
    """Convert an amount from one currency to another.

    Args:
        amount: The amount to convert
        from_currency: Source currency code (USD, EUR, GBP, JPY)
        to_currency: Target currency code (USD, EUR, GBP, JPY)

    Returns:
        Converted amount and current exchange rate
    """
    rates = {
        "usd": {"eur": 0.93, "gbp": 0.79, "jpy": 149.8, "usd": 1.0},
        "eur": {"usd": 1.08, "gbp": 0.85, "jpy": 161.5, "eur": 1.0},
        "gbp": {"usd": 1.27, "eur": 1.18, "jpy": 190.0, "gbp": 1.0},
        "jpy": {"usd": 0.0067, "eur": 0.0062, "gbp": 0.0053, "jpy": 1.0},
    }

    from_currency = from_currency.lower()
    to_currency = to_currency.lower()

    if from_currency in rates and to_currency in rates[from_currency]:
        rate = rates[from_currency][to_currency]
        converted = amount * rate
        return f"{amount} {from_currency.upper()} = {converted:.2f} {to_currency.upper()} (Rate: 1 {from_currency.upper()} = {rate} {to_currency.upper()}, as of {datetime.now().strftime('%Y-%m-%d')})"
    else:
        return f"Conversion from {from_currency.upper()} to {to_currency.upper()} is not supported."


@mcp.tool()
def get_ski_resorts(difficulty: str = "all"):
    """Get information about ski resorts based on difficulty level.

    Args:
        difficulty: Preferred difficulty level (beginner, intermediate, advanced, or all)

    Returns:
        JSON formatted data about top ski resorts
    """
    ski_resorts = [
        {
            "name": "Aspen Snowmass",
            "location": "Colorado, USA",
            "elevation": "12,510 ft",
            "trails": 362,
            "best_for": "intermediate to advanced",
            "season": "November to April",
            "highlights": "Four mountains with varied terrain, luxury amenities, vibrant après-ski scene",
        },
        {
            "name": "Whistler Blackcomb",
            "location": "British Columbia, Canada",
            "elevation": "7,494 ft",
            "trails": 200,
            "best_for": "all levels",
            "season": "November to May",
            "highlights": "Largest ski resort in North America, incredible backcountry, Olympic venue",
        },
        {
            "name": "Vail",
            "location": "Colorado, USA",
            "elevation": "11,570 ft",
            "trails": 195,
            "best_for": "intermediate to advanced",
            "season": "November to April",
            "highlights": "Back Bowls, European-style village, extensive groomed terrain",
        },
        {
            "name": "Park City Mountain",
            "location": "Utah, USA",
            "elevation": "10,026 ft",
            "trails": 348,
            "best_for": "all levels",
            "season": "November to April",
            "highlights": "Largest ski resort in USA, excellent snow quality, charming historic town",
        },
        {
            "name": "Heavenly",
            "location": "Lake Tahoe, California/Nevada, USA",
            "elevation": "10,067 ft",
            "trails": 97,
            "best_for": "intermediate",
            "season": "November to April",
            "highlights": "Stunning lake views, crosses state lines, vibrant casino nightlife",
        },
        {
            "name": "Zermatt",
            "location": "Switzerland",
            "elevation": "12,740 ft",
            "trails": 200,
            "best_for": "all levels",
            "season": "November to April",
            "highlights": "Matterhorn views, glacier skiing, car-free village, international cuisine",
        },
    ]

    if difficulty.lower() == "all":
        return json.dumps(ski_resorts, indent=2)
    else:
        filtered_resorts = [
            resort for resort in ski_resorts if difficulty.lower() in resort["best_for"]
        ]
        if filtered_resorts:
            return json.dumps(filtered_resorts, indent=2)
        else:
            return f"No resorts found for {difficulty} difficulty. Try 'beginner', 'intermediate', 'advanced', or 'all'."


if __name__ == "__main__":
    mcp.run(transport="stdio")
