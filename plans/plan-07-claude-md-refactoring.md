# Plan 07: CLAUDE.md Refactoring & Code Quality Audit

## 📋 Contexto

O CLAUDE.md atual tem **1051 linhas** e foi criado como design inicial. Durante o desenvolvimento rápido para lançamento, muitas features foram implementadas sem atualizar o documento, resultando em:

- ❌ Desatualização com o código real
- ❌ Excesso de informação (sobrecarga de contexto)
- ❌ Possíveis inconsistências arquiteturais não documentadas
- ❌ Duplicação de código (violação do DRY)
- ❌ Testes não seguindo 100% o TDD pattern

**CLAUDE.md é a memória da AI** - precisa ser:
- ✅ Conciso e direto
- ✅ Refletir o estado REAL do código
- ✅ Priorizar informações de alta qualidade contextual
- ✅ Incluir guidelines de como se auto-atualizar

## 🎯 Objetivo

1. **Auditar código** vs CLAUDE.md atual
2. **Criar novo CLAUDE.md** enxuto e atualizado (meta: < 800 linhas)
3. **Documentar débitos técnicos** em arquivo separado
4. **Estabelecer processo** de manutenção do CLAUDE.md

## 🔬 Metodologia de Auditoria

**IMPORTANTE - Abordagem de Leitura Completa:**

Para evitar perda de contexto durante compactação:
1. ✅ **LER ARQUIVOS COMPLETOS** - sem usar offset/limit
2. ✅ **DOCUMENTAR TUDO** em `AUDIT-LOG.md` passo a passo
3. ✅ **REGISTRAR DESCOBERTAS** imediatamente
4. ✅ **VALIDAR COM CÓDIGO REAL** antes de documentar

**Estrutura do AUDIT-LOG.md:**
```markdown
## [TIMESTAMP] - Arquivo X
### O que CLAUDE.md diz:
- Claim 1
- Claim 2

### O que o código REAL mostra:
- Reality 1
- Reality 2

### Descobertas:
- ✅ Confirmado
- ❌ Desatualizado
- ⚠️ Parcialmente correto

### Ações necessárias:
- [ ] Atualizar CLAUDE-NEW-TEMPLATE.md seção Y
- [ ] Adicionar ao TECH-DEBT.md: issue Z
```

Esta abordagem garante que o histórico de auditoria seja preservado mesmo se o contexto for compactado.

## 📊 Escopo

### Etapa 1: Auditoria (Análise)

**Arquivos a revisar:**
```
src/
├── orchestrator.py       # Core - verificar responsabilidades
├── storage.py           # State/Config/Secrets - v0.2.0 simplificado?
├── app_registry.py      # Dependências - fonte única de verdade?
├── app_deployer.py      # Deploy logic - DRY violations?
├── server_setup.py      # DNS-first architecture?
├── job_manager.py       # Async jobs
├── job_executor.py      # Background processing
├── ssh_manager.py       # Key management
├── providers/hetzner.py # Cloud provider
├── integrations/        # Portainer, Cloudflare
└── api/                 # FastAPI endpoints
```

**Questões a responder:**
1. ✅ Storage está realmente usando apenas state.json + vault? (config.yaml foi removido?)
2. ✅ DNS é obrigatório no setup-server?
3. ✅ Infrastructure (Traefik+Portainer) é app ou parte do setup?
4. ✅ AppRegistry resolve dependências dos YAMLs?
5. ✅ Testes seguem os padrões definidos? (< 3s unit, mocks corretos)
6. ⚠️ Há duplicação de lógica entre módulos?
7. ⚠️ APIs seguem os endpoints documentados?

### Etapa 2: Criação do Novo CLAUDE.md

**Estrutura proposta (enxuta):**

```markdown
# LivChat Setup - AI Context Document

## Meta-Documentation
- Como manter este documento
- Quando atualizar
- Limites de tamanho (< 800 linhas)

## Architecture (REAL STATE)
- High-level diagram (ASCII)
- Tech stack (apenas decisões finais)
- Storage model (state.json + vault)

## Core Components (IMPLEMENTED)
- Orchestrator
- Storage Manager
- App Registry
- App Deployer
- Server Setup
- Job System

## File Structure (CURRENT)
- Estrutura real de diretórios
- Onde adicionar novos componentes

## Development Guidelines
- TDD patterns
- Mock standards
- Planning process

## API & MCP Tools
- Endpoints implementados
- MCP tools (14 tools)

## Deployment Workflow
- Fluxo real: create → setup → deploy
- DNS-first approach

## Technical Debt & TODOs
- Link para TECH-DEBT.md

## Status
- Version: 0.1.5
- Last Updated: 2025-10-19
```

**Seções REMOVIDAS (migrar para docs/):**
- ❌ Histórico detalhado de decisões
- ❌ Exemplos extensos de código
- ❌ Planos futuros detalhados (Q1-Q4 2025)
- ❌ Open Questions (mover para TECH-DEBT.md)

### Etapa 3: TECH-DEBT.md

