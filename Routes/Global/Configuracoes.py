from flask import Blueprint, render_template, request, jsonify, flash, url_for
from flask_login import login_required
from sqlalchemy import or_
from Services.PermissaoService import RequerPermissao
from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Permissoes import Tb_PLN_Permissao, Tb_PLN_PermissaoGrupo, Tb_PLN_PermissaoUsuario
from Models.SQL_SERVER.Usuario import UsuarioGrupo, Usuario

ConfiguracoesBp = Blueprint('Configuracoes', __name__)

@ConfiguracoesBp.route('/')
@login_required
@RequerPermissao('sistema.configuracoes.visualizar')
def Index():
    return render_template('Configuracoes/Index.html')

# --- ROTA PRINCIPAL (VIEW) ---
@ConfiguracoesBp.route('/Permissoes')
@login_required
@RequerPermissao('sistema.configuracoes.visualizar')
def Permissoes():
    Sessao = ObterSessaoSqlServer()
    try:
        # Busca Dados Gerais de Grupos
        Grupos = Sessao.query(UsuarioGrupo).order_by(UsuarioGrupo.Sigla_UsuarioGrupo).all()
        
        # Busca Usuários (CORRIGIDO para compatibilidade com o modelo Usuario.py)
        # Usamos .label('Nome_UsuarioGrupo') para manter compatibilidade com o template
        Usuarios = Sessao.query(
            Usuario.Codigo_Usuario, 
            Usuario.Nome_Usuario, 
            Usuario.Login_Usuario, 
            UsuarioGrupo.Sigla_UsuarioGrupo.label('Nome_UsuarioGrupo')
        ).join(
            UsuarioGrupo, 
            Usuario.codigo_usuariogrupo == UsuarioGrupo.codigo_usuariogrupo
        ).order_by(Usuario.Nome_Usuario).all()

        # Busca todas as permissões e agrupa
        ListaPermissoes = Sessao.query(Tb_PLN_Permissao).order_by(
            Tb_PLN_Permissao.Categoria_Permissao, 
            Tb_PLN_Permissao.Descricao_Permissao
        ).all()
        
        PermissoesPorCategoria = {}
        for p in ListaPermissoes:
            cat = p.Categoria_Permissao or 'Geral'
            if cat not in PermissoesPorCategoria: PermissoesPorCategoria[cat] = []
            PermissoesPorCategoria[cat].append(p)
            
        return render_template('Configuracoes/Permissoes.html', 
                             Grupos=Grupos,
                             Usuarios=Usuarios,
                             PermissoesPorCategoria=PermissoesPorCategoria)
    finally:
        Sessao.close()

# --- API: BUSCAR ACESSOS DE UM GRUPO ---
@ConfiguracoesBp.route('/Permissoes/BuscarAcessosGrupo')
@login_required
@RequerPermissao('sistema.configuracoes.visualizar')
def BuscarAcessosGrupo():
    IdGrupo = request.args.get('idGrupo')
    Sessao = ObterSessaoSqlServer()
    try:
        Vinculos = Sessao.query(Tb_PLN_PermissaoGrupo).filter_by(Codigo_UsuarioGrupo=IdGrupo).all()
        Ids = [v.Id_Permissao for v in Vinculos]
        return jsonify({'ids_ativos': Ids})
    finally:
        Sessao.close()

# --- API: BUSCAR ACESSOS DE UM USUÁRIO (COM HERANÇA) ---
@ConfiguracoesBp.route('/Permissoes/BuscarAcessosUsuario')
@login_required
@RequerPermissao('sistema.configuracoes.visualizar')
def BuscarAcessosUsuario():
    IdUsuario = request.args.get('idUsuario')
    Sessao = ObterSessaoSqlServer()
    try:
        User = Sessao.query(Usuario).filter_by(Codigo_Usuario=IdUsuario).first()
        if not User: return jsonify({'erro': 'Usuário não encontrado'}), 404

        # 1. Permissões do Grupo (Herança)
        # CORREÇÃO: Usando codigo_usuariogrupo conforme seu Model
        PermissoesGrupo = Sessao.query(Tb_PLN_PermissaoGrupo.Id_Permissao)\
            .filter(Tb_PLN_PermissaoGrupo.Codigo_UsuarioGrupo == User.codigo_usuariogrupo).all()
        ListaGrupo = [p[0] for p in PermissoesGrupo]

        # 2. Permissões Individuais (Overrides)
        # Conceder = 1 (Permitir forçado), Conceder = 0 (Bloquear forçado)
        Overrides = Sessao.query(Tb_PLN_PermissaoUsuario).filter_by(Codigo_Usuario=IdUsuario).all()
        
        ListaPermitidos = [o.Id_Permissao for o in Overrides if o.Conceder == True]
        ListaBloqueados = [o.Id_Permissao for o in Overrides if o.Conceder == False]

        return jsonify({
            'heranca_grupo': ListaGrupo, 
            'usuario_permitidos': ListaPermitidos, 
            'usuario_bloqueados': ListaBloqueados
        })
    finally:
        Sessao.close()

