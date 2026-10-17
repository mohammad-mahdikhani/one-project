"""اتصال مستقیم به سامانه مودیان، مسیر self-tsp."""

from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PROD_BASE = "https://tp.tax.gov.ir/req/api/self-tsp"
SANDBOX_BASE = "https://sandboxrc.tax.gov.ir/req/api/self-tsp"

_MUL = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_PERM = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


class MoadianError(Exception):
    pass


def verhoeff_valid(number: str) -> bool:
    check = 0
    length = len(number)
    for index in range(length):
        digit = int(number[length - index - 1])
        check = _MUL[check][_PERM[index % 8][digit]]
    return check == 0


def verhoeff_check(number: str) -> str:
    check = 0
    length = len(number)
    for index in range(length):
        digit = int(number[length - index - 1])
        check = _MUL[check][_PERM[(index + 1) % 8][digit]]
    return str(_INV[check])


def fiscal_to_number(fiscal_id: str) -> str:
    result = []
    for char in fiscal_id:
        if char.isdigit():
            result.append(char)
        else:
            result.append(str(ord(char)))
    return "".join(result)


def generate_tax_id(fiscal_id: str, when: datetime, serial: int) -> str:
    # روز صورتحساب همان تاریخ محلی است. تبدیل به UTC حوالی نیمه‌شب روز را عوض می‌کند.
    days = (when.date() - datetime(1970, 1, 1).date()).days
    hex_days = f"{days:05X}"
    hex_serial = f"{int(serial):010X}"
    decimal = fiscal_to_number(fiscal_id) + f"{days:06d}" + f"{int(serial):012d}"
    return f"{fiscal_id}{hex_days}{hex_serial}{verhoeff_check(decimal)}".upper()


def invoice_serial_hex(serial: int) -> str:
    return f"{int(serial):010X}"


def _flatten(value, prefix=""):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            out.update(_flatten(item, f"{prefix}{key}."))
        return out
    if isinstance(value, list):
        out = {}
        for index, item in enumerate(value):
            out.update(_flatten(item, f"{prefix}{index}."))
        return out
    return {prefix[:-1]: value}


def _value_text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "#"
    if isinstance(value, str):
        if value.strip() == "":
            return "#"
        return value.replace("#", "##")
    if isinstance(value, list):
        return ""
    return str(value)


def normalize_json(data: dict, extra: dict | None = None) -> str:
    merged = dict(data)
    if extra:
        merged.update(extra)
    flat = _flatten(merged)
    ordered = json.loads(json.dumps(flat, sort_keys=True, default=str))
    return "#".join(_value_text(item) for item in ordered.values())


