import logging
import os
import traceback
from datetime import datetime
from Configuracoes import ConfiguracaoAtual

class LogService:
    """
    Serviço centralizado de Logs.
    Gerencia logs de sessão (voláteis) e logs gerais (persistentes).
    """
    _logger = None
    _inicializado = False

    @staticmethod
    def Inicializar():
        if LogService._inicializado:
            return

        # Garante que o diretório de logs existe
        if not os.path.exists(ConfiguracaoAtual.DIR_LOGS):
            os.makedirs(ConfiguracaoAtual.DIR_LOGS)

        # Definição dos caminhos
        caminho_sessao = os.path.join(ConfiguracaoAtual.DIR_LOGS, "session.log")
        caminho_geral = os.path.join(ConfiguracaoAtual.DIR_LOGS, "application.log")

        # Configuração do Logger Principal
        logger = logging.getLogger("FlightOps")
        logger.setLevel(logging.DEBUG if ConfiguracaoAtual.DEBUG else logging.INFO)
        logger.handlers = []  # Limpa handlers anteriores para evitar duplicação
        logger.propagate = False

        # Formatação Profissional: DATA HORA | NIVEL | ORIGEM | MENSAGEM
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 1. Handler de Sessão (Reinicia a cada start da aplicação - mode='w')
        # encoding='utf-8' é crucial para evitar erros com acentos
        handler_sessao = logging.FileHandler(caminho_sessao, mode='w', encoding='utf-8')
        handler_sessao.setLevel(logging.DEBUG)
        handler_sessao.setFormatter(formatter)
        logger.addHandler(handler_sessao)

        # 2. Handler Geral (Histórico Eterno - mode='a')
        handler_geral = logging.FileHandler(caminho_geral, mode='a', encoding='utf-8')
        handler_geral.setLevel(logging.INFO) # No histórico geral, talvez não queira DEBUG para não encher o disco
        handler_geral.setFormatter(formatter)
        logger.addHandler(handler_geral)

        # 3. Handler de Console (Para ver no terminal enquanto desenvolve)
        handler_console = logging.StreamHandler()
        handler_console.setLevel(logging.DEBUG)
        handler_console.setFormatter(formatter)
        logger.addHandler(handler_console)

        LogService._logger = logger
        LogService._inicializado = True
        
        LogService.Info("LogService", "Sistema de logs inicializado com sucesso.")

    @staticmethod
    def _obter_logger(origem):
        if not LogService._logger:
            LogService.Inicializar()
        # Retorna um adaptador para injetar o nome da origem (Classe/Modulo) no log
        return logging.getLogger(f"FlightOps.{origem}")

    @staticmethod
    def Info(origem, mensagem):
        LogService._obter_logger(origem).info(mensagem)

    @staticmethod
    def Warning(origem, mensagem):
        LogService._obter_logger(origem).warning(mensagem)

    @staticmethod
    def Error(origem, mensagem, excecao=None):
        """
        Registra erros com stack trace completo se uma exceção for fornecida.
        """
        detalhes = mensagem
        if excecao:
            # Formata o traceback para string
            tb_str = "".join(traceback.format_exception(None, excecao, excecao.__traceback__))
            detalhes = f"{mensagem} | Exception: {str(excecao)}\nTraceback:\n{tb_str}"
        
        LogService._obter_logger(origem).error(detalhes)

    @staticmethod
    def Debug(origem, mensagem):
        # Só grava se DEBUG=True no .env (controlado pelo setLevel no Inicializar)
        LogService._obter_logger(origem).debug(mensagem)