# --- API: SALVAR VÍNCULO (GRUPO OU USUÁRIO) ---
@ConfiguracoesBp.route('/Permissoes/Salvar', methods=['POST'])
@login_required
@RequerPermissao('sistema.configuracoes.editar')
def SalvarVinculo():
    Dados = request.get_json()
    Tipo = Dados.get('Tipo')
    IdAlvo = Dados.get('IdAlvo')
    IdPermissao = Dados.get('IdPermissao')
    Acao = Dados.get('Acao') 
    
    Sessao = ObterSessaoSqlServer()
    try:
        if Tipo == 'Grupo':
            Vinculo = Sessao.query(Tb_PLN_PermissaoGrupo).filter_by(Codigo_UsuarioGrupo=IdAlvo, Id_Permissao=IdPermissao).first()
            
            if Acao == 'Adicionar' and not Vinculo:
                Novo = Tb_PLN_PermissaoGrupo(Codigo_UsuarioGrupo=IdAlvo, Id_Permissao=IdPermissao)
                Sessao.add(Novo)
            elif Acao == 'Remover' and Vinculo:
                Sessao.delete(Vinculo)
                
        elif Tipo == 'Usuario':
            Vinculo = Sessao.query(Tb_PLN_PermissaoUsuario).filter_by(Codigo_Usuario=IdAlvo, Id_Permissao=IdPermissao).first()
            
            if Acao == 'Resetar':
                if Vinculo: Sessao.delete(Vinculo)
            
            else:
                EstadoBoleano = True if Acao == 'Permitir' else False
                
                if not Vinculo:
                    Novo = Tb_PLN_PermissaoUsuario(
                        Codigo_Usuario=IdAlvo, 
                        Id_Permissao=IdPermissao, 
                        Conceder=EstadoBoleano
                    )
                    Sessao.add(Novo)
                else:
                    Vinculo.Conceder = EstadoBoleano

        Sessao.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)})
    finally:
        Sessao.close()

@ConfiguracoesBp.route('/Permissoes/CriarNova', methods=['POST'])
@login_required
@RequerPermissao('sistema.configuracoes.criar')
def CriarNovaPermissao():
    Dados = request.form
    # Remove espaços extras e força minúsculo para garantir padrão
    Chave = Dados.get('chave').lower().strip() 
    
    Sessao = ObterSessaoSqlServer()
    try:
        # 1. VERIFICAÇÃO PRÉVIA: Checa se a chave já existe no banco
        PermissaoExistente = Sessao.query(Tb_PLN_Permissao).filter_by(Chave_Permissao=Chave).first()
        
        if PermissaoExistente:
            flash(f'Atenção: A chave de permissão "{Chave}" já está cadastrada.', 'warning')
        else:
            # 2. Se não existe, cria a nova
            Nova = Tb_PLN_Permissao(
                Chave_Permissao=Chave,
                Descricao_Permissao=Dados.get('descricao'),
                Categoria_Permissao=Dados.get('categoria')
            )
            Sessao.add(Nova)
            Sessao.commit()
            flash('Permissão criada com sucesso!', 'success')
            
    except Exception as e:
        # Captura outros erros genéricos (ex: banco fora do ar)
        flash(f'Erro técnico ao criar permissão: {str(e)}', 'danger')
    finally:
        Sessao.close()
    
    # Recarrega a página (seja sucesso ou erro)
    return Permissoes()