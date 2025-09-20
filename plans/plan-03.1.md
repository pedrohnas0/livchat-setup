# Plan 03.1: Unified Stack Definitions Architecture

## 📋 Contexto

### Referência
- **CLAUDE.md**: Design document principal
- **Plan-03**: Integrations (Portainer, Cloudflare, App Registry) ✅ COMPLETED
- **Status Atual**: Inconsistência arquitetural identificada

### Problema Identificado
1. **Duplicação**: Portainer existe em `templates/` e `apps/definitions/infrastructure/`
2. **Inconsistência**: Traefik está inline no playbook, não em template
3. **Complexidade**: 3 métodos diferentes de definir stacks
4. **Desvio do CLAUDE.md**: `templates/traefik-stack.j2` mencionado mas não existe

### Descoberta Atual
```
templates/portainer-stack.j2         → Usado pelo Ansible
apps/definitions/infrastructure/     → Duplicação (portainer.yaml)
ansible/playbooks/traefik-deploy.yml → Stack inline (linha 31-105)
```

## 🎯 Objetivo

**Unificar TODAS as definições de stacks em `apps/definitions/` com formato YAML padronizado, eliminando duplicação e complexidade.**

### Metas Específicas
1. Centralizar todas as stacks em um único local
2. Padronizar formato YAML para todas as definições
3. Eliminar diretório `templates/`
4. Manter separação lógica: infraestrutura vs aplicações
5. Simplificar manutenção e extensibilidade

## 📊 Escopo Definitivo

### Nova Estrutura de Arquivos
```
apps/
├── catalog.yaml                    # Registry de todas as apps
└── definitions/
    ├── infrastructure/             # Deploy via Ansible
    │   ├── traefik.yaml           # CRIAR (migrar do inline)
    │   └── portainer.yaml         # AJUSTAR (já existe)
    ├── databases/                 # Deploy via Portainer API
    │   ├── postgres.yaml         # Manter
    │   └── redis.yaml           # Manter
    └── applications/            # Deploy via Portainer API
        ├── n8n.yaml            # Manter
        └── chatwoot.yaml      # Manter

# DELETAR:
templates/                    # Não mais necessário
```

### Formato YAML Unificado

#### Para Infraestrutura (deploy_method: ansible)
```yaml
# apps/definitions/infrastructure/traefik.yaml
name: traefik
category: infrastructure
version: "v3.2.3"
description: "Reverse proxy with automatic SSL via Let's Encrypt"

# Método de deploy determina o fluxo
deploy_method: ansible  # ou 'portainer' para apps

# Variáveis configuráveis com defaults
variables:
  network_name:
    default: "livchat_network"
    description: "Docker Swarm overlay network"
    required: false
  ssl_email:
    default: "admin@example.com"
    description: "Email for Let's Encrypt SSL certificates"
    required: true
  traefik_version:
    default: "v3.2.3"
    description: "Traefik version"
    required: false

# Requisitos do sistema
requirements:
  min_ram_mb: 128
  min_cpu_cores: 0.5
  ports:
    - 80
    - 443

# Docker Compose Stack (substituição de variáveis via environment)
compose: |
  version: "3.7"
  services:
    traefik:
      image: traefik:${TRAEFIK_VERSION:-v3.2.3}
      command:
        - "--api.dashboard=true"
        - "--providers.swarm=true"
        - "--providers.docker.endpoint=unix:///var/run/docker.sock"
        - "--providers.docker.exposedbydefault=false"
        - "--providers.docker.network=${NETWORK_NAME:-livchat_network}"
        - "--entrypoints.web.address=:80"
        - "--entrypoints.web.http.redirections.entryPoint.to=websecure"
        - "--entrypoints.web.http.redirections.entryPoint.scheme=https"
        - "--entrypoints.websecure.address=:443"
        - "--certificatesresolvers.letsencryptresolver.acme.httpchallenge=true"
        - "--certificatesresolvers.letsencryptresolver.acme.httpchallenge.entrypoint=web"
        - "--certificatesresolvers.letsencryptresolver.acme.storage=/etc/traefik/letsencrypt/acme.json"
        - "--certificatesresolvers.letsencryptresolver.acme.email=${SSL_EMAIL}"
        - "--log.level=INFO"
      volumes:
        - "vol_certificates:/etc/traefik/letsencrypt"
        - "/var/run/docker.sock:/var/run/docker.sock:ro"
      networks:
        - ${NETWORK_NAME:-livchat_network}
      ports:
        - target: 80
          published: 80
          mode: host
        - target: 443
          published: 443
          mode: host
      deploy:
        placement:
          constraints:
            - node.role == manager

  volumes:
    vol_certificates:
      external: true
      name: volume_swarm_certificates

  networks:
    ${NETWORK_NAME:-livchat_network}:
      external: true
      name: ${NETWORK_NAME:-livchat_network}
```

