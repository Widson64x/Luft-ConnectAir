from functools import wraps
from flask import request, abort, flash, redirect, url_for
from flask_login import current_user
from sqlalchemy import or_
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Permissoes import Tb_PLN_Permissao, Tb_PLN_PermissaoGrupo, Tb_PLN_PermissaoUsuario, Tb_PLN_LogAcesso
from Services.LogService import LogService

class PermissaoService:
    
    @staticmethod
    def VerificarPermissao(Usuario, ChavePermissao):
        """
        Verifica se o usuário tem permissão via Grupo OU via Permissão Individual.
        Retorna True/False.
        """
        if not Usuario.is_authenticated:
            return False

        # Super Admin Bypass (Opcional)
        # Verifica se existe o atributo Grupo antes de comparar
        if getattr(Usuario, 'Grupo', '') == 'ADM_SISTEMA': 
            return True

        Sessao = ObterSessaoSqlServer()
        TemPermissao = False
        
        try:
            # Força o SQLAlchemy a buscar dados frescos do banco
            Sessao.expire_all() 

            # 1. Busca ID da permissão pela chave
            Permissao = Sessao.query(Tb_PLN_Permissao).filter_by(Chave_Permissao=ChavePermissao).first()
            
            if not Permissao:
                LogService.Warning("PermissaoService", f"Permissão não cadastrada: {ChavePermissao}")
                return False 

            # 2. Verifica se o GRUPO do usuário possui essa permissão
            IdGrupo = getattr(Usuario, 'codigo_usuariogrupo', getattr(Usuario, 'Id_Grupo_Banco', None))
            
            if IdGrupo:
                NoGrupo = Sessao.query(Tb_PLN_PermissaoGrupo).filter(
                    Tb_PLN_PermissaoGrupo.Id_Permissao == Permissao.Id_Permissao,
                    Tb_PLN_PermissaoGrupo.Codigo_UsuarioGrupo == IdGrupo
                ).count() > 0
            else:
                NoGrupo = False

            # 3. Checa Individual (Permissão Específica do Usuário)
            IdUsuario = getattr(Usuario, 'Codigo_Usuario', getattr(Usuario, 'IdBanco', None))
            
            NoUsuario = Sessao.query(Tb_PLN_PermissaoUsuario).filter(
                Tb_PLN_PermissaoUsuario.Id_Permissao == Permissao.Id_Permissao,
                Tb_PLN_PermissaoUsuario.Codigo_Usuario == IdUsuario
            ).first()

            # Lógica de Prevalência
            if NoUsuario:
                TemPermissao = NoUsuario.Conceder 
            else:
                TemPermissao = NoGrupo

        except Exception as e:
            LogService.Error("PermissaoService", f"Erro ao validar permissão '{ChavePermissao}'", e)
            TemPermissao = False 
        finally:
            Sessao.close()
            
        return TemPermissao

    @staticmethod
    def RegistrarLog(Usuario, Rota, Metodo, Ip, Chave, Permitido):
        Sessao = ObterSessaoSqlServer()
        try:
            IdUsuario = getattr(Usuario, 'Codigo_Usuario', getattr(Usuario, 'IdBanco', None)) if Usuario.is_authenticated else None
            NomeUsuario = getattr(Usuario, 'Nome_Usuario', getattr(Usuario, 'Nome', 'Anonimo')) if Usuario.is_authenticated else 'Anonimo'

            NovoLog = Tb_PLN_LogAcesso(
                Id_Usuario=IdUsuario,
                Nome_Usuario=NomeUsuario,
                Rota_Acessada=Rota,
                Metodo_Http=Metodo,
                Ip_Origem=Ip,
                Permissao_Exigida=Chave,
                Acesso_Permitido=Permitido
            )
            Sessao.add(NovoLog)
            Sessao.commit()
        except Exception as e:
            LogService.Error("PermissaoService", "Falha ao gravar log de acesso", e)
        finally:
            Sessao.close()

    # --- NOVO MÉTODO AUXILIAR ---
    @staticmethod
    def ObterCategoriaPermissao(ChavePermissao):
        """Busca o nome da categoria apenas para exibir no erro"""
        Sessao = ObterSessaoSqlServer()
        Categoria = "Geral"
        try:
            Perm = Sessao.query(Tb_PLN_Permissao).filter_by(Chave_Permissao=ChavePermissao).first()
            if Perm and Perm.Categoria_Permissao:
                Categoria = Perm.Categoria_Permissao
        except:
            pass
        finally:
            Sessao.close()
        return Categoria

# --- O DECORATOR ---
def RequerPermissao(ChavePermissao):
    def Decorator(F):
        @wraps(F)
        def Wrapper(*args, **kwargs):
            
            Permitido = PermissaoService.VerificarPermissao(current_user, ChavePermissao)
            
            PermissaoService.RegistrarLog(
                Usuario=current_user,
                Rota=request.path,
                Metodo=request.method,
                Ip=request.remote_addr,
                Chave=ChavePermissao,
                Permitido=Permitido
            )

            if not Permitido:
                # Busca a categoria para enriquecer a mensagem
                Categoria = PermissaoService.ObterCategoriaPermissao(ChavePermissao)
                
                flash(f"Acesso Negado. Você precisa de permissão no módulo '{Categoria}' para acessar este recurso.", "danger")
                
                return redirect(url_for('Dashboard') if current_user.is_authenticated else url_for('Auth.Login'))
            
            return F(*args, **kwargs)
        return Wrapper
    return Decorator