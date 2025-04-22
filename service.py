import os, logging, json, uuid, re, requests, hashlib
import pandas as pd
from datetime import datetime
from importlib import import_module
from flask import Flask, request
from flask_restx import Api, Resource, Namespace, fields
from bs4 import BeautifulSoup as bs
from hana_ml.dataframe import ConnectionContext
from hana_ml.dataframe import create_dataframe_from_pandas
from lib.util import generateUuid, getTitleHash, getInt, isValidDate

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

# Technology Q&A의 Article을 추출하여 JSON 객체로 반환
# 추출 대상: 코멘트가 1건 이상이고 문제가 해결된 건 
def parsingQnaArticle(articleList) -> dict:
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
        "IS_SOLVED": []
    }

    try:
        for article in articleList:
            titleTag = article.select_one("h3 > a")
            title = titleTag.get_text(strip=True)
            url = "https://community.sap.com" + titleTag["href"]
            summaryTag = article.select_one("footer p")
            summary = summaryTag.get_text(strip=True)
            timeTag = article.select_one("time")
            postedDate = timeTag["datetime"]
            authorTag = article.select_one("a.custom-tile-author-link[rel='author']")
            author = authorTag.get_text(strip=True)
            viewsTag = article.select_one("ul.custom-tile-statistics li.custom-tile-views b")
            views = getInt(viewsTag)
            commentsTag = article.select_one("ul.custom-tile-statistics li.custom-tile-replies b")
            comments = getInt(commentsTag)
            classNames = article.get("class", [])
            isSolved = "custom-thread-solved" in classNames
            if not isSolved and comments == 0:
                continue            
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
            result["IS_SOLVED"].append(True)
        return {
            "columns": _COLUMNS,
            "data": result,
            "total": len(result["TITLE"])
        }
    except Exception as e:
        logging.error(f"Q&A Article Parsing 중 오류 발생: {str(e)}")
        raise


# Technology Blogs by SAP의 Article을 추출하여 JSON 객체로 반환
# 추출 대상: 전체
def parsingBlogArticle(articles) -> dict:
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
    
    try:
        for article in articles:
            titleTag = article.select_one("h3 > a")
            title = titleTag.get_text(strip=True)
            url = "https://community.sap.com" + titleTag["href"]
            summaryTag = article.select_one("p")
            summary = summaryTag.get_text(strip=True)
            timeTag = article.select_one("time")
            postedDate = timeTag["datetime"]
            authorTag = article.select_one("footer .custom-tile-author-info a[rel='author']")
            author = authorTag.get_text(strip=True)
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
            result["COMMENTS"].append(comments)
        return {
            "columns": _COLUMNS,
            "data": result,
            "total": len(result["TITLE"])
        }
    except Exception as e:
        logging.error(f"Blog Article Parsing 중 오류 발생: {str(e)}")
        raise

# Scrapper Module을 로딩하여 반환
def loadScrapper(scrapType):
    try:
        modulePath = f"scrapper.{scrapType.lower()}"
        return scrapperModule
    except:
        raise ValueError(f"Scrapper module이 없거나 scrapType이 유효하지 않습니다")

# Article 저장
def saveContent(data) -> None:
    try:
        df = pd.DataFrame(columns=data["columns"], data=data["data"])
        create_dataframe_from_pandas(connection_context=ccHana, table_name='KR_SAP_DEMO_LLM_SCRAPCHUNK', pandas_df=df, append=True)
        logging.info(f"테이블(KR_SAP_DEMO_LLM_SCRAPCHUNK)에 {data['total']}건 저장되었습니다")
    except Exception as e:
        logging.error(f"Article 저장 중 오류발생: {str(e)}")
        raise

# 사이트(Technology Q&A / Technology Blogs by SAP) Scraping 처리
@ns.route("/scrap")
class processScrap(Resource):
    @ns.doc(params={ "urlCode": { "description": "파라미터 종류는 QNA, BLOG", "in": "query", "type": "string" }})
    @ns.doc(responses={ 200: 'Scraping Success' })
    @ns.doc(responses={ 500: 'Scraping Failed' })
    def get(self):
        urlCode = request.args.get("urlCode", default="QNA", type=str).upper()
        headers = { "User-Agent": "Chrome/135.0.0.0" }
        
        try:
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
                # 컨텐츠 저장 후 DB Connection 닫기
                saveContent(data)
                ccHana.close()
                return { "msg": f"{data['total']}건 처리되었습니다" }, 200
        except RequestException as re:
            logging.error(f"URL 요청 중 오류 발생: {str(re)}")
            return { "msg": "URL 요청 중 오류가 발생되었습니다" }, 500 
        except Exception as e:
            logging.error(f"Article Parsing 중 오류 발생: {str(e)}")
            return { "msg": "Article Parsing 중 오류가 발생되었습니다" }, 500

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
            return { "msg": f"Article {cnt}건 삭제되었습니다" }, 200
        else:
            return { "msg": "Article 삭제 중 오류가 발생했습니다" }, 500

# 서버 구동
if __name__ == "__main__":
	app.run(host="0.0.0.0", port=port, debug=True)