#### Para Aplicações (deploy_method: portainer)
```yaml
# apps/definitions/databases/postgres.yaml
name: postgres
category: database
version: "14-alpine"
description: "PostgreSQL database server"

deploy_method: portainer  # Via Portainer API

variables:
  postgres_password:
    required: true
    description: "Database root password"
  postgres_user:
    default: "postgres"
    description: "Database user"
  postgres_db:
    default: "postgres"
    description: "Default database name"

requirements:
  min_ram_mb: 256
  min_storage_gb: 1

dependencies: []  # Sem dependências

compose: |
  version: "3.8"
  services:
    postgres:
      image: postgres:14-alpine
      environment:
        POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
        POSTGRES_USER: ${POSTGRES_USER:-postgres}
        POSTGRES_DB: ${POSTGRES_DB:-postgres}
      volumes:
        - postgres_data:/var/lib/postgresql/data
      networks:
        - livchat_network
      deploy:
        replicas: 1
        restart_policy:
          condition: any

  volumes:
    postgres_data:
      driver: local

  networks:
    livchat_network:
      external: true
```

### Novo Sistema de Deploy Unificado

```python
# src/unified_deployer.py
class UnifiedDeployer:
    """Deploy unificado para todas as stacks"""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.registry = AppRegistry()

    async def deploy(self, app_name: str, server_name: str, config: Dict = None):
        """
        Deploy de qualquer stack baseado em deploy_method
        """
        # 1. Carregar definição
        app = self.registry.get_app(app_name)
        if not app:
            raise ValueError(f"App not found: {app_name}")

        # 2. Validar requisitos
        if not self.validate_requirements(app, server_name):
            raise ValueError(f"Server doesn't meet requirements for {app_name}")

        # 3. Preparar variáveis
        variables = self.prepare_variables(app, config)

        # 4. Deploy baseado no método
        deploy_method = app.get('deploy_method', 'portainer')

        if deploy_method == 'ansible':
            return await self.deploy_via_ansible(app, server_name, variables)
        else:
            return await self.deploy_via_portainer(app, server_name, variables)

    async def deploy_via_ansible(self, app, server_name, variables):
        """Deploy de infraestrutura via Ansible"""
        server = self.orchestrator.get_server(server_name)

        # 1. Substituir variáveis no compose
        compose = self.substitute_variables(app['compose'], variables)

        # 2. Salvar temporariamente
        temp_file = f"/tmp/{app['name']}-stack-{uuid4()}.yml"
        with open(temp_file, 'w') as f:
            f.write(compose)

        try:
            # 3. Deploy via playbook genérico
            result = self.orchestrator.ansible_runner.run_playbook(
                'generic-stack-deploy.yml',
                inventory={server_name: server},
                extra_vars={
                    'stack_name': app['name'],
                    'stack_file': temp_file,
                    'stack_variables': variables
                }
            )
            return result
        finally:
            # 4. Limpar arquivo temporário
            if os.path.exists(temp_file):
                os.remove(temp_file)

    async def deploy_via_portainer(self, app, server_name, variables):
        """Deploy de aplicação via Portainer API"""
        # Usar AppDeployer existente
        return await self.orchestrator.deploy_app(server_name, app['name'], variables)
```

