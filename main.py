import json
import os
import threading
from typing import Literal

import fastapi
import requests
import uvicorn
from bs4 import BeautifulSoup as BS
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from openai import OpenAI
from pydub import AudioSegment

import c

client = OpenAI()
app = fastapi.FastAPI()


def createTTS(id: int, index: int, voice: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = "nova",
              model: Literal["tts-1", "tts-1-hd"] = "tts-1"):
    if index == 0:
        return
    print(f"Creating TTS for {id} {index}")
    if os.path.exists(f"book/{id}/{index}.mp3.lock"):
        return
    if os.path.exists(f"book/{id}/{index}.mp3"):
        return
    # touch the file
    with open(f"book/{id}/{index}.mp3.lock", "w") as file:
        file.write("Processing")
    if not os.path.exists(f"book/{id}"):
        showBook(id)
    if not os.path.exists(f"book/{id}/{index}"):
        showChapter(id, index)
    try:
        text = open(f"book/{id}/{index}.txt", "r").read()
        text = text.split("\n")
        cpart = 0
        AS = AudioSegment.empty()
        ii_start, ii_end = 0, 0
        while ii_end <= len(text):
            while len("\n".join(text[ii_start:ii_end + 1])) < 4096:
                ii_end += 1
                if ii_end >= len(text):
                    break
            # print(ii_start, ii_end, len(text), text[ii_start:ii_end])
            # print(len("\n".join(text[ii_start:ii_end])))
            response = client.audio.speech.create(model=model, voice=voice, input="\n".join(text[ii_start:ii_end]))
            response.stream_to_file(f"book/{id}/{index}.{cpart}.mp3")
            AS += AudioSegment.from_file(f"book/{id}/{index}.{cpart}.mp3")
            ii_start = ii_end
            cpart += 1
            if ii_end >= len(text):
                break
        AS.export(f"book/{id}/{index}.mp3", format="mp3")
        for i in range(cpart):
            if os.path.exists(f"book/{id}/{index}.{i}.mp3"):
                os.remove(f"book/{id}/{index}.{i}.mp3")
        print(f"Created TTS for {id} {index}")
    except Exception as e:
        print(f"Failed to create TTS for {id} {index}")
        raise e
    finally:
        os.remove(f"book/{id}/{index}.mp3.lock")
        print(f"Done TTS for {id} {index}")


def index_to_ii(catlog, index):
    for i, url in catlog:
        if index == int(url.split("/")[-1]):
            return i + 1
    return 0


def ii_to_index(catlog, ii):
    if ii <= 0:
        return 0
    if ii > len(catlog):
        return 0
    return int(catlog[ii - 1][1].split("/")[-1])


def autoindex(id, index):
    if not os.path.exists(f"book/{id}/catlog.json"):
        showBook(id)
    catlog = json.load(open(f"book/{id}/catlog.json"))
    if 0 < index < len(catlog):
        index = ii_to_index(catlog, index)
    if index < 0:
        index = 0
    if index_to_ii(catlog, index) == 0:  # means index is not in catlog
        showBook(id)
        if index_to_ii(catlog, index) == 0:  # after showBook, still not in catlog
            return 0
    return index


@app.get("/")
def index():
    return HTMLResponse(open("audio.html").read())


@app.get('/favicon.ico')
def favicon():
    return FileResponse("favicon.ico")


# sample.jpg, sample.mp3, sample.txt
@app.get("/sample/jpg")
def samplejpg():
    return FileResponse("sample.jpg", media_type="image/jpeg")


@app.get("/sample/mp3")
def samplemp3():
    return FileResponse("sample.mp3", media_type="audio/mpeg")


@app.get("/img/{id}")
def showBook(id: int):
    return FileResponse(f"book/{id}/cover.jpg")


