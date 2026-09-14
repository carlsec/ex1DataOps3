"""Checks de qualidade de dados — funções puras e testáveis.

Cada check recebe um DataFrame (e parâmetros próprios) e devolve um dict:

    {"check": <nome>, "passed": <bool>, "details": <mensagem legível>}

Nenhum check decide sozinho se deve travar o pipeline. Essa decisão é
externa, em `SEVERITY`, para ficar explícita e fácil de ajustar sem tocar
na lógica de cada checagem.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

BLOCKING = "BLOQUEANTE"
WARNING = "ALERTA"

# Ajuste aqui quais checks travam o Quality Gate e quais só geram alerta.
# schema e consistency são os exemplos "óbvios" de bloqueio: se a forma dos
# dados não é a esperada, ou se o valor central (total_amount) não bate com
# a conta, não há decisão de negócio segura a se tomar. volume abaixo do
# esperado é tratado como alerta: uma carga parcial pode ser legítima
# (ex: job rodou no meio do dia) e merece investigação, não bloqueio automático.
SEVERITY = {
    "schema": BLOCKING,
    "nulls": BLOCKING,
    "duplicates": BLOCKING,
    "volume": WARNING,
    "freshness": BLOCKING,
    "consistency": BLOCKING,
}

EXPECTED_COLUMNS = {
    "order_id": "int",
    "customer_id": "string",
    "product": "string",
    "quantity": "numeric",
    "unit_price": "numeric",
    "region": "string",
    "total_amount": "numeric",
}

_NUMERIC_KINDS = {"numeric": ("i", "u", "f")}


def _result(check: str, passed: bool, details: str) -> dict:
    return {"check": check, "passed": passed, "details": details}


def check_schema(df: pd.DataFrame, expected_columns: dict | None = None) -> dict:
    """Confere se as colunas esperadas existem e têm tipo compatível."""
    expected = expected_columns or EXPECTED_COLUMNS

    missing = [col for col in expected if col not in df.columns]
    if missing:
        return _result(
            "schema",
            False,
            f"Colunas ausentes: {sorted(missing)}",
        )

    wrong_type = []
    for col, kind in expected.items():
        if kind != "numeric":
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            wrong_type.append(col)

    if wrong_type:
        return _result(
            "schema",
            False,
            f"Colunas com tipo incompatível (esperado numérico): {sorted(wrong_type)}",
        )

    return _result("schema", True, "Todas as colunas esperadas presentes e com tipo compatível")


def check_nulls(
    df: pd.DataFrame,
    campos_obrigatorios: list[str],
    limite_percentual: float,
) -> dict:
    """Falha se algum campo obrigatório tiver % de nulos acima do limite."""
    if df.empty:
        return _result("nulls", True, "DataFrame vazio: nada a checar")

    violacoes = []
    for campo in campos_obrigatorios:
        if campo not in df.columns:
            violacoes.append(f"{campo} (coluna ausente)")
            continue
        percentual_nulo = df[campo].isnull().mean() * 100
        if percentual_nulo > limite_percentual:
            violacoes.append(f"{campo}={percentual_nulo:.1f}%")

    if violacoes:
        return _result(
            "nulls",
            False,
            f"Campos acima do limite de {limite_percentual}% de nulos: {', '.join(violacoes)}",
        )

    return _result(
        "nulls", True, f"Nenhum campo obrigatório acima de {limite_percentual}% de nulos"
    )


def check_duplicates(df: pd.DataFrame, chave: list[str] | None = None) -> dict:
    """Falha se houver linhas duplicadas pela chave informada."""
    chave = chave or ["order_id"]
    missing = [col for col in chave if col not in df.columns]
    if missing:
        return _result("duplicates", False, f"Coluna(s) de chave ausente(s): {missing}")

    duplicated_mask = df.duplicated(subset=chave, keep=False)
    if duplicated_mask.any():
        valores = df.loc[duplicated_mask, chave].drop_duplicates().to_dict("records")
        return _result(
            "duplicates",
            False,
            f"Chave {chave} duplicada em {duplicated_mask.sum()} linha(s): {valores}",
        )

    return _result("duplicates", True, f"Nenhuma duplicidade encontrada para a chave {chave}")


def check_volume(df: pd.DataFrame, volume_esperado_min: int, volume_esperado_max: int) -> dict:
    """Falha se o número de linhas estiver fora da janela esperada."""
    total = len(df)
    if total < volume_esperado_min or total > volume_esperado_max:
        return _result(
            "volume",
            False,
            f"Volume {total} fora da janela esperada "
            f"[{volume_esperado_min}, {volume_esperado_max}]",
        )

    return _result(
        "volume",
        True,
        f"Volume {total} dentro da janela esperada [{volume_esperado_min}, {volume_esperado_max}]",
    )


def check_freshness(
    df: pd.DataFrame,
    coluna_data: str,
    sla_horas: float,
    reference_time: datetime | None = None,
) -> dict:
    """Falha se alguma linha tiver `coluna_data` mais velha que o SLA."""
    if coluna_data not in df.columns:
        return _result("freshness", False, f"Coluna de data ausente: {coluna_data}")

    reference = pd.Timestamp(reference_time or datetime.now())
    datas = pd.to_datetime(df[coluna_data], errors="coerce")

    if datas.isnull().any():
        return _result(
            "freshness",
            False,
            f"{datas.isnull().sum()} linha(s) com {coluna_data} inválida ou não parseável",
        )

    idade_horas = (reference - datas).dt.total_seconds() / 3600
    atrasadas = idade_horas[idade_horas > sla_horas]

    if not atrasadas.empty:
        pior = atrasadas.max()
        return _result(
            "freshness",
            False,
            f"{len(atrasadas)} linha(s) fora do SLA de {sla_horas}h "
            f"(pior atraso: {pior:.1f}h)",
        )

    return _result("freshness", True, f"Todas as linhas dentro do SLA de {sla_horas}h")


def check_consistency(df: pd.DataFrame, tolerancia: float = 0.01) -> dict:
    """Falha se total_amount != quantity * unit_price (com tolerância)."""
    colunas = {"quantity", "unit_price", "total_amount"}
    missing = colunas - set(df.columns)
    if missing:
        return _result("consistency", False, f"Coluna(s) ausente(s): {sorted(missing)}")

    esperado = df["quantity"] * df["unit_price"]
    diferenca = (df["total_amount"] - esperado).abs()
    inconsistentes = diferenca[diferenca > tolerancia]

    if not inconsistentes.empty:
        linhas = df.loc[inconsistentes.index]
        exemplos = linhas.get("order_id", inconsistentes.index).tolist()[:5]
        return _result(
            "consistency",
            False,
            f"{len(inconsistentes)} linha(s) com total_amount != quantity * unit_price "
            f"(order_id de exemplo: {exemplos})",
        )

    return _result(
        "consistency",
        True,
        "total_amount bate com quantity * unit_price em todas as linhas (dentro da tolerância)",
    )


def run_all_checks(
    df: pd.DataFrame,
    *,
    campos_obrigatorios: list[str] | None = None,
    limite_percentual_nulos: float = 5.0,
    chave_duplicidade: list[str] | None = None,
    volume_esperado_min: int = 20,
    volume_esperado_max: int = 40,
    coluna_data: str = "event_date",
    sla_horas: float = 48.0,
    reference_time: datetime | None = None,
    tolerancia_consistencia: float = 0.01,
) -> list[dict]:
    """Executa todos os checks na ordem e devolve a lista de resultados."""
    campos_obrigatorios = campos_obrigatorios or ["order_id", "customer_id", "product", "region"]
    chave_duplicidade = chave_duplicidade or ["order_id"]

    return [
        check_schema(df),
        check_nulls(df, campos_obrigatorios, limite_percentual_nulos),
        check_duplicates(df, chave_duplicidade),
        check_volume(df, volume_esperado_min, volume_esperado_max),
        check_freshness(df, coluna_data, sla_horas, reference_time),
        check_consistency(df, tolerancia_consistencia),
    ]
