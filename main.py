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
    wd.login(local_site)
    wd.login(site)

    # results['id'] is wikibase qid
    results = wd.import_wikidata_item_to_local_wikibase(data.qid, site, local_site)
    update_ca_record_local_wiki_qid(data.table, results["id"], data.ca_id)

    content = {"message": f"{results['label']} {results['id']} added to local Wikibase"}
    return JSONResponse(content=content, headers=headers)


def update_ca_record_local_wiki_qid(table, qid, ca_id):
    """save wikibase qid to CollectiveAccess record."""
    bundles = f'{{name: "authority_wiki_data", value: "{qid}", replace: true}}'
    update_ca_record(table, ca_id, bundles)


def update_ca_record_wikidata_qid(table, qid, ca_id):
    """save wikidata qid to CollectiveAccess record."""
    bundles = f'{{name: "authority_wikipedia", value: "{qid}", replace: true}}'
    update_ca_record(table, ca_id, bundles)


def update_ca_record(table, ca_id, bundles):
    update_identifier_type = "id"
    query = format_edit_mutation(table, ca_id, bundles, update_identifier_type)
    api_edit(query)


class WikiItem(BaseModel):
    data: dict
    wiki_instance: str
    ca_id: str
    table: str
    type: str


@app.post("/create_wiki_item")
def create_wiki_item(data: WikiItem):
    errors = []
    item_changed = 0
    if data.wiki_instance == "wikidata":
        site = pywikibot.Site("wikidata", "wikidata")
    else:
        pywikibot.config.put_throttle = 2
        site = pywikibot.Site("en", "cawiki")
    wd.login(site)
    wikidata_repo = pywikibot.Site("wikidata", "wikidata").data_repository()

    # create item
    try:
        itemData = format_item_data(data)
        item = wd.create_item(site, itemData)
        item_changed = 1
    except ValueError as err:
        errors.append(str(err))
    except:
        errors.append(f'Item for "{data.data["labels"]["en"]}" not created.')

    if item_changed > 0:
        # add wiki id to CollectiveAccess record
        if data.wiki_instance == "wikidata":
            update_ca_record_wikidata_qid(data.table, item.id, data.ca_id)
        else:
            update_ca_record_local_wiki_qid(data.table, item.id, data.ca_id)

        # add statements to wiki item
        create_item_statements(item, wikidata_repo, data.wiki_instance, data, errors)

    return JSONResponse(
        content={"changed": item_changed, "warnings": [], "errors": errors},
        headers=headers,
    )


def format_item_data(data):
    itemData = {
        "labels": data.data["labels"],
    }
    if "descriptions" in data.data:
        itemData["descriptions"] = data.data["descriptions"]
    if "aliases" in data.data:
        itemData["aliases"] = data.data["aliases"]

    return itemData


def create_item_statements(item, wikidata_repo, wiki_instance, data, errors):
    for statement in data.data["statements"]:
        if statement["data_type"] == "wikibase-item":
            qid = statement["data_value"]["value"]["id"]
            claim_value = get_claim_item(wiki_instance, qid)
            pid = statement["property"]
            try:
                # NOTE: must use wikidata_repo for federated claims
                statement = wd.add_claim(wikidata_repo, item, pid, claim_value)
                # TODO: add references
                # wd.add_reference(repo, statement, 'P?', "https://example.com")
            except:
                errors.append(
                    f'Statement for "{data["labels"]["en"]}" "{pid}" not created.'
                )
        else:
            errors.append(f"{statement['data_type']} not implemented.")


def get_claim_item(wiki_instance, qid):
    # get exisiting item from wikidata
    if wiki_instance == "wikidata":
        site = pywikibot.Site("wikidata", "wikidata")
        repo = site.data_repository()
        return pywikibot.ItemPage(repo, qid)
    # copy wikidata item to local wikibase
    else:
        local_site = pywikibot.Site("en", "cawiki")
        site = pywikibot.Site("wikidata", "wikidata")
        results = wd.import_wikidata_item_to_local_wikibase(qid, site, local_site)
        return results["item"]
