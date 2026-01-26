# Documentação Técnica - Consolidação de CTCs

## 📦 Visão Geral

Esta documentação descreve a implementação da funcionalidade de **consolidação automática de CTCs** no módulo de planejamento do sistema T-FlightOps. A funcionalidade identifica e agrupa CTCs com mesma origem e destino para otimizar o planejamento de voos e cargas.

---

## 🎯 Objetivo

Quando um usuário clicar em "Planejar" para um CTC específico, o sistema deve:

1. Identificar a origem e destino do CTC selecionado
2. Buscar automaticamente todos os outros CTCs do mesmo dia com mesma origem/destino
3. Consolidar essas informações e exibir totais agregados
4. Permitir visualização detalhada de cada CTC consolidado
5. Preparar estrutura para expansão futura (valor tarifa, tipo produto, etc.)

---

## 🔧 Implementação Backend

### 1. Service Layer - `PlanejamentoService.py`

#### Novo Método: `BuscarCtcsConsolidaveis()`

**Localização:** `Services/PlanejamentoService.py` (linha ~240)

**Assinatura:**
```python
@staticmethod
def BuscarCtcsConsolidaveis(cidade_origem, uf_origem, cidade_destino, uf_destino, 
                            data_base, filial_excluir=None, ctc_excluir=None)
```

**Parâmetros:**
- `cidade_origem`: Cidade de origem do CTC
- `uf_origem`: UF de origem
- `cidade_destino`: Cidade de destino
- `uf_destino`: UF de destino
- `data_base`: Data de referência (date ou datetime)
- `filial_excluir`: Filial do CTC principal (opcional, para excluir da lista)
- `ctc_excluir`: Número do CTC principal (opcional, para excluir da lista)

**Retorno:**
Lista de dicionários contendo:
```python
{
    'filial': str,
    'ctc': str,
    'serie': str,
    'data_emissao': str,
    'hora_emissao': str,
    'prioridade': str,
    'remetente': str,
    'destinatario': str,
    'volumes': int,
    'peso_taxado': float,
    'peso_real': float,
    'val_mercadoria': float,
    'frete_total': float,
    'qtd_notas': int,
    'tabela_frete': str,
    'natureza': str,
    'especie': str,
    # Campos preparados para expansão futura
    'tipo_produto': str,
    'valor_tarifa': float
}
```

**Lógica de Busca:**
1. Normaliza a data para buscar todo o dia (00:00 até 23:59)
2. Normaliza strings de cidade/UF para comparação case-insensitive
3. Filtra CTCs com:
   - Mesma data de emissão
   - Modal AÉREO
   - Tipo de documento diferente de 'COB'
   - Mesma origem (cidade + UF)
   - Mesmo destino (cidade + UF)
4. Exclui o CTC principal da lista (se fornecido)
5. Ordena por data e hora de emissão (mais recentes primeiro)

**Imports Adicionados:**
```python
from sqlalchemy import desc, func
```

---

### 2. Route Layer - `Planejamento.py`

#### Modificação: Rota `MontarPlanejamento()`

**Localização:** `Routes/Planejamento.py` (linha ~48)

**Alterações:**

1. **Nova Etapa de Consolidação** (após Geografia, antes de Aeroportos):
```python
# 3. Consolidação - Busca CTCs com mesma origem/destino
CtcsConsolidados = PlanejamentoService.BuscarCtcsConsolidaveis(
    DadosCtc['origem_cidade'], 
    DadosCtc['origem_uf'],
    DadosCtc['destino_cidade'], 
    DadosCtc['destino_uf'],
    DadosCtc['data_emissao_real'],
    filial,
    ctc
)
```

2. **Cálculo de Totais Consolidados**:
```python
TotaisConsolidados = {
    'qtd_ctcs': len(CtcsConsolidados) + 1,  # +1 para incluir o CTC principal
    'volumes_total': DadosCtc['volumes'] + sum(c['volumes'] for c in CtcsConsolidados),
    'peso_total': DadosCtc['peso'] + sum(c['peso_taxado'] for c in CtcsConsolidados),
    'valor_total': float(DadosCtc['valor']) + sum(c['val_mercadoria'] for c in CtcsConsolidados),
    'notas_total': sum(c['qtd_notas'] for c in CtcsConsolidados) + 1
}
```

