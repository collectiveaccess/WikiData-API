# WikiData API
API to connect with wikidata.org and wikibase

This repo uses:
- fastAPI to run an API
- WikiDataIntegration that uses PyWikibot to connect with wikidata.org and wikibase. WikiDataIntegration is a git submodule.


## Setup

1. Create [wikidata account](https://www.wikidata.org/w/index.php?title=Special:CreateAccount&returnto=Wikidata%3AMain+Page)

2. Create [wikidata bot account](https://www.wikidata.org/wiki/Special:BotPasswords)

3. install libraries

requires Python 3.6.8+

Optional: create a virtual environment called 'venv' using venv

```
python3 -m venv venv
source venv/bin/activate
```

install libraries

```bash
pip install -r requirements.txt
```


## Run the code

Start api

```
uvicorn main:app --reload
```