## 🧪 Estratégia de Testes TDD

### Testes Unitários
```python
# tests/unit/test_unified_deployer.py
class TestUnifiedDeployer:
    """Testes para o novo sistema unificado"""

    def test_load_infrastructure_definition(self):
        """Testa carregamento de definição de infraestrutura"""
        registry = AppRegistry('tests/fixtures/apps')
        traefik = registry.get_app('traefik')

        assert traefik['name'] == 'traefik'
        assert traefik['deploy_method'] == 'ansible'
        assert 'compose' in traefik
        assert 'variables' in traefik

    def test_variable_substitution(self):
        """Testa substituição de variáveis no compose"""
        compose = "image: traefik:${VERSION:-v3}"
        variables = {'VERSION': 'v3.2.3'}

        result = substitute_variables(compose, variables)
        assert 'traefik:v3.2.3' in result

    @pytest.mark.asyncio
    async def test_deploy_via_ansible(self):
        """Testa deploy via Ansible"""
        deployer = UnifiedDeployer(mock_orchestrator)
        result = await deployer.deploy('traefik', 'test-server', {
            'ssl_email': 'test@example.com'
        })

        assert result['success'] is True
        assert result['method'] == 'ansible'

    @pytest.mark.asyncio
    async def test_deploy_via_portainer(self):
        """Testa deploy via Portainer"""
        deployer = UnifiedDeployer(mock_orchestrator)
        result = await deployer.deploy('postgres', 'test-server', {
            'postgres_password': 'secret'
        })

        assert result['success'] is True
        assert result['method'] == 'portainer'
```

### Testes de Integração
```python
# tests/integration/test_unified_system.py
def test_full_infrastructure_deploy():
    """Testa deploy completo de infraestrutura"""
    # 1. Criar servidor mock
    # 2. Deploy Traefik via ansible
    # 3. Deploy Portainer via ansible
    # 4. Verificar que ambos estão rodando

def test_app_deploy_after_infrastructure():
    """Testa deploy de app após infraestrutura"""
    # 1. Assumir infra pronta
    # 2. Deploy postgres via Portainer
    # 3. Deploy n8n com dependência
    # 4. Verificar resolução de dependências
```

## 📁 Estrutura de Arquivos

### Arquivos a Criar
```
apps/definitions/infrastructure/traefik.yaml    # Nova definição
ansible/playbooks/generic-stack-deploy.yml      # Playbook genérico
src/unified_deployer.py                        # Sistema unificado
tests/unit/test_unified_deployer.py           # Testes
```

### Arquivos a Modificar
```
apps/definitions/infrastructure/portainer.yaml  # Ajustar formato
src/app_registry.py                            # Suportar deploy_method
src/orchestrator.py                           # Integrar UnifiedDeployer
CLAUDE.md                                     # Atualizar documentação
```

### Arquivos a Deletar
```
templates/                                    # Todo o diretório
```

## ✅ Checklist de Implementação

### Etapa 1: Preparação e Testes
- [ ] Task 1: Criar testes unitários para UnifiedDeployer
- [ ] Task 2: Criar fixtures de teste com YAMLs exemplo
- [ ] Task 3: Implementar testes de substituição de variáveis

### Etapa 2: Migração de Definições
- [ ] Task 4: Extrair stack Traefik do playbook inline
- [ ] Task 5: Criar apps/definitions/infrastructure/traefik.yaml
- [ ] Task 6: Ajustar apps/definitions/infrastructure/portainer.yaml
- [ ] Task 7: Adicionar campo deploy_method em todos os YAMLs

