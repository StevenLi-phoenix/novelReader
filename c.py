import random

import c

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
with open("ua.text", "r") as file:
    ua = file.read().split("\n")
ua = [i.split("|")[1] for i in ua if i]

baseurl = "https://www.69shu.pro"

def getRandomUA(referrer=c.baseurl):
    return {"User-Agent": random.choice(ua), "referer": referrer}

