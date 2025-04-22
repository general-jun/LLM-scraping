## ✅ 프로젝트 개요
SAP 커뮤니티 사이트(Technology Q&A / Blog)에서 HTML 데이터를 수집(Scraping)하여 SAP HANA DB에 저장하는 Application<br>개발을 목표로 하고있으며 수집된 Article은 향후 Embedding처리에 활용할 예정입니다.


## 🔧 주요 구성 요소
| 요소 | 설명 |
|------|------|
| Flask | REST-API 서버 역할 |
| flask-restx | Swagger 문서 자동 생성 및 라우팅 지원 |
| BeautifulSoup | HTML 문서 파싱 |
| pandas | 수집한 데이터를 DataFrame으로 가공 |
| hana_ml | SAP HANA DB와 연결하여 테이블에 저장 |
| uuid / hashlib | ID 및 중복검사용 해시값 생성 |
| requests | 외부 HTML 페이지 요청 처리 |


## 🔑 스크래핑 대상
```python
_TARGET = {
    "QNA": "https://community.sap.com/t5/technology-q-a/qa-p/technology-questions",
    "BLOG": "https://community.sap.com/t5/technology-blogs-by-sap/bg-p/technology-blog-sap"
}
```
- URL 파라미터(urlCode)를 통해 대상 선택 (QNA 또는 BLOG)


## 🔍 주요 로직 흐름
### 1. 요청 수신
- `/api/scrap?urlCode=QNA`
- URL 파라미터(urlCode)에 따라 스크래핑 대상 분기

### 2. HTML 파싱
```python
bsContent = bs(response.text, 'html.parser')
articles = bsContent.select("article.custom-message-tile")
...
```
### 3. 항목별 데이터 추출
- 제목, 요약, 게시일, 작성자, 조회수, 댓글수 등
- 중복(Article) 검사를 위한 SHA256 해시값 변환 및 셋팅
- 고유ID값 설정을 위한 UUID 생성 및 셋팅

### 4. HANA 저장
```python
df = pd.DataFrame(columns=data["columns"], data=data["data"])
create_dataframe_from_pandas(connection_context=ccHana, pandas_df=df, table_name='KR_SAP_DEMO_LLM_SCRAPCHUNK')
...
```


## 📌 함수 요약
| 함수명 | 반환값 | 설명 |
|--------|------|----|
| `getTitleHash(title)` | str | Parameter 값을 Hash(SHA256) 값으로 변환 |
| `generateUuid()` | str |  UUID 생성 |
| `getInt(tag)` | str | Parameter 값을 숫자로 변환  |
| `isValidDate(value)` | bool | 날짜형식(yyyy-mm-dd) 및 날짜값 유효성 검사 |
| `parsingQnaArticle()` | dict | QNA Article Parsing 및 정리 |
| `parsingBlogArticle()` | dict | BLOG Article Parsing 및 정리 |
| `saveContent(data)` | None | Dataframe을 이용한 저장 처리 |


## ⚙️ Swagger 문서 경로
- 실행 후 접속: `http://localhost:5000/`
- Swagger UI 자동 생성됨: `/`


## 🚀 실행 방법
```bash
python service.py
```


## 🧪 테스트 예시
```http
GET http://localhost:5000/api/scrap?urlCode=BLOG
```


## 🧠 개선 예정 및 추가 개발 항목
### 1. 로직(Article 저장) 개선
- 내용<br>HANA_ml에서 제공하는 Dataframe을 이용하는 방식에서 hdbcli의 전통적인 SQL을 이용하는 방식으로 변경
- 변경사유<br>Dataframe을 이용하여 저장하는 것이 hdbcli를 사용하는 것보다 빠르나 현재 HDI Container에서는 제대로 동작하지 않는 문제 발생
- 검토사항<br>Article 저장 시 건별 저장이 아닌 일괄(Batch)저장 방식으로 처리가 가능한지 확인 필요 

### 2. 로직(Article 삭제 API) 구현 
```http
GET /api/purge?beforeDate=2024-12-31
```
- 매일 정기적으로 Scraping 시 QNA, BLOG 각각 50건씩 저장되며 하루 최대 1200건 적재되는 상태로 중복제거 로직 적용 전까지는 데이터 증가량이 큰 상태<br>
`POSTED_DATE`가 `beforeDate`보다 이전인 Article은 삭제 처리

### 3. 추가 개발
- Hash값을 이용하여 등록되어 있는 Article과 중복되는지 검사하여 중복 시 제거하는 기능 개발
- 사용자 요청 시 즉시 Scraping Trigger를 위한 API 개발<br>`JobScheduler와 중복수행되지 방지를 위해 수행상태 사전확인 필요` 
- JobScheduler의 수행상태 확인을 위한 API 개발<br>REST API Document: https://help.sap.com/docs/job-scheduling/sap-job-scheduling-service/retrieve-job-run-log-details?locale=en-US&mt=ko-KR


## 🧠 향후 검토
- 사이트별 Scrapper를 Module로 개발하여 다양한 Site를 대응하더라도 컨텐츠를 저장하는 SAP Community 컨텐츠 저장에 맞춰진 현재 테이블 구조로는 대응이 불가<br>컨텐츠를 JSON String으로 변환하여 단일컬럼에 저장하는 방식으로 검토
- 컨텐츠 저장방식 변경 시 UI에서 해당 데이터 조회 시 사용자가 알아보기 어렵다는 단점이 발생<br> Service Level에서 JSON String을 개별항목으로 분리하여 화면에 보여줄 수 있는 방안으로 CDS + Procedure 조합 또는 REST API로 구현 또는 별도 테이블 + Trigger 조합

## 📎 참고사항 - Job Scheduling Service 
- Dashboard: https://jobscheduler-dashboard.cfapps.ap12.hana.ondemand.com/manageinstances/b78ef70b-c7ea-45d5-b8b2-10f7a598f4d8
- Scraping 수행 설정: 1개의 Job과 2개의 Schedules로 구성
- 지정된 시간에 수행되는 Schedule<br>Daily scraping from Technology Q&A<br>Daily scraping from Technology Blogs by SAP
- 일회성으로 수행되는 Schedule<br>Immdiate scraping from Technology Q&A<br>Immdiate scraping from Technology Blogs by SAP


## 📎 참고사항 - Job 설정
| 함목명 | 설명 |
|--------|------|
| Name | scrapingArticle |
| Job Action | https://llm-scrap-service-delightful-koala-ly.cfapps.ap12.hana.ondemand.com/api/scrap |
| HTTP Method | GET |


 ## 📎 참고사항 - Schedules(Technology Q&A) 설정
| 항목명 | 설명 |
|--------|------|
| Description | Daily scraping from Technology Q&A |
| Pattern | Recurring - Cron |
| Value | * * * * * 0 0 |
| Data (JSON) | { "urlCode": "QNA" } |
| Description | Immdiate scraping from Technology Q&A |
| Pattern | One-time |
| Value | now |
| Data (JSON) | { "urlCode": "QNA" } |


## 📎 참고사항 - Schedules(Technology Blogs by SAP) 설정
| 항목명 | 설명 |
|--------|------|
| Descripton | Daily scraping from Technology Blogs by SAP |
| Pattern | Recurring - Cron |
| Value | * * * * * 30 0 |
| Data (JSON) | { "urlCode": "BLOG" } |
| Description | Immdiate scraping from Technology Blogs by SAP |
| Pattern | One-time |
| Value | now |
| Data (JSON) | { "urlCode": "BLOG" } |