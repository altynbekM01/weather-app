from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import httpx

from fastapi import Query
from fastapi.responses import JSONResponse
from urllib.parse import unquote, quote
from collections import defaultdict

city_stats = defaultdict(int)

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    last_city = request.cookies.get("last_city")
    history_cookie = request.cookies.get("history", "")
    history = unquote(history_cookie).split("|") if history_cookie else []

    weather_data = None

    if last_city:
        last_city = unquote(last_city)
        async with httpx.AsyncClient() as client:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={last_city}&count=1&language=ru"
            geo_response = await client.get(geo_url)
            geo_data = geo_response.json()

            results = geo_data.get("results")
            if results:
                latitude = results[0]["latitude"]
                longitude = results[0]["longitude"]

                weather_url = (
                    f"https://api.open-meteo.com/v1/forecast?"
                    f"latitude={latitude}&longitude={longitude}&current_weather=true"
                )
                weather_response = await client.get(weather_url)
                weather_data = weather_response.json().get("current_weather")

    return templates.TemplateResponse("index.html", {
        "request": request,
        "last_city": last_city,
        "history": history,
        "weather": weather_data,
        "city": last_city
    })


@app.get("/api/stats")
async def get_city_stats():
    return JSONResponse(dict(city_stats))

@app.post("/weather", response_class=HTMLResponse)
async def get_weather(request: Request, city: str = Form(...)):
    city = city.strip()
    city_stats[city] += 1
    history = request.cookies.get("history", "")
    history_list = history.split("|") if history else []
    if city not in history_list:
        history_list.append(city)
    new_history = "|".join(history_list)

    async with httpx.AsyncClient() as client:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=ru"
        geo_response = await client.get(geo_url)
        geo_data = geo_response.json()

        results = geo_data.get("results")
        if not results:
            response = templates.TemplateResponse("index.html", {
                "request": request,
                "error": "Город не найден",
                "last_city": city
            })
            response.set_cookie("history", quote(new_history))
            return response

        latitude = results[0]["latitude"]
        longitude = results[0]["longitude"]

        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={latitude}&longitude={longitude}&current_weather=true"
        )
        weather_response = await client.get(weather_url)
        weather_data = weather_response.json().get("current_weather")

    response = templates.TemplateResponse("index.html", {
        "request": request,
        "weather": weather_data,
        "city": city
    })
    response.set_cookie("last_city", quote(city))
    response.set_cookie("history", quote(new_history))
    return response



@app.get("/autocomplete")
async def autocomplete(query: str = Query(..., min_length=2)):
    async with httpx.AsyncClient() as client:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={query}&count=5&language=ru"
        geo_response = await client.get(geo_url)
        geo_data = geo_response.json()

    suggestions = [item["name"] for item in geo_data.get("results", [])]
    return JSONResponse(suggestions)