**Criar arquivo separado para:**
```markdown
# Technical Debt & Code Quality

## Architecture Issues
- [ ] Duplicação entre X e Y
- [ ] Violação DRY em Z

## Test Coverage Gaps
- [ ] Module X precisa testes
- [ ] Integration test para workflow Y

## Refactoring Needed
- [ ] Simplificar classe W
- [ ] Extrair lógica comum de A e B

## Performance
- [ ] Otimizar consulta N+1 em lista de apps
- [ ] Cache para app registry

## Documentation
- [ ] API docs incompletos
- [ ] Falta docstring em métodos críticos
```

### Etapa 4: Guidelines de Manutenção

**Adicionar ao novo CLAUDE.md:**

```markdown
## 📝 How to Update This Document

### When to Update
- ✅ After implementing new core feature
- ✅ After architectural decision
- ✅ After changing file structure
- ❌ NOT for minor bug fixes
- ❌ NOT for adding single function

### Update Process
1. Read entire document first
2. Identify outdated section
3. Update with REAL implementation (check code!)
4. Keep it concise (favor bullet points)
5. Move details to docs/ or TECH-DEBT.md
6. Verify total lines < 800

### Quality Checklist
- [ ] Reflects current code state
- [ ] No outdated information
- [ ] Clear and actionable
- [ ] Under 800 lines
- [ ] High signal-to-noise ratio
```

## ✅ Checklist de Implementação

### Fase 1: Auditoria (2-3h)
- [ ] Comparar CLAUDE.md seção "Storage Manager" com storage.py real
- [ ] Comparar seção "App Registry" com app_registry.py real
- [ ] Verificar se DNS-first está implementado (server_setup.py)
- [ ] Verificar estrutura de testes vs guidelines
- [ ] Listar inconsistências em AUDIT.md temporário
- [ ] Identificar código duplicado (grep, manual review)

### Fase 2: Renomeação e Criação (1h)
- [ ] `git mv CLAUDE.md CLAUDE-LEGACY.md`
- [ ] Criar novo CLAUDE.md com estrutura enxuta
- [ ] Criar TECH-DEBT.md inicial
- [ ] Criar docs/ARCHITECTURE.md (detalhes técnicos)

### Fase 3: Migração de Conteúdo (3-4h)
- [ ] Migrar "Executive Summary" (validar com realidade)
- [ ] Migrar "Architecture" (simplificar, apenas diagrama + stack)
- [ ] Migrar "Core Components" (apenas implementados, sem exemplos longos)
- [ ] Migrar "File Structure" (validar com `tree`)
- [ ] Migrar "Development Practices" (guidelines essenciais)
- [ ] Migrar "API Design" (apenas endpoints reais)
- [ ] Adicionar seção "Meta-Documentation"

### Fase 4: Validação (1h)
- [ ] Verificar total de linhas < 800
- [ ] Testar: pedir para AI ler CLAUDE.md e implementar feature nova
- [ ] Verificar se AI consegue navegar sem confusão
- [ ] Revisar com olhar crítico: tudo é essencial?

### Fase 5: Documentação Complementar (2h)
- [ ] Preencher TECH-DEBT.md com issues encontrados
- [ ] Criar docs/ARCHITECTURE.md com detalhes técnicos
- [ ] Criar docs/TESTING.md com estratégias completas
- [ ] Atualizar README.md se necessário

## 📦 Dependências

- Nenhuma dependência externa
- Ferramentas: editor de texto, grep, tree

## 🎯 Critérios de Sucesso

1. ✅ Novo CLAUDE.md < 800 linhas
2. ✅ Sem informações desatualizadas
3. ✅ Todos os componentes IMPLEMENTADOS documentados
4. ✅ Componentes NÃO implementados removidos ou marcados [PLANEJADO]
5. ✅ TECH-DEBT.md criado com issues identificados
6. ✅ AI consegue usar novo CLAUDE.md sem confusão

## 📊 Métricas

- **Redução de linhas**: 1051 → < 800 (24% redução)
- **Precisão**: 100% das informações refletem código real
- **Usabilidade**: AI completa tarefa usando apenas CLAUDE.md em < 5 interações
- **Manutenibilidade**: Guidelines claros para atualização

## ⚠️ Considerações Importantes

1. **Não deletar CLAUDE-LEGACY.md** - manter como referência histórica
2. **Priorizar qualidade sobre quantidade** - menos é mais
3. **Validar cada afirmação com código real** - zero especulação
4. **Separar "O que é" de "O que será"** - CLAUDE.md só estado atual
5. **Mover detalhes para docs/** - CLAUDE.md é índice, não manual

## 🚀 Próximos Passos Após Este Plan

Após atualizar CLAUDE.md:
- Plan 08: Code Quality Improvements (baseado em TECH-DEBT.md)
- Plan 09: Test Coverage Enhancement
- Plan 10: Documentation Sprint (docs/)

## 📊 Status

- 🔵 **READY TO START**
- Criado: 2025-10-19
- Estimativa: 8-10 horas de trabalho focado
- Prioridade: ALTA (fundação para melhorias futuras)

---

**Nota:** Este plano estabelece a FUNDAÇÃO para garantir que:
1. AI tem contexto preciso
2. Desenvolvedores sabem estado real do projeto
3. Débitos técnicos estão rastreados
4. Processo de manutenção está claro