3. **Novos Parâmetros no Template**:
```python
return render_template('Planejamento/Editor.html', 
                       Ctc=DadosCtc, 
                       Origem=CoordOrigem, Destino=CoordDestino,
                       AeroOrigem=AeroOrigem, AeroDestino=AeroDestino,
                       Rotas=RotasSugeridas,
                       CtcsConsolidados=CtcsConsolidados,      # NOVO
                       TotaisConsolidados=TotaisConsolidados)  # NOVO
```

---

## 🎨 Implementação Frontend

### 1. Card de Consolidação no Header

**Localização:** `Templates/Planejamento/Editor.html` (linha ~351)

**Componente:**
- Badge visual com gradiente azul/roxo
- Ícone de "stack" (pilha)
- Grid 4 colunas com totais: CTCs, Volumes, Peso, Notas
- Botão para expandir modal com lista completa

**Estilo:**
- Background: Gradiente linear azul/roxo com transparência
- Border: Azul semi-transparente
- Responsivo e integrado ao design glassmorphism existente

**Condicional de Exibição:**
```jinja2
{% if CtcsConsolidados and CtcsConsolidados|length > 0 %}
```

---

### 2. Modal de Consolidação

**Localização:** `Templates/Planejamento/Editor.html` (linha ~430)

**Estrutura:**

#### Header
- Título com ícone
- Contador de CTCs consolidáveis
- Botão de fechar (X)

#### Seção de Totais
- Grid 5 colunas: Total CTCs, Volumes, Peso Total, Valor Total, Notas
- Background com gradiente sutil
- Tipografia destacada (2rem, font-weight 800)

#### Lista de CTCs
- Cards interativos com hover effect
- Layout em grid com 3 seções por card:
  1. **Badge CTC**: Número do CTC com gradiente azul/roxo
  2. **Informações**: Remetente, Destinatário, Data de Emissão
  3. **KPIs**: Volumes, Peso, Notas, Valor

#### Footer
- Dica de uso (clique para ver detalhes)
- Botão de fechar

**Interatividade:**
- Clique em qualquer card abre o modal de detalhes do CTC (`AbrirModalGlobal()`)
- Hover effects: elevação, mudança de cor de borda, sombra
- Scroll interno para listas longas

---

### 3. Funções JavaScript

**Localização:** `Templates/Planejamento/Editor.html` (linha ~602)

```javascript
function toggleConsolidacao() {
    const modal = document.getElementById('modal-consolidacao');
    if (modal) {
        modal.style.display = modal.style.display === 'none' ? 'flex' : 'none';
    }
}

function fecharModalConsolidacao() {
    const modal = document.getElementById('modal-consolidacao');
    if (modal) modal.style.display = 'none';
}
```

---

## 🔮 Preparação para Expansão Futura

### Campos Preparados no Backend

O método `BuscarCtcsConsolidaveis()` já retorna campos preparados para funcionalidades futuras:

```python
'tipo_produto': to_str(c.natureza),      # Placeholder - pode ser refinado
'valor_tarifa': to_float(c.fretetotalbruto),  # Placeholder
'tabela_frete': to_str(c.tabfrete),
'natureza': to_str(c.natureza),
'especie': to_str(c.especie),
```

### Campos Ocultos no Frontend

Cada card do modal possui uma `<div>` oculta com data-attributes para expansão:

```html
<div style="display: none;" 
     data-tipo-produto="{{ ctc_cons.tipo_produto }}" 
     data-valor-tarifa="{{ ctc_cons.valor_tarifa }}" 
     data-tabela-frete="{{ ctc_cons.tabela_frete }}" 
     data-natureza="{{ ctc_cons.natureza }}" 
     data-especie="{{ ctc_cons.especie }}">
</div>
```

