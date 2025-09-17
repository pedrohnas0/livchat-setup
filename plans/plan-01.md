# Plan 01: Refatoração Arquitetural

## 📋 Status Atual
✅ **MVP Implementado e Funcional** - O código base está 100% implementado e testado:
- ConfigManager, StateManager, SecretsManager funcionando
- HetznerProvider implementado com hcloud SDK
- CLI básico operacional
- Estrutura de persistência em ~/.livchat/ funcionando

## 🎯 Objetivo da Refatoração
Reorganizar o código existente para seguir a arquitetura definida em CLAUDE.md, mantendo toda a funcionalidade atual mas com estrutura mais escalável e profissional.

## 🔄 De → Para

### Estrutura Atual (Funcional mas Desorganizada)
```
src/
├── __init__.py      # 160 linhas - fazendo papel de orchestrator ❌
├── config.py        # ConfigManager separado
├── state.py         # StateManager separado
├── vault.py         # SecretsManager (deveria ser secrets.py)
├── cli.py          # CLI entry point
└── providers/
    ├── __init__.py  # Interface base
    └── hetzner.py   # Provider implementado
```

### Nova Estrutura (Arquitetura Limpa)
```
src/
├── __init__.py          # APENAS exports públicos (~20 linhas)
├── orchestrator.py      # Core + DependencyResolver (~200 linhas)
├── storage.py           # ConfigStore + StateStore + SecretsStore (~400 linhas)
├── cli.py              # Mantém como está
├── providers/          # Mantém estrutura
│   ├── __init__.py
│   ├── base.py         # Extrair interface para arquivo próprio
│   └── hetzner.py
├── integrations/       # CRIAR estrutura para futuras integrações
│   └── __init__.py
└── api/                # CRIAR estrutura para futura API
    └── __init__.py
```

## ✅ Checklist de Refatoração

### Fase 1: Preparação [30 min]
- [ ] Criar branch `refactor/architecture`
- [ ] Fazer backup completo do código atual
- [ ] Criar estruturas de diretórios faltantes:
  - [ ] `src/integrations/`
  - [ ] `src/api/`
- [ ] Instalar dependências adicionais se necessário

### Fase 2: Unificar Storage [1h]
- [ ] Criar `src/storage.py` com estrutura unificada:
  ```python
  class ConfigStore:  # Mover de config.py
  class StateStore:   # Mover de state.py
  class SecretsStore: # Mover de vault.py

  class StorageManager:  # Nova classe unificadora
      def __init__(self):
          self.config = ConfigStore()
          self.state = StateStore()
          self.secrets = SecretsStore()
  ```
- [ ] Migrar código de `config.py` → `ConfigStore`
- [ ] Migrar código de `state.py` → `StateStore`
- [ ] Migrar código de `vault.py` → `SecretsStore`
- [ ] Adicionar interface unificada no `StorageManager`
- [ ] Remover arquivos antigos após validação

### Fase 3: Refatorar Orchestrator [45 min]
- [ ] Criar `src/orchestrator.py`
- [ ] Mover lógica de `__init__.py:LivChatSetup` → `orchestrator.py:Orchestrator`
- [ ] Adicionar `DependencyResolver` no mesmo arquivo:
  ```python
  class DependencyResolver:
      def resolve_install_order(self, apps: List[str]) -> List[str]
      def validate_dependencies(self, app: str) -> bool

  class Orchestrator:  # Antiga LivChatSetup
      def __init__(self):
          self.storage = StorageManager()
          self.resolver = DependencyResolver()
  ```
- [ ] Atualizar imports em todos os lugares que usam

### Fase 4: Limpar __init__.py [15 min]
- [ ] Reduzir `__init__.py` para apenas exports:
  ```python
  """LivChat Setup - Automated server setup and deployment"""

  from .orchestrator import Orchestrator
  from .storage import StorageManager

  __version__ = "0.1.0"
  __all__ = ["Orchestrator", "StorageManager"]
  ```

### Fase 5: Organizar Providers [20 min]
- [ ] Criar `src/providers/base.py`
- [ ] Mover `ProviderInterface` de `__init__.py` → `base.py`
- [ ] Atualizar imports em `hetzner.py`
- [ ] Garantir que `providers/__init__.py` exporta corretamente

