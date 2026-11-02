import base64
import json

import pytest

import probar_api


def _token(payload: dict) -> str:
    def trozo(datos: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(datos).encode()).rstrip(b"=").decode()

    return f"{trozo({'alg': 'RS256'})}.{trozo(payload)}.firma"


def _lanzar(monkeypatch, *argumentos):
    monkeypatch.setattr("sys.argv", ["probar_api.py", *argumentos])
    probar_api.main()


class CognitoFalso:
    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.peticion = None

    def initiate_auth(self, **kwargs):
        self.peticion = kwargs
        return self.respuesta


@pytest.fixture
def cognito(monkeypatch):
    """Cliente de Cognito que devuelve un token con el grupo tiendas, y contraseña por entorno."""
    falso = CognitoFalso({"AuthenticationResult": {"IdToken": _token({"cognito:groups": ["tiendas"]})}})
    monkeypatch.setenv("PASSWORD_TIENDA", "contraseña-de-prueba")

    class Sesion:
        creada_con = {}

        def __init__(self, **kwargs):
            Sesion.creada_con = kwargs

        def client(self, _servicio):
            return falso

    monkeypatch.setattr(probar_api.boto3, "Session", Sesion)
    falso.sesion = Sesion
    return falso


def _api(monkeypatch, sin_token=401, con_token=200):
    monkeypatch.setattr(probar_api, "llamar", lambda _url, token=None: (con_token if token else sin_token, "{}"))


def _sin_terraform(monkeypatch):
    def falla(_modulo):
        raise AssertionError("No debe leer Terraform")

    monkeypatch.setattr(probar_api, "outputs", falla)


def test_montado_a_mano_no_usa_terraform(monkeypatch, cognito, capsys):
    _sin_terraform(monkeypatch)
    _api(monkeypatch)
    _lanzar(monkeypatch, "--url", "https://x/prod/hola", "--client-id", "cliente", "--usuario", "tienda-mad-001")
    assert cognito.peticion["ClientId"] == "cliente"
    assert cognito.peticion["AuthParameters"] == {"USERNAME": "tienda-mad-001", "PASSWORD": "contraseña-de-prueba"}
    assert cognito.sesion.creada_con["region_name"] == "eu-west-1"
    assert "Terminado (401 sin token y 200 con token): SÍ" in capsys.readouterr().out


def test_region_con_argumento(monkeypatch, cognito):
    _sin_terraform(monkeypatch)
    _api(monkeypatch)
    _lanzar(monkeypatch, "--url", "https://x", "--client-id", "c", "--region", "us-east-1")
    assert cognito.sesion.creada_con["region_name"] == "us-east-1"


def test_por_defecto_lee_terraform(monkeypatch, cognito):
    salidas = {"url_api": "https://tf/prod/hola", "client_id": "cliente-tf", "region": "eu-west-1"}
    monkeypatch.setattr(probar_api, "outputs", lambda _modulo: salidas)
    urls = []

    def llamar(url, token=None):
        urls.append(url)
        return (200 if token else 401), "{}"

    monkeypatch.setattr(probar_api, "llamar", llamar)
    _lanzar(monkeypatch)
    assert urls == ["https://tf/prod/hola"] * 2
    assert cognito.peticion["ClientId"] == "cliente-tf"
    assert cognito.peticion["AuthParameters"]["USERNAME"] == "tienda-vlc-003"


@pytest.mark.parametrize("argumentos", [("--url", "https://x"), ("--client-id", "c")])
def test_url_y_client_id_van_juntos(monkeypatch, capsys, argumentos):
    _sin_terraform(monkeypatch)
    with pytest.raises(SystemExit) as salida:
        _lanzar(monkeypatch, *argumentos)
    assert salida.value.code == 2
    assert "van juntos" in capsys.readouterr().err


def test_decodificar_no_usa_aws_ni_terraform(monkeypatch, capsys):
    _sin_terraform(monkeypatch)

    def falla(**_kwargs):
        raise AssertionError("No debe usar AWS")

    monkeypatch.setattr(probar_api.boto3, "Session", falla)
    _lanzar(monkeypatch, "--decodificar", _token({"cognito:groups": ["tiendas"], "token_use": "id"}))
    assert json.loads(capsys.readouterr().out) == {"cognito:groups": ["tiendas"], "token_use": "id"}


@pytest.mark.parametrize(
    ("sin_token", "con_token"),
    [(200, 200), (401, 401), (403, 200)],
)
def test_no_terminado_sale_con_error(monkeypatch, cognito, capsys, sin_token, con_token):
    _sin_terraform(monkeypatch)
    _api(monkeypatch, sin_token, con_token)
    with pytest.raises(SystemExit) as salida:
        _lanzar(monkeypatch, "--url", "https://x", "--client-id", "c")
    assert salida.value.code == 1
    assert "Terminado (401 sin token y 200 con token): NO" in capsys.readouterr().out


def test_sin_el_grupo_termina_pero_avisa(monkeypatch, cognito, capsys):
    cognito.respuesta = {"AuthenticationResult": {"IdToken": _token({"sub": "x"})}}
    _sin_terraform(monkeypatch)
    _api(monkeypatch)
    with pytest.raises(SystemExit) as salida:
        _lanzar(monkeypatch, "--url", "https://x", "--client-id", "c")
    assert salida.value.code == 1
    texto = capsys.readouterr().out
    assert "[FALLO] Grupo tiendas en el token" in texto
    assert "(401 sin token y 200 con token): SÍ" in texto


def test_usuario_en_force_change_password(monkeypatch, cognito):
    cognito.respuesta = {"ChallengeName": "NEW_PASSWORD_REQUIRED", "Session": "s"}
    _sin_terraform(monkeypatch)
    _api(monkeypatch)
    with pytest.raises(SystemExit) as salida:
        _lanzar(monkeypatch, "--url", "https://x", "--client-id", "c")
    assert "FORCE_CHANGE_PASSWORD" in str(salida.value.code)
