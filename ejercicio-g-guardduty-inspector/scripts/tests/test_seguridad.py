from estado_servicios import comparable, recomendacion
from hallazgos_ejemplo import contar_ejemplos, tramo
from resumen_inspector import paquetes_con_mas_cve, por_severidad


def test_tramos_de_severidad():
    assert [tramo(s) for s in (9.0, 8.9, 7.0, 6.9, 4.0, 3.9, 1.0)] == [
        "Crítica", "Alta", "Alta", "Media", "Media", "Baja", "Baja"
    ]  # fmt: skip


def test_solo_cuenta_los_de_ejemplo():
    def hallazgo(severidad, valor):
        return {"Severity": severidad, "Service": {"AdditionalInfo": {"Value": valor}}}

    hallazgos = [
        hallazgo(8.0, '{"threatListName":"x","sample":true}'),
        hallazgo(2.0, '{"sample":true}'),
        hallazgo(8.0, '{"threatListName":"x"}'),
        {"Severity": 5.0},
    ]
    assert contar_ejemplos(hallazgos) == {"Alta": 1, "Baja": 1}


def _hallazgo(cve, *paquetes, severidad="HIGH"):
    return {
        "severity": severidad,
        "packageVulnerabilityDetails": {"vulnerabilityId": cve, "vulnerablePackages": [{"name": p} for p in paquetes]},
    }


def test_paquetes_ordenados_por_cve_distintos():
    hallazgos = [_hallazgo("CVE-1", "openssl"), _hallazgo("CVE-2", "openssl"), _hallazgo("CVE-3", "curl", "openssl")]
    assert paquetes_con_mas_cve(hallazgos) == [("openssl", 3), ("curl", 1)]


def test_mismo_cve_en_dos_hallazgos_cuenta_una_vez():
    assert paquetes_con_mas_cve([_hallazgo("CVE-1", "curl"), _hallazgo("CVE-1", "curl")]) == [("curl", 1)]


def test_como_mucho_cinco_paquetes_y_hallazgos_sin_paquete():
    hallazgos = [_hallazgo(f"CVE-{n}", f"p{n}") for n in range(8)] + [{"severity": "LOW"}]
    assert len(paquetes_con_mas_cve(hallazgos)) == 5
    assert por_severidad(hallazgos) == {"HIGH": 8, "LOW": 1}


def _estado(detector=False, ecr="DISABLED", admin=None):
    return {"detector": detector, "activo": detector, "administrador": None}, {
        "recursos": {"ecr": ecr},
        "administrador": admin,
    }


def test_activa_lo_que_esta_desactivado():
    assert recomendacion(*_estado()) == {"crear_detector_guardduty": True, "activar_inspector_ecr": True}


def test_no_toca_lo_que_ya_esta_activo():
    assert recomendacion(*_estado(detector=True, ecr="ENABLED")) == {
        "crear_detector_guardduty": False,
        "activar_inspector_ecr": False,
    }


def test_no_toca_lo_que_gestiona_la_organizacion():
    assert recomendacion(*_estado(admin="111122223333"))["activar_inspector_ecr"] is False


def test_comparar_ignora_tipos_nuevos_desactivados():
    gd = {"detector": False, "activo": False, "administrador": None}
    antes = {"guardduty": gd, "inspector": {"recursos": {"ecr": "DISABLED"}, "administrador": None}}
    recursos = {"ecr": "DISABLED", "ami": "DISABLED"}
    despues = {"guardduty": gd, "inspector": {"recursos": recursos, "administrador": None}}
    assert comparable(antes) == comparable(despues)
    activo = {"guardduty": gd, "inspector": {"recursos": {"ecr": "ENABLED"}, "administrador": None}}
    assert comparable(antes) != comparable(activo)
