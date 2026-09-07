"""Cliente HTTP genérico para as APIs do Banco Central."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx
import structlog

from bcb_ingest import __version__

logger = structlog.get_logger(__name__)

_STATUS_NAO_MODIFICADO = 304
_STATUS_LIMITE_TAXA = 429
_STATUS_ERRO_SERVIDOR = 500
_STATUS_ERRO_CLIENTE = 400


@dataclass(frozen=True)
class ConfiguracaoCliente:
    """Parâmetros de conexão, retry e identificação do cliente HTTP."""

    base_url: str
    timeout_conexao: float = 5.0
    timeout_leitura: float = 15.0
    max_tentativas: int = 4
    backoff_base_segundos: float = 0.5
    backoff_teto_segundos: float = 8.0
    limite_conexoes: int = 5
    limite_conexoes_keepalive: int = 5
    user_agent: str = (
        f"bcb-ingest/{__version__} (+https://github.com/mikhael907/projeto-bcb-python-dbt)"
    )


class ErroClienteBcb(Exception):
    """Base para todos os erros levantados pelo cliente HTTP do BCB."""


class ErroRequisicaoInvalida(ErroClienteBcb):
    """Erro 4xx diferente de 429."""

    def __init__(self, status_code: int, corpo_bruto: str, url: str) -> None:
        self.status_code = status_code
        self.corpo_bruto = corpo_bruto
        self.url = url
        super().__init__(f"requisição inválida ({status_code}) em {url}: {corpo_bruto[:500]}")


class ErroServidorIndisponivel(ErroClienteBcb):
    """Tentativas esgotadas após 429, 5xx ou timeout repetidos."""

    def __init__(
        self,
        tentativas: int,
        ultimo_status: int | None,
        ultimo_erro: Exception | None,
        url: str,
    ) -> None:
        self.tentativas = tentativas
        self.ultimo_status = ultimo_status
        self.ultimo_erro = ultimo_erro
        self.url = url
        super().__init__(
            f"servidor indisponível após {tentativas} tentativa(s) em {url} "
            f"(último status={ultimo_status}, último erro={ultimo_erro!r})"
        )


class ClienteBCB:
    """Cliente HTTP síncrono com timeout, retry e limite de concorrência."""

    def __init__(
        self,
        config: ConfiguracaoCliente,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._dormir = dormir
        self._http = httpx.Client(
            base_url=config.base_url,
            timeout=httpx.Timeout(
                connect=config.timeout_conexao,
                read=config.timeout_leitura,
                write=config.timeout_conexao,
                pool=config.timeout_conexao,
            ),
            limits=httpx.Limits(
                max_connections=config.limite_conexoes,
                max_keepalive_connections=config.limite_conexoes_keepalive,
            ),
            headers={"User-Agent": config.user_agent},
        )

    def __enter__(self) -> ClienteBCB:
        return self

    def __exit__(self, *exc: object) -> None:
        self.fechar()

    def fechar(self) -> None:
        self._http.close()

    def requisitar(
        self,
        metodo: str,
        caminho: str,
        *,
        params: dict[str, str] | None = None,
        etag_anterior: str | None = None,
    ) -> httpx.Response:
        headers = {"If-None-Match": etag_anterior} if etag_anterior else None
        ultimo_status: int | None = None
        ultimo_erro: Exception | None = None

        for tentativa in range(1, self._config.max_tentativas + 1):
            inicio = time.monotonic()
            retry_after: str | None = None
            try:
                resposta = self._http.request(metodo, caminho, params=params, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError) as erro:
                duracao = time.monotonic() - inicio
                logger.warning(
                    "requisicao_falhou",
                    metodo=metodo,
                    caminho=caminho,
                    tentativa=tentativa,
                    duracao_segundos=round(duracao, 3),
                    erro=repr(erro),
                )
                ultimo_erro = erro
                ultimo_status = None
            else:
                duracao = time.monotonic() - inicio
                logger.info(
                    "requisicao_concluida",
                    metodo=metodo,
                    caminho=caminho,
                    tentativa=tentativa,
                    status_code=resposta.status_code,
                    duracao_segundos=round(duracao, 3),
                )
                if resposta.status_code < _STATUS_ERRO_CLIENTE or (
                    resposta.status_code == _STATUS_NAO_MODIFICADO
                ):
                    return resposta
                if not self._deve_tentar_novamente(resposta.status_code, None):
                    raise ErroRequisicaoInvalida(
                        resposta.status_code, resposta.text, str(resposta.url)
                    )
                ultimo_status = resposta.status_code
                ultimo_erro = None
                retry_after = resposta.headers.get("Retry-After")

            if tentativa < self._config.max_tentativas:
                espera = self._calcular_espera(tentativa, retry_after)
                self._dormir(espera)

        raise ErroServidorIndisponivel(
            self._config.max_tentativas, ultimo_status, ultimo_erro, caminho
        )

    def _deve_tentar_novamente(self, status_code: int | None, excecao: Exception | None) -> bool:
        if excecao is not None:
            return True
        if status_code is None:
            return False
        return status_code == _STATUS_LIMITE_TAXA or status_code >= _STATUS_ERRO_SERVIDOR

    def _calcular_espera(self, tentativa: int, retry_after: str | None) -> float:
        if retry_after is not None:
            try:
                return float(retry_after)
            except ValueError:
                pass

        espera_base: float = min(
            self._config.backoff_teto_segundos,
            self._config.backoff_base_segundos * (2 ** (tentativa - 1)),
        )
        jitter: float = random.uniform(0, espera_base * 0.5)  # noqa: S311
        return espera_base + jitter
