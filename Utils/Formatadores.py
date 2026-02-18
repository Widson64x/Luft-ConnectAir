from datetime import datetime, date
import re

def PadronizarData(Valor):
    """
    Recebe uma data suja e retorna um objeto date padrão (sem horário).
    """
    if not Valor:
        return None

    # Verifica primeiro se é datetime para extrair apenas a data (.date())
    if isinstance(Valor, datetime):
        return Valor.date()
    
    # Se for apenas date, retorna ele mesmo
    if isinstance(Valor, date):
        return Valor

    ValorStr = str(Valor).strip().lower()

    # Mapa de meses em português
    MapaMeses = {
        'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04', 'mai': '05', 'jun': '06',
        'jul': '07', 'ago': '08', 'set': '09', 'out': '10', 'nov': '11', 'dez': '12'
    }

    try:
        # 1. Substitui meses texto por números
        for MesTexto, MesNum in MapaMeses.items():
            if MesTexto in ValorStr:
                ValorStr = ValorStr.replace(MesTexto, MesNum)
                break

        # 2. Limpa caracteres estranhos
        ValorLimpo = re.sub(r'[^0-9/\-]', '', ValorStr)

        # 3. Tenta converter formatos comuns
        FormatosPossiveis = [
            '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y'
        ]

        for Fmt in FormatosPossiveis:
            try:
                return datetime.strptime(ValorLimpo, Fmt).date()
            except ValueError:
                continue
        
        return None

    except Exception as e:
        print(f"⚠️ Erro ao padronizar data '{Valor}': {e}")
        return None