### Fase 6: Atualizar Imports e CLI [30 min]
- [ ] Atualizar `cli.py` para usar novos imports:
  ```python
  from orchestrator import Orchestrator
  # ao invés de
  from __init__ import LivChatSetup
  ```
- [ ] Atualizar `setup.py` se necessário
- [ ] Verificar todos os imports cruzados

### Fase 7: Testes de Regressão [30 min]
- [ ] Teste 1: Inicialização
  ```bash
  python -c "from src.orchestrator import Orchestrator; o = Orchestrator(); o.init()"
  ```
- [ ] Teste 2: CLI funciona
  ```bash
  python src/cli.py init
  python src/cli.py list-servers
  ```
- [ ] Teste 3: Criação de servidor (mock)
- [ ] Teste 4: Persistência funciona
- [ ] Teste 5: Secrets continuam criptografados

### Fase 8: Documentação e Cleanup [20 min]
- [ ] Atualizar docstrings nos novos arquivos
- [ ] Remover arquivos antigos:
  - [ ] `config.py`
  - [ ] `state.py`
  - [ ] `vault.py`
- [ ] Atualizar README.md com novos imports
- [ ] Commit com mensagem clara sobre refatoração

## 🧪 Validação Pós-Refatoração

### Teste de Fumaça Completo
```python
# Deve funcionar exatamente como antes
from src.orchestrator import Orchestrator

# 1. Inicializar
setup = Orchestrator()
setup.init()

# 2. Verificar estrutura ~/.livchat/
assert Path("~/.livchat/config.yaml").exists()
assert Path("~/.livchat/state.json").exists()
assert Path("~/.livchat/credentials.vault").exists()

# 3. Configurar provider
setup.configure_provider("hetzner", "test_token")

# 4. Verificar persistência
setup2 = Orchestrator()
token = setup2.storage.secrets.get_secret("hetzner_token")
assert token == "test_token"

print("✅ Refatoração bem-sucedida!")
```

### Verificação de Imports
```python
# Todos esses imports devem funcionar
from src.orchestrator import Orchestrator, DependencyResolver
from src.storage import StorageManager, ConfigStore, StateStore, SecretsStore
from src.providers.base import ProviderInterface
from src.providers.hetzner import HetznerProvider
from src.integrations import *  # Preparado para futuro
from src.api import *  # Preparado para futuro
```

## 📊 Critérios de Sucesso

1. ✅ TODO o código Python dentro de `src/`
2. ✅ Nenhuma lógica de negócio em `__init__.py`
3. ✅ Storage unificado em um arquivo
4. ✅ Orchestrator explícito e encontrável
5. ✅ Todos os testes anteriores continuam passando
6. ✅ Estrutura pronta para crescer (integrations/, api/)
7. ✅ Imports mais claros e pythônicos

## ⚠️ Riscos e Mitigações

| Risco | Mitigação |
|-------|-----------|
| Quebrar funcionalidade existente | Backup completo + testes de regressão |
| Imports circulares | Cuidado com dependências, testar cada fase |
| Perder dados em ~/.livchat/ | Não tocar em ~/.livchat/, só no código |
| Conflitos de merge | Trabalhar em branch separada |

## 📅 Timeline Estimado

- **Total**: ~4 horas de trabalho focado
- **Fase 1-2**: 1h30 (Storage unificado)
- **Fase 3-4**: 1h (Orchestrator + cleanup)
- **Fase 5-6**: 50min (Providers + CLI)
- **Fase 7-8**: 50min (Testes + Docs)

## 🚀 Próximos Passos (Pós-Refatoração)

1. **Plan 02**: Implementar DependencyResolver completo
2. **Plan 03**: Adicionar primeiras integrações (Portainer, Cloudflare)
3. **Plan 04**: Criar API FastAPI básica
4. **Plan 05**: Implementar Ansible Runner

## 📝 Notas Importantes

- **NÃO** alterar a estrutura de ~/.livchat/ (já está funcionando)
- **NÃO** mudar a lógica de negócio, apenas reorganizar
- **SIM** manter compatibilidade com código existente
- **SIM** fazer commits incrementais para poder reverter

---

*Última atualização: 2024-12-17*
*Status: Pronto para Execução*
*Tipo: Refatoração Arquitetural*