import sanic
from sanic import json
from sanic_ext import openapi, Extend
from pymongo import MongoClient
import requests
from dotenv import load_dotenv
from os import environ as env

load_dotenv()

db = MongoClient()["MeowerBots"]

app = sanic.Sanic("MeowerBots")
Extend(app)

resp = requests.post("https://meltauth.meltland.dev/login", json={
    "username": env["MEOWER_USERNAME"],
    "pswd": env["MEOWER_PASSWORD"]
})

if resp.status_code != 200:
    raise Exception("Failed to login to Meower")

token = resp.json()["payload"]["payload"]["token"]

def get_max_pages():
    return (db["bots"].count_documents({}) // 5) + 1

@app.get("/")
async def get_bots(request: sanic.request.Request):

    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1

    return json({
        "bots": list(db["bots"].find({}, skip=(page-1)*5, limit=5)),
        "page": page,
        "max_pages": get_max_pages()
    })

# noinspection PyShadowingNames
def check_key(name, key):

    resp = requests.get(f"https://api.meower.org/users/{name}/dm", headers={
        "token": token
    })
    if resp.status_code != 200:
        print(resp.text, resp.status_code)
        return False

    resp = resp.json()

    post = requests.get(f"https://api.meower.org/posts/{resp["_id"]}?autoget=1&page=1", headers={
        "token": token
    }).json()["autoget"][0]

    return post["p"] == key

# noinspection PyTestUnpassedFixture
@app.put("/bot/<name:str>")
@openapi.body({
    "body": {
        "type": "object",
        "properties": {
            "key": {
                "type": "string"
            },
            "library": {
                "type": "string"
            }
        },
        "required": ["key"]
    }
})
async def add_bot(request: sanic.request.Request, name: str):
    if db["bots"].find_one({"name": name}):
        return json({"error": "Bot already added"}, status=400)

    data = request.json

    if not check_key(name, data["key"]):
        return json({"error": "Verification failed"}, status=400)

    db["bots"].insert_one({
        "_id": name,
        "owner": None,
        "verified": False,
        "library": data.get("library", "Unknown"),
    })
    return json({"message": "Bot added"})


@app.delete("/bot/<name:str>")
async def remove_bot(request: sanic.request.Request, name: str):
    if not check_key(name, request.headers["key"]):
        return json({"error": "Verification failed"}, status=400)

    db["bots"].delete_one({
        "_id": name,
    })
    return json({"message": "Bot removed"})

@app.get("/bot/<name:str>")
async def get_bot(request: sanic.request.Request, name: str):

    return json({"bot": db["bots"].find_one({"name": name})})


# noinspection PyTestUnpassedFixture
@app.patch("/bot/<name:str>")
async def update_bot(request: sanic.request.Request, name: str):
    if not check_key(name, request.headers["key"]):
        return json({"error": "Verification failed"}, status=400)

    return 501

    data = request.json

    db["bots"].update_one({
        "_id": name,
    }, {
        "$set": data,
        "_id": name,
        "verified": False,
    })

    return json({"message": "Bot updated"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
