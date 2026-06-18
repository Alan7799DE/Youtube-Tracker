"""Casos borde de la Fase 2 (resolución de canales).

Complementa test_channels_refs.py y test_channels_resolve.py con los límites
reales que enfrenta la entrada del usuario: URLs con query/paths, variantes de
dominio, payloads parciales de la API y errores HTTP.
"""
import pytest
import requests

from verifier.channels.refs import parse_channel_ref, ChannelRef
from verifier.channels.resolve import (
    resolve_channel,
    _params_for,
    ResolvedChannel,
    API_URL,
)


# --------------------------------------------------------------------------- #
# parse_channel_ref — casos borde                                             #
# --------------------------------------------------------------------------- #

def test_handle_url_con_query_params():
    # El usuario pega el link de compartir con ?si=...
    assert parse_channel_ref("https://youtube.com/@GamerPro?si=abc123") == ChannelRef(
        kind="handle", value="GamerPro"
    )


def test_handle_url_con_path_extra():
    # /@handle/videos, /@handle/about, etc.
    assert parse_channel_ref("https://www.youtube.com/@GamerPro/videos") == ChannelRef(
        kind="handle", value="GamerPro"
    )


def test_channel_id_url_con_path_extra():
    assert parse_channel_ref("https://youtube.com/channel/UC123abc/featured") == ChannelRef(
        kind="channel_id", value="UC123abc"
    )


def test_handle_url_trailing_slash():
    assert parse_channel_ref("https://youtube.com/@GamerPro/") == ChannelRef(
        kind="handle", value="GamerPro"
    )


def test_m_youtube_subdominio_movil():
    assert parse_channel_ref("https://m.youtube.com/@GamerPro") == ChannelRef(
        kind="handle", value="GamerPro"
    )


def test_http_sin_s():
    assert parse_channel_ref("http://youtube.com/channel/UC123abc") == ChannelRef(
        kind="channel_id", value="UC123abc"
    )


def test_custom_url_c_es_username():
    assert parse_channel_ref("https://youtube.com/c/SomeBrand") == ChannelRef(
        kind="username", value="SomeBrand"
    )


def test_handle_con_punto_guion_bajo():
    # Los handles admiten . _ -
    assert parse_channel_ref("@gamer.pro_1") == ChannelRef(kind="handle", value="gamer.pro_1")


def test_espacios_alrededor_se_recortan():
    assert parse_channel_ref("   @GamerPro   ") == ChannelRef(kind="handle", value="GamerPro")


def test_handle_preserva_mayusculas():
    # No se normaliza el caso del handle; la API es case-insensitive pero
    # acá no decidimos eso.
    assert parse_channel_ref("@GamerPro").value == "GamerPro"


def test_uc_minuscula_no_es_channel_id():
    # "UC" debe ir en mayúsculas; lo demás cae en unknown (no se inventa un id).
    assert parse_channel_ref("uc123abc").kind == "unknown"


def test_texto_libre_es_unknown_con_valor_original():
    r = parse_channel_ref("Gamer Pro")
    assert r == ChannelRef(kind="unknown", value="Gamer Pro")


def test_string_vacio_es_unknown():
    assert parse_channel_ref("").kind == "unknown"


def test_channel_id_con_guiones_y_guion_bajo():
    assert parse_channel_ref("UC-_aBc123") == ChannelRef(kind="channel_id", value="UC-_aBc123")


def test_arroba_solo_da_handle_vacio():
    # Caso degenerado: "@" pelado. Documenta el comportamiento actual:
    # handle de valor vacío (luego no resolvería contra la API).
    assert parse_channel_ref("@") == ChannelRef(kind="handle", value="")


def test_dominio_mayusculas_no_matchea_url():
    # El regex de dominio es case-sensitive: un dominio en mayúsculas no se
    # reconoce como URL y cae en unknown. Documenta la limitación.
    assert parse_channel_ref("https://YOUTUBE.COM/@GamerPro").kind == "unknown"


# --------------------------------------------------------------------------- #
# _params_for — construcción de parámetros                                    #
# --------------------------------------------------------------------------- #

