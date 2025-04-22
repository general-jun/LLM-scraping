import os, logging, json, uuid, re, requests, hashlib
import pandas as pd
from datetime import datetime
from flask import Flask, request
from flask_restx import Api, Resource, Namespace, fields
from bs4 import BeautifulSoup as bs
from hana_ml.dataframe import ConnectionContext
from hana_ml.dataframe import create_dataframe_from_pandas

_TARGET = {
    "QNA": "https://community.sap.com/t5/technology-q-a/qa-p/technology-questions",
    "BLOG": "https://community.sap.com/t5/technology-blogs-by-sap/bg-p/technology-blog-sap"
}
_COLUMNS = [ "ID", "CHECKSUM", "TAG", "TITLE", "URL", "SUMMARY", "POSTED_DATE", "AUTHOR", "VIEWS", "COMMENTS", "EMBEDDED" ]

# 환경(LOG)정보 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# 실행환경(CF, Local)에 따라서 접속(HANA)정보 로드
if "VCAP_SERVICES" in os.environ:
    servicesInfo = json.loads(os.environ["VCAP_SERVICES"])
else:
    with open("vcap_services.json") as file:
        servicesInfo = json.load(file)

# HANA 접속
hanaCredentials = servicesInfo["hana"][0]["credentials"]
ccHana = ConnectionContext(
    address = hanaCredentials["host"],
    port = int(hanaCredentials["port"]),
    #user = hanaCredentials["hdi_user"],
    #password = hanaCredentials["hdi_password"],
    user="",
    password="",
    autocommit=True,
    encrypt=True,
    sslValidateCertificate=False
)

# App 초기화
app = Flask(__name__)
port = int(os.getenv("PORT", 5000))
# Flask-restx 설정
api = Api(app, version='0.1', title='Scraping API Document', description="API Documentation for Scraping", doc="/")
ns = api.namespace('api', description='Scraping Endpoints')

# UUID 생성
def generateUuid():
    return uuid.uuid4().hex

# 해쉬값 생성
def getTitleHash(data):
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

# 문자를 숫자로 변환
def getInt(tag):
    return int(tag.get_text(strip=True)) if tag else 0

