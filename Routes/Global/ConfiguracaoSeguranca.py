import os
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from collections import defaultdict

# Conexões do ConnectAir
from Conexoes import ObterSessaoSqlServer

# Models do ConnectAir
from Models.SQL_SERVER.Permissoes import Tb_PLN_Permissao, Tb_PLN_PermissaoGrupo, Tb_PLN_PermissaoUsuario, Tb_PLN_Sistema
from Models.SQL_SERVER.Usuario import Usuario, UsuarioGrupo  # Ajuste os nomes dos models conforme o seu sistema

# Service que acabamos de atualizar
from Services.PermissaoService import PermissaoService, RequerPermissao

SISTEMA_ID = int(os.getenv("SISTEMA_ID", 1))

# Criando o Blueprint 'Seguranca' (Mesmo nome usado nos url_for do HTML)
Seguranca_BP = Blueprint('Seguranca', __name__, url_prefix='/Seguranca')

@Seguranca_BP.route('/Permissoes')
@login_required
@RequerPermissao('SISTEMA.CONFIGURACOES.VISUALIZAR') # Ajuste a chave conforme sua necessidade
def Index():
    Sessao = ObterSessaoSqlServer()
    try:
        # Busca Dados Gerais de Grupos
        Grupos = Sessao.query(UsuarioGrupo).order_by(UsuarioGrupo.Sigla_UsuarioGrupo).all()
        
        # Busca Usuários fazendo o Join com o Grupo (Igual estava antes)
        Usuarios = Sessao.query(
            Usuario.Codigo_Usuario, 
            Usuario.Nome_Usuario, 
            Usuario.Login_Usuario, 
            UsuarioGrupo.Sigla_UsuarioGrupo.label('Nome_UsuarioGrupo')
        ).join(
            UsuarioGrupo, 
            Usuario.codigo_usuariogrupo == UsuarioGrupo.codigo_usuariogrupo
        ).order_by(Usuario.Nome_Usuario).all()
        
        # Busca todas as permissões deste sistema
        Permissoes = Sessao.query(Tb_PLN_Permissao).filter_by(Id_Sistema=SISTEMA_ID).order_by(
            Tb_PLN_Permissao.Categoria_Permissao, 
            Tb_PLN_Permissao.Descricao_Permissao
        ).all()
        
        # Agrupa permissões por categoria para a tela
        PermissoesPorCategoria = defaultdict(list)
        for perm in Permissoes:
            categoria = perm.Categoria_Permissao or 'Geral'
            PermissoesPorCategoria[categoria].append(perm)

        # Checa se o usuário atual pode editar/criar (para desabilitar/habilitar botões no HTML)
        PodeEditar = PermissaoService.VerificarPermissao(current_user, 'SISTEMA.CONFIGURACOES.EDITAR')
        PodeCriar = PermissaoService.VerificarPermissao(current_user, 'SISTEMA.CONFIGURACOES.CRIAR')

        return render_template('Pages/Configs/Permissoes.html', 
                               Usuarios=Usuarios, 
                               Grupos=Grupos, 
                               PermissoesPorCategoria=PermissoesPorCategoria,
                               PodeEditar=PodeEditar,
                               PodeCriar=PodeCriar)
    finally:
        Sessao.close()

@Seguranca_BP.route('/Permissoes/Criar', methods=['POST'])
@login_required
@RequerPermissao('SISTEMA.CONFIGURACOES.CRIAR')
def CriarNovaPermissao():
    modulo = request.form.get('modulo', '').upper().strip().replace(' ', '_')
    acao = request.form.get('acao', '').upper().strip()
    excecao = request.form.get('excecao', '').upper().strip().replace(' ', '_')
    descricao = request.form.get('descricao', '').strip()

    if not modulo or not acao or not descricao:
        flash("Preencha todos os campos obrigatórios.", "danger")
        return redirect(url_for('Seguranca.Index'))

    # Monta a chave da permissão no padrão: SISTEMA.MODULO.ACAO ou SISTEMA.MODULO.EXCECAO.ACAO
    chave = f"{modulo}.{excecao}.{acao}" if excecao else f"{modulo}.{acao}"

    Sessao = ObterSessaoSqlServer()
    try:
        # Verifica se já existe
        existe = Sessao.query(Tb_PLN_Permissao).filter_by(Id_Sistema=SISTEMA_ID, Chave_Permissao=chave).first()
        if existe:
            flash(f"A permissão com a chave '{chave}' já existe!", "warning")
            return redirect(url_for('Seguranca.Index'))

        NovaPermissao = Tb_PLN_Permissao(
            Id_Sistema=SISTEMA_ID,
            Chave_Permissao=chave,
            Descricao_Permissao=descricao,
            Categoria_Permissao=modulo
        )
        Sessao.add(NovaPermissao)
        Sessao.commit()
        flash("Permissão criada com sucesso!", "success")
        
    except Exception as e:
        Sessao.rollback()
        flash(f"Erro ao criar permissão: {str(e)}", "danger")
    finally:
        Sessao.close()

    return redirect(url_for('Seguranca.Index'))