def test_params_handle_agrega_arroba():
    p = _params_for(ChannelRef(kind="handle", value="gamerpro"), api_key="K")
    assert p["forHandle"] == "@gamerpro"
    assert p["part"] == "snippet"
    assert p["key"] == "K"


def test_params_handle_no_duplica_arroba():
    # Defensivo: si el valor ya trae @, no se duplica.
    p = _params_for(ChannelRef(kind="handle", value="@gamerpro"), api_key="K")
    assert p["forHandle"] == "@gamerpro"


def test_params_username_usa_for_username():
    p = _params_for(ChannelRef(kind="username", value="OldName"), api_key="K")
    assert p["forUsername"] == "OldName"
    assert "forHandle" not in p and "id" not in p


def test_params_channel_id_usa_id():
    p = _params_for(ChannelRef(kind="channel_id", value="UC123"), api_key="K")
    assert p["id"] == "UC123"


def test_params_unknown_es_none():
    assert _params_for(ChannelRef(kind="unknown", value="x"), api_key="K") is None


# --------------------------------------------------------------------------- #
# resolve_channel — casos borde con mocks                                     #
# --------------------------------------------------------------------------- #

def _resp(mocker, payload, status_exc=None):
    resp = mocker.Mock()
    resp.json.return_value = payload
    if status_exc is None:
        resp.raise_for_status.return_value = None
    else:
        resp.raise_for_status.side_effect = status_exc
    return resp


def test_resolve_pasa_url_y_timeout(mocker):
    payload = {"items": [{"id": "UC1", "snippet": {"title": "T", "customUrl": "@t"}}]}
    get = mocker.patch("verifier.channels.resolve.requests.get", return_value=_resp(mocker, payload))
    resolve_channel(ChannelRef(kind="handle", value="t"), api_key="K")
    assert get.call_args.args[0] == API_URL
    assert get.call_args.kwargs["timeout"] == 15
    assert get.call_args.kwargs["params"]["key"] == "K"


def test_resolve_toma_el_primer_item(mocker):
    payload = {"items": [
        {"id": "UC_first", "snippet": {"title": "Primero", "customUrl": "@first"}},
        {"id": "UC_second", "snippet": {"title": "Segundo", "customUrl": "@second"}},
    ]}
    mocker.patch("verifier.channels.resolve.requests.get", return_value=_resp(mocker, payload))
    r = resolve_channel(ChannelRef(kind="handle", value="x"), api_key="K")
    assert r.channel_id == "UC_first"


def test_resolve_snippet_faltante_deja_campos_none(mocker):
    payload = {"items": [{"id": "UC_no_snippet"}]}
    mocker.patch("verifier.channels.resolve.requests.get", return_value=_resp(mocker, payload))
    r = resolve_channel(ChannelRef(kind="channel_id", value="UC_no_snippet"), api_key="K")
    assert r == ResolvedChannel(channel_id="UC_no_snippet", name=None, handle=None)


def test_resolve_snippet_sin_custom_url(mocker):
    payload = {"items": [{"id": "UC1", "snippet": {"title": "Solo Titulo"}}]}
    mocker.patch("verifier.channels.resolve.requests.get", return_value=_resp(mocker, payload))
    r = resolve_channel(ChannelRef(kind="channel_id", value="UC1"), api_key="K")
    assert r.name == "Solo Titulo"
    assert r.handle is None


def test_resolve_propaga_error_http(mocker):
    # 403 por quota agotada: raise_for_status revienta y el error sube.
    err = requests.HTTPError("403 quota exceeded")
    mocker.patch(
        "verifier.channels.resolve.requests.get",
        return_value=_resp(mocker, {}, status_exc=err),
    )
    with pytest.raises(requests.HTTPError):
        resolve_channel(ChannelRef(kind="handle", value="x"), api_key="K")


def test_resolve_unknown_no_hace_request_red(mocker):
    get = mocker.patch("verifier.channels.resolve.requests.get")
    assert resolve_channel(ChannelRef(kind="unknown", value="Gamer Pro"), api_key="K") is None
    get.assert_not_called()