# 날짜 유효성 검사
def isValidDate(value):
    if not value:
        return False    
    # 형식 및 유효값 검사
    pattern = r"^\d{4}-\d{2}-\d{2}$"
    if not re.match(pattern, value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False

# Technology Q&A의 Article을 추출하여 JSON 객체로 반환 
def parsingQnaArticle(artic을eList):
    result = {
        "ID": [],
        "CHECKSUM": [],
        "TAG": [],
        "TITLE": [],
        "URL": [],
        "SUMMARY": [],
        "POSTED_DATE": [],
        "AUTHOR": [],
        "VIEWS": [],
        "COMMENTS": [],
        "EMBEDDED": []
    }

    for article in articleList:
        titleTag = article.select_one("h3 > a")
        title = titleTag.get_text(strip=True) if titleTag else ""
        if not title:
            continue
        url = "https://community.sap.com" + titleTag["href"] if titleTag else ""
        summaryTag = article.select_one("footer p")
        summary = summaryTag.get_text(strip=True) if summaryTag else ""
        timeTag = article.select_one("time")
        postedDate = timeTag["datetime"] if timeTag and "datetime" in timeTag.attrs else ""
        authorTag = article.select_one("a.custom-tile-author-link[rel='author']")
        author = authorTag.get_text(strip=True) if authorTag else ""
        viewsTag = article.select_one("ul.custom-tile-statistics li.custom-tile-views b")
        views = getInt(viewsTag)
        commentsTag = article.select_one("ul.custom-tile-statistics li.custom-tile-replies b")
        comments = getInt(commentsTag)
        
        result["ID"].append(generateUuid())
        result["CHECKSUM"].append(getTitleHash(title))
        result["TAG"].append("QNA")
        result["TITLE"].append(title)
        result["URL"].append(url)
        result["SUMMARY"].append(summary)
        result["POSTED_DATE"].append(postedDate)
        result["AUTHOR"].append(author)
        result["VIEWS"].append(views)
        result["COMMENTS"].append(comments)
        result["EMBEDDED"].append(False)

    return {
        "columns": _COLUMNS,
        "data": result,
        "total": len(result["TITLE"])
    }

# Technology Blogs by SAP의 Article을 추출하여 JSON 객체로 반환 
def parsingBlogArticle(articles):
    result = {
        "ID": [],
        "CHECKSUM": [],
        "TAG": [],
        "TITLE": [],
        "URL": [],
        "SUMMARY": [],
        "POSTED_DATE": [],
        "AUTHOR": [],
        "VIEWS": [],
        "COMMENTS": [],
        "EMBEDDED": []
    }

    for article in articles:
        titleTag = article.select_one("h3 > a")
        title = titleTag.get_text(strip=True) if titleTag else ""
        if not title:
            continue
        url = "https://community.sap.com" + titleTag["href"] if titleTag else ""
        summaryTag = article.select_one("p")
        summary = summaryTag.get_text(strip=True) if summaryTag else ""
        timeTag = article.select_one("time")
        postedDate = timeTag["datetime"] if timeTag and "datetime" in timeTag.attrs else ""
        authorTag = article.select_one("footer .custom-tile-author-info a[rel='author']")
        author = authorTag.get_text(strip=True) if authorTag else ""
        viewsTag = article.select_one("li.custom-tile-views b")
        views = getInt(viewsTag)
        commentsTag = article.select_one("li.custom-tile-replies b")
        comments = getInt(commentsTag)

        result["ID"].append(generateUuid())
        result["CHECKSUM"].append(getTitleHash(title)),
        result["TAG"].append("BLOG")
        result["TITLE"].append(title)
        result["URL"].append(url)
        result["SUMMARY"].append(summary)
        result["POSTED_DATE"].append(postedDate)
        result["AUTHOR"].append(author)
        result["VIEWS"].append(views)
        result["COMMENTS"].append(comments),
        result["EMBEDDED"].append(False)

    return {
        "columns": _COLUMNS,
        "data": result,
        "total": len(result["TITLE"])
    }

# Article 저장
def saveContent(data):
    df = pd.DataFrame(columns=data["columns"], data=data["data"])
    create_dataframe_from_pandas(connection_context=ccHana, table_name='KR_SAP_DEMO_LLM_SCRAPCHUNK', pandas_df=df, append=True)
    logging.info(f"테이블(KR_SAP_DEMO_LLM_SCRAPCHUNK)에 {data['total']}건 저장되었습니다")

# 사이트(Technology Q&A / Technology Blogs by SAP) Scraping 처리
@ns.route("/scrap")
class processScrap(Resource):
    @ns.doc(params={ "urlCode": { "description": "파라미터 종류는 QNA, BLOG", "in": "query", "type": "string" }})
    @ns.doc(responses={ 200: 'Scraping Success' })
    @ns.doc(responses={ 500: 'Scraping Failed' })
    def get(self):
        urlCode = request.args.get("urlCode", default="QNA", type=str).upper()
        headers = { "User-Agent": "Chrome/135.0.0.0" }
        response = requests.get(_TARGET[urlCode], headers=headers)
        if response.status_code == 200:
            logging.debug(f"컨텐츠 정보: {response.text}")

            # Article Parsing
            bsContent = bs(response.text, 'html.parser')
            articles = bsContent.select("article.custom-message-tile")
            if urlCode == "QNA":
                data = parsingQnaArticle(articles)
            else:
                data = parsingBlogArticle(articles)
            # 컨텐츠 저장
            saveContent(data)
            return { "msg": f"{data['total']}건 처리되었습니다" }, 200
        else:
            return { "msg": "URL 접속 중 오류가 발생되었습니다" }, 500

# 오래된 Article 삭제 처리
@ns.route("/purge")
class processPurge(Resource):
    @ns.doc(params= { "beforeDate": { "description": "입력한 일자보다 Posting 일자가 이전인 Article 삭제", "in": "query", "type": "string" }})
    @ns.doc(responses={ 200: 'Purge Success' })
    @ns.doc(responses={ 500: 'Purge Failed' })
    def get(self):
        # 입력값 검사
        beforeDate = request.args.get("beforeDate", type="str")
        if isValidDate(beforeDate) == False:
            return { "msg": "날짜가 입력되지 않았거나 유효하지 않습니다" }, 500
        # 삭제 처리
        if None:
            return { f"Article {cnt}건 삭제되었습니다" }, 200
        else:
            return { "msg": "Article 삭제 중 오류가 발생했습니다" }, 500

# 서버 구동
if __name__ == "__main__":
	app.run(host="0.0.0.0", port=port, debug=True)