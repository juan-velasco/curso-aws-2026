import base64
import json

from probar_api import decodificar_jwt


def _token(payload: dict) -> str:
    def trozo(datos: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(datos).encode()).rstrip(b"=").decode()

    return f"{trozo({'alg': 'RS256'})}.{trozo(payload)}.firma-sin-verificar"


def test_decodifica_el_payload():
    payload = {"sub": "5f1c", "cognito:groups": ["tiendas"], "token_use": "id", "exp": 1793270400}
    assert decodificar_jwt(_token(payload)) == payload


def test_longitudes_que_necesitan_relleno():
    for longitud in range(1, 8):
        payload = {"sub": "x" * longitud}
        assert decodificar_jwt(_token(payload)) == payload


def test_caracteres_de_base64url():
    # ~ y ? producen - y _ en base64url
    payload = {"sub": "~~~???>>>", "nombre": "tienda ñ"}
    assert decodificar_jwt(_token(payload)) == payload
