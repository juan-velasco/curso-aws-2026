"""Generador de ventas del TPV: envía lotes de eventos a la API de ventas.

Un evento es una línea de ticket. Los eventos se construyen en comun/eventos.py
con los maestros de comun/maestros.py, así que tiendas, clientes y productos
existen en los maestros que replica DMS (demo 2).

Configuración por variables de entorno (ver Config.desde_entorno).
"""

from __future__ import annotations

import json
import logging
import os
import random
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx2 as httpx

from comun.eventos import FabricaVentas, ahora_iso

log = logging.getLogger("generador")


@dataclass(frozen=True)
class Config:
    api_url: str = "http://api:8000"
    eventos_por_segundo: float = 1.0
    modo: str = "normal"  # normal | pico (x10)
    duracion_min: float = 10.0
    tam_lote: int = 25
    duplicados_pct: float = 0.0
    invalidos_pct: float = 0.0
    salida: Path = Path("salida")

    @classmethod
    def desde_entorno(cls) -> Config:
        env = os.environ
        config = cls(
            api_url=env.get("API_URL", cls.api_url).rstrip("/"),
            eventos_por_segundo=float(env.get("EVENTOS_POR_SEGUNDO", cls.eventos_por_segundo)),
            modo=env.get("MODO", cls.modo).lower(),
            duracion_min=float(env.get("DURACION_MIN", cls.duracion_min)),
            tam_lote=int(env.get("TAM_LOTE", cls.tam_lote)),
            duplicados_pct=float(env.get("DUPLICADOS_PCT", cls.duplicados_pct)),
            invalidos_pct=float(env.get("INVALIDOS_PCT", cls.invalidos_pct)),
            salida=Path(env.get("SALIDA_DIR", str(cls.salida))),
        )
        if config.modo not in ("normal", "pico"):
            raise SystemExit(f"MODO debe ser 'normal' o 'pico', no '{config.modo}'")
        if not 1 <= config.tam_lote <= 500:
            raise SystemExit("TAM_LOTE debe estar entre 1 y 500 (límite de la API)")
        return config

    @property
    def ritmo(self) -> float:
        """Eventos por segundo efectivos: en hora pico, x10."""
        return self.eventos_por_segundo * (10 if self.modo == "pico" else 1)


@dataclass
class Resumen:
    inicio: str = field(default_factory=ahora_iso)
    fin: str | None = None
    eventos_generados: int = 0
    eventos_enviados: int = 0  # válidos, incluidos los duplicados
    eventos_aceptados: int = 0  # según las respuestas 202 de la API
    duplicados_enviados: int = 0
    duplicados_aceptados: int = 0
    eventos_perdidos: int = 0  # lotes que fallaron tras todos los reintentos
    invalidos_enviados: int = 0
    invalidos_rechazados: int = 0  # respondidos con 422
    lotes_enviados: int = 0