@Seguranca_BP.route('/Api/AcessosGrupo', methods=['GET'])
@login_required
def BuscarAcessosGrupo():
    id_grupo = request.args.get('idGrupo')
    if not id_grupo: return jsonify({"erro": "ID do grupo não informado"}), 400

    Sessao = ObterSessaoSqlServer()
    try:
        vinculos = Sessao.query(Tb_PLN_PermissaoGrupo).filter_by(Codigo_UsuarioGrupo=id_grupo).all()
        ids_ativos = [v.Id_Permissao for v in vinculos]
        return jsonify({"ids_ativos": ids_ativos})
    finally:
        Sessao.close()

@Seguranca_BP.route('/Api/AcessosUsuario', methods=['GET'])
@login_required
def BuscarAcessosUsuario():
    id_usuario = request.args.get('idUsuario')
    if not id_usuario: return jsonify({"erro": "ID do usuário não informado"}), 400

    Sessao = ObterSessaoSqlServer()
    try:
        usuario = Sessao.query(Usuario).filter_by(Codigo_Usuario=id_usuario).first()
        if not usuario: return jsonify({"erro": "Usuário não encontrado"}), 404

        id_grupo = usuario.codigo_usuariogrupo
        
        # Permissões herdadas do grupo
        heranca = []
        if id_grupo:
            vinculos_grupo = Sessao.query(Tb_PLN_PermissaoGrupo).filter_by(Codigo_UsuarioGrupo=id_grupo).all()
            heranca = [v.Id_Permissao for v in vinculos_grupo]

        # Permissões/Exceções específicas do usuário
        vinculos_usuario = Sessao.query(Tb_PLN_PermissaoUsuario).filter_by(Codigo_Usuario=id_usuario).all()
        
        permitidos = [v.Id_Permissao for v in vinculos_usuario if v.Conceder]
        bloqueados = [v.Id_Permissao for v in vinculos_usuario if not v.Conceder]

        return jsonify({
            "heranca_grupo": heranca,
            "usuario_permitidos": permitidos,
            "usuario_bloqueados": bloqueados
        })
    finally:
        Sessao.close()

@Seguranca_BP.route('/Api/SalvarVinculo', methods=['POST'])
@login_required
@RequerPermissao('SISTEMA.CONFIGURACOES.EDITAR')
def SalvarVinculo():
    dados = request.get_json()
    tipo = dados.get('Tipo') # 'Grupo' ou 'Usuario'
    id_alvo = dados.get('IdAlvo')
    id_permissao = dados.get('IdPermissao')
    acao = dados.get('Acao') # 'Adicionar', 'Remover', 'Permitir', 'Bloquear', 'Resetar'

    Sessao = ObterSessaoSqlServer()
    try:
        if tipo == 'Grupo':
            vinculo = Sessao.query(Tb_PLN_PermissaoGrupo).filter_by(Codigo_UsuarioGrupo=id_alvo, Id_Permissao=id_permissao).first()
            
            if acao == 'Adicionar' and not vinculo:
                Sessao.add(Tb_PLN_PermissaoGrupo(Codigo_UsuarioGrupo=id_alvo, Id_Permissao=id_permissao))
            elif acao == 'Remover' and vinculo:
                Sessao.delete(vinculo)
                
        elif tipo == 'Usuario':
            vinculo = Sessao.query(Tb_PLN_PermissaoUsuario).filter_by(Codigo_Usuario=id_alvo, Id_Permissao=id_permissao).first()

            if acao == 'Resetar':
                if vinculo: Sessao.delete(vinculo)
            else:
                conceder = (acao == 'Permitir')
                if vinculo:
                    vinculo.Conceder = conceder
                else:
                    Sessao.add(Tb_PLN_PermissaoUsuario(Codigo_Usuario=id_alvo, Id_Permissao=id_permissao, Conceder=conceder))

        Sessao.commit()
        return jsonify({"sucesso": True})
    except Exception as e:
        Sessao.rollback()
        return jsonify({"sucesso": False, "erro": str(e)})
    finally:
        Sessao.close()