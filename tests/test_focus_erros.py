"""Testes do decodificador de erro do Focus/Olinda."""

from __future__ import annotations

from pathlib import Path

from bcb_ingest.focus import decodificar_erro_olinda

DIR_FIXTURES = Path(__file__).parent / "fixtures"


def test_decodifica_erro_envelopado_em_comentario_real() -> None:
    corpo = (DIR_FIXTURES / "focus_erro_sintaxe.txt").read_text(encoding="utf-8")

    mensagem = decodificar_erro_olinda(corpo)

    assert "400" in mensagem
    assert "substringof" in mensagem


def test_decodifica_json_puro_sem_envelope() -> None:
    mensagem = decodificar_erro_olinda('{"codigo": 404, "mensagem": "não encontrado"}')

    assert "404" in mensagem
    assert "não encontrado" in mensagem


def test_corpo_nao_reconhecido_cai_no_fallback_sem_estourar() -> None:
    mensagem = decodificar_erro_olinda("<html>erro genérico do proxy</html>")

    assert "não reconhecido" in mensagem
    assert "<html>" in mensagem