def sign_text(text: str, private_pem: str) -> str:
    key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    signature = key.sign(text.encode(), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode()


def _xor_blocks(data: bytes, key: bytes) -> bytes:
    mixed = bytearray(data)
    for index, byte in enumerate(data):
        mixed[index] = byte ^ key[index % len(key)]
    end = len(mixed)
    while end > 0 and mixed[end - 1] == 0:
        end -= 1
    return bytes(mixed[:end])


def encrypt_invoice(invoice: dict, public_key_body: str) -> tuple[str, str, str]:
    raw_key = os.urandom(32)
    iv = os.urandom(16)
    key_hex = raw_key.hex()
    payload = json.dumps(invoice).encode("utf-8")
    encrypted = AESGCM(raw_key).encrypt(iv, _xor_blocks(payload, raw_key), None)
    body = public_key_body.replace("-----BEGIN PUBLIC KEY-----", "").replace("-----END PUBLIC KEY-----", "").strip()
    pem = "-----BEGIN PUBLIC KEY-----\n" + body + "\n-----END PUBLIC KEY-----"
    public_key = serialization.load_pem_public_key(pem.encode())
    wrapped = public_key.encrypt(
        key_hex.encode(),
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    return base64.b64encode(encrypted).decode(), base64.b64encode(wrapped).decode(), iv.hex()


def packet(packet_type: str, fiscal_id: str, data=None) -> dict:
    return {
        "uid": str(uuid.uuid4()),
        "packetType": packet_type,
        "retry": False,
        "data": data,
        "encryptionKeyId": None,
        "symmetricKey": None,
        "iv": None,
        "fiscalId": fiscal_id,
        "dataSignature": None,
    }


class Client:
    def __init__(self, fiscal_id: str, private_key: str, sandbox: bool, http_request):
        self.fiscal_id = fiscal_id
        self.private_key = private_key
        self.base = SANDBOX_BASE if sandbox else PROD_BASE
        self.http = http_request

    def _post(self, path: str, body: dict, headers: dict):
        status, response = self.http("POST", self.base + path, payload=body, headers=headers, timeout=25)
        if not isinstance(response, dict):
            raise MoadianError("سامانه مودیان پاسخ قابل خواندن نداد")
        if status >= 400:
            detail = response.get("error") or response.get("message") or response.get("raw") or f"HTTP {status}"
            raise MoadianError(str(detail)[:240])
        return response

    def _headers(self) -> dict:
        return {
            "timestamp": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
            "requestTraceId": str(uuid.uuid4()),
        }

    def _signed(self, path: str, body_key: str, item: dict, token: str | None = None):
        headers = self._headers()
        sign_headers = dict(headers)
        if token:
            sign_headers["Authorization"] = token
            headers["Authorization"] = "Bearer " + token
        body = {"time": 1, body_key: item, "signature": ""}
        signed = item if body_key == "packet" else {"packets": item}
        body["signature"] = sign_text(normalize_json(signed, sign_headers), self.private_key)
        return self._post(path, body, headers)

    def _open(self, path: str, item: dict):
        body = {"time": 1, "packet": item, "signature": ""}
        return self._post(path, body, self._headers())

    def server_information(self) -> dict:
        item = packet("GET_SERVER_INFORMATION", self.fiscal_id)
        return self._open("/sync/GET_SERVER_INFORMATION", item)

    def public_key(self) -> tuple[str, str]:
        info = self.server_information()
        data = ((info.get("result") or {}).get("data") or {})
        keys = data.get("publicKeys") or []
        if not keys:
            raise MoadianError("کلید عمومی سازمان از سامانه مودیان نیامد")
        return str(keys[0].get("id") or ""), str(keys[0].get("key") or "")

    def token(self) -> str:
        item = packet("GET_TOKEN", self.fiscal_id, {"username": self.fiscal_id})
        body = self._signed("/sync/GET_TOKEN", "packet", item)
        token = (((body.get("result") or {}).get("data") or {}).get("token")) or ""
        if not token:
            raise MoadianError("توکن سامانه مودیان نیامد. شناسه حافظه و کلید خصوصی را بررسی کنید.")
        return str(token)

    def economic_code(self, economic_code: str) -> dict:
        item = packet("GET_ECONOMIC_CODE_INFORMATION", self.fiscal_id, {"economicCode": economic_code})
        return self._open("/sync/GET_ECONOMIC_CODE_INFORMATION", item)

    def send_invoice(self, invoice: dict) -> dict:
        key_id, public_key = self.public_key()
        signed = packet("INVOICE.V01", self.fiscal_id)
        signed["dataSignature"] = sign_text(normalize_json(invoice), self.private_key)
        data, wrapped, iv = encrypt_invoice(invoice, public_key)
        signed["data"] = data
        signed["symmetricKey"] = wrapped
        signed["iv"] = iv
        signed["encryptionKeyId"] = key_id
        token = self.token()
        return self._signed("/async/normal-enqueue", "packets", [signed], token)

    def inquiry(self, reference: str) -> dict:
        item = packet("INQUIRY_BY_REFERENCE_NUMBER", self.fiscal_id, {"referenceNumber": [reference]})
        return self._signed("/sync/INQUIRY_BY_REFERENCE_NUMBER", "packet", item, self.token())