class Generador:
    def __init__(self, config: Config, cliente: httpx.Client | None = None, rng: random.Random | None = None):
        self.config = config
        self.cliente = cliente or httpx.Client(base_url=config.api_url, timeout=10)
        self.rng = rng or random.Random()
        self.fabrica = FabricaVentas(self.rng)
        self.resumen = Resumen()
        self.pendientes: list[dict] = []  # eventos listos para el próximo lote
        self.copias: set[int] = set()  # id() de los eventos duplicados pendientes de enviar

    # --- envío -------------------------------------------------------------

    def _post(self, eventos: list[dict], intentos: int = 5) -> httpx.Response | None:
        """POST con backoff ante errores de red o 5xx. None si se agotan los intentos."""
        for intento in range(intentos):
            try:
                r = self.cliente.post("/ventas/lote", json=eventos)
                if r.status_code < 500:
                    return r
                log.warning("La API respondió %s: %s", r.status_code, r.text[:200])
            except httpx.TransportError as e:
                log.warning("Error de red llamando a la API: %s", e)
            time.sleep(0.5 * 2**intento)
        return None

    def enviar_lote(self, lote: list[dict]) -> None:
        duplicados = sum(1 for e in lote if id(e) in self.copias)
        self.copias.difference_update(id(e) for e in lote)
        self.resumen.eventos_enviados += len(lote)
        self.resumen.lotes_enviados += 1
        r = self._post(lote)
        if r is not None and r.status_code == 202:
            self.resumen.eventos_aceptados += r.json()["enviados"]
            self.resumen.duplicados_aceptados += duplicados
        elif r is None:
            log.error("Lote de %d eventos perdido tras agotar los reintentos", len(lote))
            self.resumen.eventos_perdidos += len(lote)
        else:
            log.error("Lote válido rechazado (%s): %s", r.status_code, r.text[:300])
            self.resumen.eventos_perdidos += len(lote)

    def enviar_invalido(self, evento: dict) -> None:
        self.resumen.invalidos_enviados += 1
        r = self._post([evento])
        if r is not None and r.status_code == 422:
            self.resumen.invalidos_rechazados += 1
        else:
            log.error("Evento inválido NO rechazado: %s", None if r is None else r.status_code)

    def vaciar(self, todo: bool = False) -> None:
        """Envía los eventos pendientes en lotes de TAM_LOTE (todos si `todo`)."""
        tam = self.config.tam_lote
        while len(self.pendientes) >= tam or (todo and self.pendientes):
            lote, self.pendientes = self.pendientes[:tam], self.pendientes[tam:]
            self.enviar_lote(lote)

    # --- generación ----------------------------------------------------------

    def generar_ticket(self) -> int:
        lineas = self.fabrica.ticket()
        self.resumen.eventos_generados += len(lineas)
        for evento in lineas:
            if self.rng.random() * 100 < self.config.invalidos_pct:
                self.enviar_invalido(self.fabrica.invalido(evento))
        # Los duplicados se reenvían al final de la cola: llegan en un lote posterior,
        # como el reintento de un TPV que no recibió respuesta
        copias = [dict(e) for e in lineas if self.rng.random() * 100 < self.config.duplicados_pct]
        self.pendientes.extend(lineas)
        self.pendientes.extend(copias)
        self.copias.update(id(e) for e in copias)
        self.resumen.duplicados_enviados += len(copias)
        return len(lineas)

    def log_progreso(self, transcurrido: float) -> None:
        r = self.resumen
        log.info(
            "Progreso %4.0f s: %d generados, %d enviados, %d aceptados, %d duplicados, "
            "%d inválidos rechazados, %d perdidos (%.1f ev/s)",
            transcurrido,
            r.eventos_generados,
            r.eventos_enviados,
            r.eventos_aceptados,
            r.duplicados_enviados,
            r.invalidos_rechazados,
            r.eventos_perdidos,
            r.eventos_generados / max(transcurrido, 1e-9),
        )

    def ejecutar(self) -> Resumen:
        c = self.config
        log.info(
            "Inicio: %s, modo %s, %.1f eventos/s durante %.1f min, lotes de %d, duplicados %.1f %%, inválidos %.1f %%",
            c.api_url, c.modo, c.ritmo, c.duracion_min, c.tam_lote, c.duplicados_pct, c.invalidos_pct,
        )
        t0 = time.monotonic()
        fin = t0 + c.duracion_min * 60
        ultimo_envio = ultimo_log = t0
        while (ahora := time.monotonic()) < fin:
            # Generar los tickets necesarios para mantener el ritmo objetivo
            objetivo = (ahora - t0) * c.ritmo
            while self.resumen.eventos_generados < objetivo:
                self.generar_ticket()
            if len(self.pendientes) >= c.tam_lote:
                self.vaciar()
                ultimo_envio = ahora
            elif self.pendientes and ahora - ultimo_envio >= 1:  # se envía también al pasar 1 s
                self.vaciar(todo=True)
                ultimo_envio = ahora
            if ahora - ultimo_log >= 10:
                self.log_progreso(ahora - t0)
                ultimo_log = ahora
            time.sleep(0.05)
        self.vaciar(todo=True)
        self.resumen.fin = ahora_iso()
        self.log_progreso(time.monotonic() - t0)
        return self.resumen

    def guardar_resumen(self) -> None:
        datos = {**vars(self.resumen), "config": {**vars(self.config), "salida": str(self.config.salida)}}
        texto = json.dumps(datos, indent=2, ensure_ascii=False)
        try:
            self.config.salida.mkdir(parents=True, exist_ok=True)
            fichero = self.config.salida / "resumen.json"
            fichero.write_text(texto + "\n", encoding="utf-8")
            log.info("Resumen escrito en %s", fichero)
        except OSError as e:
            log.error("No se pudo escribir el resumen (%s). Resumen:\n%s", e, texto)


def esperar_api(cliente: httpx.Client, segundos: int = 60) -> None:
    limite = time.monotonic() + segundos
    while True:
        try:
            if cliente.get("/health").status_code == 200:
                return
        except httpx.TransportError:
            pass
        if time.monotonic() > limite:
            raise SystemExit("La API no responde en /health")
        time.sleep(1)


def parar(signum, frame):
    raise KeyboardInterrupt


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)  # sin una línea por petición
    signal.signal(signal.SIGTERM, parar)  # docker compose stop/down envía SIGTERM
    generador = Generador(Config.desde_entorno())
    esperar_api(generador.cliente)
    try:
        generador.ejecutar()
    except KeyboardInterrupt:
        log.info("Interrumpido: enviando los eventos pendientes")
        generador.vaciar(todo=True)
        generador.resumen.fin = ahora_iso()
    generador.guardar_resumen()


if __name__ == "__main__":
    main()