@app.get("/tts/{id}/{index}")
def tts(id: int, index: int):
    index = autoindex(id, index)
    if index == 0:
        return HTTPException(status_code=400, detail="Bad Request")

    if os.path.exists(f"book/{id}/{index}.mp3.lock"):
        return HTTPException(status_code=503,
                             detail="Request already being processed")
    if os.path.exists(f"book/{id}/{index}.mp3"):
        return FileResponse(f"book/{id}/{index}.mp3")

    if not os.path.exists(f"book/{id}/{index}.txt"):
        showChapter(id, index)
    t = threading.Thread(target=createTTS, args=(id, index))
    t.start()
    return HTTPException(status_code=503,
                         detail="Request started being processed.")


@app.post("/tts/{id}/{index}")
def tts_push(id: int, index: int):
    index = autoindex(id, index)
    response = tts(id, index)
    if response.status_code != 200:
        return response
    return {"status": "ok"}


@app.get("/{id}")
def showBook(id: int):
    if os.path.exists(f"book/{id}/catlog.json"):
        return {"links": json.load(open(f"book/{id}/catlog.json"))}

    print(f"Getting {id}")
    os.makedirs(f"book/{id}", exist_ok=True)
    url = f"{c.baseurl}/book/{id}/"
    response = requests.get(url, headers=c.getRandomUA())
    open("tempbook.txt", "w").write(response.content.decode("gbk", errors="ignore"))
    soup = BS(response.content.decode("gbk", errors="ignore"), "html.parser")

    catalog = soup.find_all("div", class_="catalog")[1]
    links = catalog.find_all("a")

    # view point at bool/54583.htm
    # img = soup.find("div", class_="bookimg2")
    # print(img.content)
    # img = img.find("img")["src"]
    # headers = c.getRandomUA()
    # headers["referer"] = c.baseurl
    # img = requests.get(img, headers=headers)
    # with open(f"book/{id}.jpg", "wb") as file:
    #     file.write(img.content)

    imgurl = f"https://cdn.shucdn.com/files/article/image/{str(id)[:2]}/{id}/{id}s.jpg"
    img = requests.get(imgurl, headers=c.getRandomUA(c.baseurl))
    with open(f"book/{id}/cover.jpg", "wb") as file:
        file.write(img.content)

    links = list(enumerate(list(map(lambda x: x["href"], links))))
    json.dump(links, open(f"book/{id}/catlog.json", "w"))
    return {"links": links}


@app.get("/{id}/{index}")
def showChapter(id: int, index: int):
    if not os.path.exists(f"book/{id}/catlog.json"):
        showBook(id)
    catlog = json.load(open(f"book/{id}/catlog.json"))

    index = autoindex(id, index)
    if index == 0:
        return HTTPException(status_code=400, detail="Bad Request")

    if os.path.exists(f"book/{id}/{index}.txt"):
        ii = index_to_ii(catlog, index)
        lastindex = ii - 1 if ii - 1 >= 0 else None
        nextIndex = ii + 1 if ii + 1 < len(catlog) else None
        # print(f"Next: {nextIndex}, Current: {ii}, Last: {lastindex}")
        return {"textd": open(f"book/{id}/{index}.txt").read(), "lastI": lastindex, "nextI": nextIndex, "currentI": ii}

    print(f"Getting {id} {index}")
    url = f"{c.baseurl}/txt/{id}/{index}"
    response = requests.get(url, headers=c.getRandomUA())
    # open("tempchapter.txt", "w").write(response.content.decode("gbk", errors="ignore"))
    bso = BS(response.content.decode("gbk", errors="ignore"), "html.parser")
    context = bso.find("div", class_="txtnav")

    # print(f"Got {index}")
    context = context.text.replace(" ", "  ").replace("(本章完)", "").replace("\r", "").strip()
    context = context.split("\n")
    title = context[0]
    context.pop(1)
    context = "\n".join(context)
    os.makedirs(f"book/{id}/", exist_ok=True)
    with open(f"book/{id}/{index}.txt", "w", encoding="utf-8") as file:
        file.write(context)

    ii = index_to_ii(catlog, index)
    lastindex = ii - 1 if ii - 1 >= 0 else 0
    nextIndex = ii + 1 if ii + 1 < len(catlog) else 0
    # print(f"Next: {nextIndex}, Current: {ii}, Last: {lastindex}")
    return {"textd": context, "lastI": lastindex, "nextI": nextIndex, "currentI": ii}


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8001)
