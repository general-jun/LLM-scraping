# UUID 생성
def generateUuid() -> str:
    return uuid.uuid4().hex

# 해쉬값 생성
def getTitleHash(data) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

# 문자를 숫자로 변환
def getInt(tag) -> int:
    return int(tag.get_text(strip=True)) if tag else 0

# 날짜 유효성 검사
def isValidDate(value) -> bool:
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
