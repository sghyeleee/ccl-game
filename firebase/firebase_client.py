"""Firebase REST API 클라이언트.

firebase-admin SDK 대신 REST API를 사용하여 Firestore에 접근합니다.
이 방식은 서비스 계정 키(firebase_key.json) 없이 동작합니다.
"""

from __future__ import annotations

import urllib.request
import urllib.error
import urllib.parse
import json
from typing import Any, Dict, List, Optional

from firebase.config import API_KEY, FIRESTORE_BASE_URL


def _make_request(
    method: str,
    url: str,
    data: Optional[Dict[str, Any]] = None,
    timeout: float = 10.0,
    silent_404: bool = False
) -> Optional[Dict[str, Any]]:
    """HTTP 요청을 수행한다.
    
    Args:
        method: HTTP 메서드 (GET, POST, PATCH, DELETE)
        url: 요청 URL
        data: 요청 바디 (JSON)
        timeout: 타임아웃 (초)
        silent_404: True면 404 에러를 조용히 처리 (문서 없음은 정상 상황)
        
    Returns:
        응답 JSON 또는 None (실패 시)
    """
    try:
        headers = {"Content-Type": "application/json"}
        body = json.dumps(data).encode("utf-8") if data else None
        
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 404는 문서가 없는 정상 상황일 수 있음
        if e.code == 404 and silent_404:
            return None
        print(f"[DEBUG] HTTP Error {e.code}: {e.reason}")
        return None
    except urllib.error.URLError as e:
        print(f"[DEBUG] URL Error: {e.reason}")
        return None
    except Exception as e:
        print(f"[DEBUG] Request Error: {e}")
        return None


def get_document(collection: str, document_id: str) -> Optional[Dict[str, Any]]:
    """Firestore 문서를 조회한다.
    
    Args:
        collection: 컬렉션 이름
        document_id: 문서 ID
        
    Returns:
        문서 데이터 또는 None (문서가 없는 경우도 None)
    """
    # 한글 등 비ASCII 문자를 URL 인코딩
    encoded_doc_id = urllib.parse.quote(document_id, safe='')
    url = f"{FIRESTORE_BASE_URL}/{collection}/{encoded_doc_id}?key={API_KEY}"
    result = _make_request("GET", url, silent_404=True)
    
    if result and "fields" in result:
        return _parse_firestore_fields(result["fields"])
    return None


def set_document(collection: str, document_id: str, data: Dict[str, Any]) -> bool:
    """Firestore 문서를 생성/갱신한다.
    
    Args:
        collection: 컬렉션 이름
        document_id: 문서 ID
        data: 저장할 데이터
        
    Returns:
        성공 여부
    """
    # 한글 등 비ASCII 문자를 URL 인코딩
    encoded_doc_id = urllib.parse.quote(document_id, safe='')
    url = f"{FIRESTORE_BASE_URL}/{collection}/{encoded_doc_id}?key={API_KEY}"
    firestore_data = {"fields": _convert_to_firestore_fields(data)}
    
    result = _make_request("PATCH", url, firestore_data)
    return result is not None


def query_collection(
    collection: str,
    order_by: Optional[str] = None,
    descending: bool = False,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Firestore 컬렉션을 쿼리한다.
    
    Args:
        collection: 컬렉션 이름
        order_by: 정렬 필드
        descending: 내림차순 여부
        limit: 최대 결과 수
        
    Returns:
        문서 리스트
    """
    # Firestore REST API의 runQuery 사용
    url = f"{FIRESTORE_BASE_URL}:runQuery?key={API_KEY}"
    
    query: Dict[str, Any] = {
        "structuredQuery": {
            "from": [{"collectionId": collection}],
            "limit": limit,
        }
    }
    
    if order_by:
        query["structuredQuery"]["orderBy"] = [{
            "field": {"fieldPath": order_by},
            "direction": "DESCENDING" if descending else "ASCENDING"
        }]
    
    result = _make_request("POST", url, query)
    
    if not result:
        return []
    
    documents = []
    # runQuery 결과는 리스트 형태로 반환됨
    if isinstance(result, list):
        for item in result:
            if "document" in item and "fields" in item["document"]:
                doc_data = _parse_firestore_fields(item["document"]["fields"])
                documents.append(doc_data)
    
    return documents


def _convert_to_firestore_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Python dict를 Firestore 필드 형식으로 변환한다."""
    fields = {}
    for key, value in data.items():
        if isinstance(value, str):
            fields[key] = {"stringValue": value}
        elif isinstance(value, int):
            fields[key] = {"integerValue": str(value)}
        elif isinstance(value, float):
            fields[key] = {"doubleValue": value}
        elif isinstance(value, bool):
            fields[key] = {"booleanValue": value}
        elif value is None:
            fields[key] = {"nullValue": None}
        else:
            # 기타 타입은 문자열로 변환
            fields[key] = {"stringValue": str(value)}
    return fields


def _parse_firestore_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Firestore 필드 형식을 Python dict로 변환한다."""
    data = {}
    for key, value in fields.items():
        if "stringValue" in value:
            data[key] = value["stringValue"]
        elif "integerValue" in value:
            data[key] = int(value["integerValue"])
        elif "doubleValue" in value:
            data[key] = float(value["doubleValue"])
        elif "booleanValue" in value:
            data[key] = value["booleanValue"]
        elif "nullValue" in value:
            data[key] = None
        elif "timestampValue" in value:
            data[key] = value["timestampValue"]
        else:
            data[key] = str(value)
    return data
