import os
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from collections import defaultdict

from Conexoes import ObterSessaoSqlServer
from Models.SQL_SERVER.Permissoes import Tb_Permissao, Tb_PermissaoGrupo, Tb_PermissaoUsuario, Tb_Sistema
from Models.SQL_SERVER.Usuario import Usuario, UsuarioGrupo  

from Services.PermissaoService import PermissaoService, RequerPermissao
from luftcore.extensions.flask_extension import require_ajax

sistemaId = int(os.getenv("SISTEMA_ID", 1))

Seguranca_BP = Blueprint('Seguranca', __name__, url_prefix='/Seguranca')

@Seguranca_BP.route('/Permissoes')
@login_required
@RequerPermissao('SISTEMA.SEGURANCA.VISUALIZAR')
def index():
    sessaoDb = ObterSessaoSqlServer()
    try:
        listaGrupos = sessaoDb.query(UsuarioGrupo).order_by(UsuarioGrupo.Sigla_UsuarioGrupo).all()
        
        listaUsuarios = sessaoDb.query(
            Usuario.Codigo_Usuario, 
            Usuario.Nome_Usuario, 
            Usuario.Login_Usuario, 
            UsuarioGrupo.Sigla_UsuarioGrupo.label('Nome_UsuarioGrupo')
        ).join(
            UsuarioGrupo, 
            Usuario.codigo_usuariogrupo == UsuarioGrupo.codigo_usuariogrupo
        ).order_by(Usuario.Nome_Usuario).all()
        
        listaPermissoes = sessaoDb.query(Tb_Permissao).filter_by(Id_Sistema=sistemaId).order_by(
            Tb_Permissao.Categoria_Permissao, 
            Tb_Permissao.Descricao_Permissao
        ).all()
        
        permissoesPorCategoria = defaultdict(list)
        for perm in listaPermissoes:
            categoriaPerm = perm.Categoria_Permissao or 'Geral'
            permissoesPorCategoria[categoriaPerm].append(perm)

        podeEditar = PermissaoService.VerificarPermissao(current_user, 'SISTEMA.CONFIGURACOES.EDITAR')
        podeCriar = PermissaoService.VerificarPermissao(current_user, 'SISTEMA.CONFIGURACOES.CRIAR')

        return render_template('Pages/Configs/Permissoes.html', 
                               Usuarios=listaUsuarios, 
                               Grupos=listaGrupos, 
                               PermissoesPorCategoria=permissoesPorCategoria,
                               PodeEditar=podeEditar,
                               PodeCriar=podeCriar)
    finally:
        sessaoDb.close()

@Seguranca_BP.route('/Permissoes/Criar', methods=['POST'])
@login_required
@RequerPermissao('SISTEMA.SEGURANCA.CRIAR')
def criarNovaPermissao():
    moduloReq = request.form.get('modulo', '').upper().strip().replace(' ', '_')
    acaoReq = request.form.get('acao', '').upper().strip()
    excecaoReq = request.form.get('excecao', '').upper().strip().replace(' ', '_')
    descricaoReq = request.form.get('descricao', '').strip()

    if not moduloReq or not acaoReq or not descricaoReq:
        flash("Preencha todos os campos obrigatórios.", "danger")
        return redirect(url_for('Seguranca.index'))

    chavePermissao = f"{moduloReq}.{excecaoReq}.{acaoReq}" if excecaoReq else f"{moduloReq}.{acaoReq}"

    sessaoDb = ObterSessaoSqlServer()
    try:
        permissaoExistente = sessaoDb.query(Tb_Permissao).filter_by(Id_Sistema=sistemaId, Chave_Permissao=chavePermissao).first()
        if permissaoExistente:
            flash(f"A permissão com a chave '{chavePermissao}' já existe!", "warning")
            return redirect(url_for('Seguranca.index'))

        novaPermissaoObj = Tb_Permissao(
            Id_Sistema=sistemaId,
            Chave_Permissao=chavePermissao,
            Descricao_Permissao=descricaoReq,
            Categoria_Permissao=moduloReq
        )
        sessaoDb.add(novaPermissaoObj)
        sessaoDb.commit()
        flash("Permissão criada com sucesso!", "success")
        
    except Exception as e:
        sessaoDb.rollback()
        flash(f"Erro ao criar permissão: {str(e)}", "danger")
    finally:
        sessaoDb.close()

    return redirect(url_for('Seguranca.index'))

