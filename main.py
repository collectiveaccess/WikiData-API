import re
import json

from dotenv import load_dotenv
load_dotenv()
import pywikibot
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import WikiDataIntegration as wd
from PyImporter import format_edit_mutation, api_edit

app = FastAPI()

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# need to set headers to ensure we are using utf-8
headers = {"Content-Type": "application/json;charset=UTF-8", "Charset": "utf-8"}


@app.get("/")
def read_root():
    content = {"message_1": "Hello", "message_2": "你好"}
    return JSONResponse(content=content, headers=headers)


@app.get("/wikidata_item/{item_id}")
def read_wikidata_item(item_id: str):
    # check for invalid item_id
    if not re.search(r"^Q[0-9]+$", item_id):
        raise HTTPException(status_code=404, detail="Item not found")

    site = pywikibot.Site("wikidata", "wikidata")
    repo = site.data_repository()
    item = pywikibot.ItemPage(repo, item_id)

    if item.exists():
        content = wd.format_display_item(item, site)
        try:
            json.dumps(content)
        except TypeError as err:
            content = {"error": err.args[0]}
    else:
        raise HTTPException(status_code=404, detail="Item not found")

    return JSONResponse(content=content, headers=headers)


@app.get("/search")
def read_search(keyword: str):
    site = pywikibot.Site("wikidata", "wikidata")
    if keyword:
        content = wd.search_keyword(site, keyword)
    else:
        content = []

    return JSONResponse(content=content, headers=headers)


@app.get("/get_menu_options")
def all_props_for_ids(ids):
    ids_list = ids.split("|")
    content = wd.fetch_and_format_menu_options(ids_list)

    return JSONResponse(content=content, headers=headers)


class WikidataId(BaseModel):
    qid: str
    ca_id: str
    table: str
    type: str


@app.post("/copy_wikidata_item")
def copy_wikidata_item(data: WikidataId):
    local_site = pywikibot.Site("en", "cawiki")
    site = pywikibot.Site("wikidata", "wikidata")

    # results['id'] is wikibase qid
    results = wd.import_wikidata_item_to_local_wikibase(data.qid, site, local_site)

    # save wikibase qid to CollectiveAccess record.
    if data.table == 'ca_entities':
        update_entity(data.table, results['id'], data.ca_id)
    elif data.table == 'ca_occurrences':
        update_occurrence(data.table, results['id'], data.ca_id)

    content = {
        "message": f"{results['label']} {results['id']} added to local Wikibase"
    }
    return JSONResponse(content=content, headers=headers)


def update_entity(table, qid, ca_id):
    bundles = f'{{name: "authority_wiki_data", value: "{qid}"}}'
    update_identifier_type = 'id'
    query = format_edit_mutation(table, ca_id, bundles, update_identifier_type)
    api_edit(query)


def update_occurrence(table, qid, ca_id):
    bundles = f'{{name: "authority_wiki_data", value: "{qid}"}}'
    update_identifier_type = 'id'
    query = format_edit_mutation(table, ca_id, bundles, update_identifier_type)
    api_edit(query)