**Uso Futuro:**
- Filtros por tipo de produto
- Cálculo de tarifas consolidadas
- Agrupamento por natureza/espécie
- Análise de rentabilidade por tabela de frete

---

## 📊 Fluxo de Dados

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Usuário clica em "Planejar" para CTC X                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Route: MontarPlanejamento(filial, serie, ctc)           │
│    - Obtém dados do CTC principal                          │
│    - Busca coordenadas geográficas                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Service: BuscarCtcsConsolidaveis()                       │
│    - Query SQL com filtros de origem/destino/data          │
│    - Exclui CTC principal da lista                         │
│    - Formata dados para frontend                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Route: Calcula Totais Consolidados                      │
│    - Soma volumes, peso, valor, notas                      │
│    - Conta quantidade de CTCs (+1 do principal)            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Template: Renderiza Editor.html                         │
│    - Card de consolidação no header (se houver CTCs)       │
│    - Modal oculto com lista completa                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Usuário clica em "Ver X CTCs Consolidados"              │
│    - toggleConsolidacao() exibe modal                      │
│    - Lista interativa com todos os CTCs                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧪 Testes Recomendados

### Teste 1: Consolidação Básica
1. Criar 3 CTCs com mesma origem/destino no mesmo dia
2. Clicar em "Planejar" em um deles
3. Verificar se o card de consolidação aparece com "3 CTCs"
4. Verificar se os totais estão corretos

### Teste 2: Sem Consolidação
1. Criar 1 CTC único (sem outros com mesma origem/destino)
2. Clicar em "Planejar"
3. Verificar que o card de consolidação NÃO aparece

### Teste 3: Modal de Detalhes
1. Abrir planejamento com consolidação
2. Clicar em "Ver X CTCs Consolidados"
3. Verificar que o modal abre corretamente
4. Clicar em um CTC da lista
5. Verificar que o modal de detalhes do CTC abre

### Teste 4: Normalização de Strings
1. Criar CTCs com variações de case: "SÃO PAULO" vs "São Paulo"
2. Verificar que a consolidação funciona corretamente

### Teste 5: Performance
1. Criar 50+ CTCs com mesma origem/destino
2. Verificar tempo de resposta da rota
3. Verificar scroll do modal

---

## 🚀 Melhorias Futuras Sugeridas

### Curto Prazo
- [ ] Adicionar filtros no modal (por prioridade, valor, peso)
- [ ] Permitir seleção múltipla de CTCs para consolidação
- [ ] Exportar lista de CTCs consolidados (Excel/PDF)

### Médio Prazo
- [ ] Implementar cálculo de tarifa consolidada
- [ ] Adicionar agrupamento por tipo de produto
- [ ] Criar dashboard de consolidação (estatísticas)
- [ ] Notificações automáticas de oportunidades de consolidação

### Longo Prazo
- [ ] Machine Learning para sugestão de consolidações
- [ ] Otimização de rotas considerando consolidação
- [ ] Integração com sistema de tarifação dinâmica
- [ ] API para consolidação automática via integração externa

---

## 📝 Notas Técnicas

### Considerações de Performance
- A query de consolidação usa índices em `data`, `cidade_orig`, `uf_orig`, `cidade_dest`, `uf_dest`
- Recomenda-se criar índice composto para otimização:
  ```sql
  CREATE INDEX idx_ctc_consolidacao 
  ON tb_ctc_esp (data, cidade_orig, uf_orig, cidade_dest, uf_dest, modal);
  ```

### Compatibilidade
- SQLAlchemy: 1.4+
- Flask: 2.0+
- Jinja2: 3.0+
- Navegadores: Chrome 90+, Firefox 88+, Safari 14+

### Segurança
- Todos os parâmetros são sanitizados via SQLAlchemy ORM
- Não há concatenação direta de strings SQL
- Filtros case-insensitive usam funções SQL nativas (UPPER, TRIM)

---

## 👥 Autores e Contribuidores

- **Implementação Inicial**: Manus AI Agent
- **Data**: Janeiro 2026
- **Versão**: 1.0.0

---

## 📄 Licença

Este código segue a mesma licença do projeto T-FlightOps.