@Seguranca_BP.route('/Api/AcessosGrupo', methods=['GET'])
@login_required
@require_ajax
@RequerPermissao('SISTEMA.SEGURANCA.VISUALIZAR')
def buscarAcessosGrupo():
    idGrupoReq = request.args.get('idGrupo')
    if not idGrupoReq: return jsonify({"erro": "ID do grupo não informado"}), 400

    sessaoDb = ObterSessaoSqlServer()
    try:
        vinculosGrupo = sessaoDb.query(Tb_PermissaoGrupo).filter_by(Codigo_UsuarioGrupo=idGrupoReq).all()
        idsAtivos = [vinculo.Id_Permissao for vinculo in vinculosGrupo]
        return jsonify({"ids_ativos": idsAtivos})
    finally:
        sessaoDb.close()

@Seguranca_BP.route('/Api/AcessosUsuario', methods=['GET'])
@login_required
@require_ajax
@RequerPermissao('SISTEMA.SEGURANCA.VISUALIZAR')
def buscarAcessosUsuario():
    idUsuarioReq = request.args.get('idUsuario')
    if not idUsuarioReq: return jsonify({"erro": "ID do usuário não informado"}), 400

    sessaoDb = ObterSessaoSqlServer()
    try:
        usuarioObj = sessaoDb.query(Usuario).filter_by(Codigo_Usuario=idUsuarioReq).first()
        if not usuarioObj: return jsonify({"erro": "Usuário não encontrado"}), 404

        idGrupoUser = usuarioObj.codigo_usuariogrupo
        
        permissoesHeranca = []
        if idGrupoUser:
            vinculosDoGrupo = sessaoDb.query(Tb_PermissaoGrupo).filter_by(Codigo_UsuarioGrupo=idGrupoUser).all()
            permissoesHeranca = [v.Id_Permissao for v in vinculosDoGrupo]

        vinculosDoUsuario = sessaoDb.query(Tb_PermissaoUsuario).filter_by(Codigo_Usuario=idUsuarioReq).all()
        
        permissoesAtivas = [v.Id_Permissao for v in vinculosDoUsuario if v.Conceder]
        permissoesBloqueadas = [v.Id_Permissao for v in vinculosDoUsuario if not v.Conceder]

        return jsonify({
            "heranca_grupo": permissoesHeranca,
            "usuario_permitidos": permissoesAtivas,
            "usuario_bloqueados": permissoesBloqueadas
        })
    finally:
        sessaoDb.close()

@Seguranca_BP.route('/Api/SalvarVinculo', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('SISTEMA.SEGURANCA.EDITAR')
def salvarVinculo():
    dadosRequisicao = request.get_json()
    tipoAlvo = dadosRequisicao.get('Tipo') 
    idAlvoReq = dadosRequisicao.get('IdAlvo')
    idPermissaoReq = dadosRequisicao.get('IdPermissao')
    acaoRequerida = dadosRequisicao.get('Acao') 

    sessaoDb = ObterSessaoSqlServer()
    try:
        if tipoAlvo == 'Grupo':
            vinculoExistente = sessaoDb.query(Tb_PermissaoGrupo).filter_by(Codigo_UsuarioGrupo=idAlvoReq, Id_Permissao=idPermissaoReq).first()
            
            if acaoRequerida == 'Adicionar' and not vinculoExistente:
                sessaoDb.add(Tb_PermissaoGrupo(Codigo_UsuarioGrupo=idAlvoReq, Id_Permissao=idPermissaoReq))
            elif acaoRequerida == 'Remover' and vinculoExistente:
                sessaoDb.delete(vinculoExistente)
                
        elif tipoAlvo == 'Usuario':
            vinculoExistente = sessaoDb.query(Tb_PermissaoUsuario).filter_by(Codigo_Usuario=idAlvoReq, Id_Permissao=idPermissaoReq).first()

            if acaoRequerida == 'Resetar':
                if vinculoExistente: sessaoDb.delete(vinculoExistente)
            else:
                concederAcesso = (acaoRequerida == 'Permitir')
                if vinculoExistente:
                    vinculoExistente.Conceder = concederAcesso
                else:
                    sessaoDb.add(Tb_PermissaoUsuario(Codigo_Usuario=idAlvoReq, Id_Permissao=idPermissaoReq, Conceder=concederAcesso))

        sessaoDb.commit()
        return jsonify({"sucesso": True})
    except Exception as e:
        sessaoDb.rollback()
        return jsonify({"sucesso": False, "erro": str(e)})
    finally:
        sessaoDb.close()