### Etapa 3: Sistema de Deploy Unificado
- [ ] Task 8: Implementar src/unified_deployer.py
- [ ] Task 9: Criar ansible/playbooks/generic-stack-deploy.yml
- [ ] Task 10: Atualizar AppRegistry para suportar deploy_method
- [ ] Task 11: Integrar UnifiedDeployer no Orchestrator

### Etapa 4: Refatoração dos Playbooks
- [ ] Task 12: Modificar traefik-deploy.yml para usar YAML
- [ ] Task 13: Modificar portainer-deploy.yml para usar YAML
- [ ] Task 14: Testar deploy via novo sistema

### Etapa 5: Limpeza e Documentação
- [ ] Task 15: Deletar diretório templates/
- [ ] Task 16: Atualizar CLAUDE.md com nova arquitetura
- [ ] Task 17: Atualizar README com exemplos
- [ ] Task 18: Executar testes E2E completos

### Etapa 6: Validação Final
- [ ] Task 19: Deploy completo de servidor do zero
- [ ] Task 20: Verificar que todas as stacks funcionam
- [ ] Task 21: Documentar processo de migração

## 📦 Dependências Novas

Nenhuma dependência nova necessária. Usa bibliotecas já existentes:
- PyYAML (já instalado)
- Jinja2 (para substituição de variáveis)
- asyncio (já em uso)

## 🎮 CLI Commands

### Novos Comandos
```bash
# Deploy qualquer stack (infra ou app)
livchat deploy-stack <server> <stack-name> [--config JSON]

# Listar todas as stacks disponíveis
livchat list-stacks [--category infrastructure|database|application]

# Validar definição YAML
livchat validate-stack <stack-yaml-path>

# Exportar compose de uma stack
livchat export-compose <stack-name> [--variables JSON]
```

### Comandos Modificados
```bash
# deploy-app agora usa UnifiedDeployer internamente
livchat deploy-app <server> <app> [--config JSON]
```

## 🎯 Critérios de Sucesso

1. **Unificação Completa**: Todas as stacks em apps/definitions/
2. **Zero Duplicação**: Diretório templates/ removido
3. **Testes Passando**: 100% dos testes unitários e integração
4. **Deploy Funcional**: Traefik e Portainer via novo sistema
5. **Backward Compatible**: Apps existentes continuam funcionando
6. **Documentação Atualizada**: CLAUDE.md reflete nova arquitetura

## 📊 Métricas

- **Redução de Complexidade**: De 3 sistemas para 1
- **Redução de Arquivos**: -2 arquivos (templates/)
- **Aumento de Consistência**: 100% YAML
- **Tempo de Deploy**: Mantido ou melhorado
- **Cobertura de Testes**: > 80% no UnifiedDeployer

## ⚠️ Considerações Importantes

### Riscos
1. **Breaking Change**: Migração requer cuidado
2. **Variáveis de Ambiente**: Garantir substituição correta
3. **Backward Compatibility**: Manter apps funcionando durante migração

### Mitigações
1. **Testes Extensivos**: TDD approach
2. **Migração Gradual**: Uma stack por vez
3. **Rollback Plan**: Git branches para reverter se necessário

### Decisões Técnicas
1. **Variáveis**: Usar formato `${VAR:-default}` no compose
2. **Deploy Method**: Campo explícito determina fluxo
3. **Temporários**: Usar /tmp com UUID para evitar conflitos

## 🚀 Próximos Passos

Após conclusão deste plano:

1. **Plan-04**: MCP Gateway Implementation
2. **Plan-05**: Production Testing & Documentation
3. **Release v1.0**: Primera versão estável

## 📊 Status

- 🔵 **READY TO START**: Plano aprovado e pronto para execução
- Estimativa: 2-3 dias de desenvolvimento
- Prioridade: ALTA (resolve inconsistência arquitetural)

---

*Plan Version: 1.0.0*
*Created: 2024-12-19*
*Status: Ready for Implementation*