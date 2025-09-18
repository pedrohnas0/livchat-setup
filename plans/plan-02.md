# Plan 02: Ansible Runner + SSH Keys + Base Infrastructure

## 📋 Contexto

Conforme **CLAUDE.md Phase 2**, precisamos implementar:
- ✅ Hetzner provider (já temos)
- ⏳ **Ansible runner** (foco principal)
- ✅ Dependency resolver (básico já implementado)
- ⏳ **Basic apps** (começar com Traefik)

## 🎯 Objetivo

Implementar **Ansible Runner** com **SSH Key Management** para conseguir fazer o setup remoto completo de um servidor com Traefik rodando.

## 📊 Escopo Definitivo

### Componente 1: SSH Key Manager [Dia 1 - Manhã]

```python
# src/ssh_manager.py
class SSHKeyManager:
    """Gerencia chaves SSH localmente e nos providers"""

    def generate_key_pair(self, name: str) -> Dict[str, str]:
        """Gera par Ed25519 usando cryptography"""

    def save_key(self, name: str, private_key: str, public_key: str):
        """Salva em ~/.livchat/ssh_keys/ com permissão 600"""

    def get_public_key(self, name: str) -> str:
        """Retorna chave pública para adicionar ao provider"""

    def delete_key(self, name: str):
        """Remove chave local e do provider"""
```

**Por que simples?** Só precisamos gerar chaves e adicionar ao Hetzner. Sem complexidade extra.

### Componente 2: Ansible Runner [Dia 1 - Tarde + Dia 2]

```python
# src/ansible_runner.py
class AnsibleRunner:
    """Executa playbooks Ansible via Python API"""

    def __init__(self, ssh_manager: SSHKeyManager):
        self.ssh_manager = ssh_manager

    def create_inventory(self, servers: List[Dict]) -> str:
        """Gera inventory dinâmico"""

    def run_playbook(self,
                    playbook_path: str,
                    inventory: Dict,
                    extra_vars: Dict = None) -> Result:
        """Executa playbook usando ansible-runner"""

    def run_adhoc(self,
                  host: str,
                  module: str,
                  args: str) -> Result:
        """Executa comando adhoc (para testes rápidos)"""
```

**Tecnologia:** `ansible-runner` (wrapper oficial da Red Hat)

### Componente 3: Playbooks Base [Dia 2 - Tarde]

```yaml
# ansible/playbooks/base-setup.yml
---
- name: Setup Base do Servidor
  hosts: all
  tasks:
    - name: Update packages
      apt:
        update_cache: yes
        upgrade: dist

    - name: Set timezone
      timezone:
        name: America/Sao_Paulo

    - name: Install base packages
      apt:
        name: [apt-utils, apparmor-utils, curl, wget]
```

```yaml
# ansible/playbooks/docker-install.yml
---
- name: Install Docker
  hosts: all
  tasks:
    - name: Install Docker via get.docker.com
      shell: curl -fsSL https://get.docker.com | bash

    - name: Start Docker service
      systemd:
        name: docker
        state: started
        enabled: yes
```

```yaml
# ansible/playbooks/swarm-init.yml
---
- name: Initialize Docker Swarm
  hosts: all
  tasks:
    - name: Init swarm
      docker_swarm:
        state: present
        advertise_addr: "{{ ansible_default_ipv4.address }}"
```

### Componente 4: Server Setup [Dia 3]

```python
# src/server_setup.py
class ServerSetup:
    """Orquestra setup completo do servidor"""

    def __init__(self, ansible_runner: AnsibleRunner):
        self.runner = ansible_runner

    def setup_base(self, server: Dict) -> Result:
        """Executa base-setup.yml"""

    def install_docker(self, server: Dict) -> Result:
        """Executa docker-install.yml"""

    def init_swarm(self, server: Dict) -> Result:
        """Executa swarm-init.yml"""

    def deploy_traefik(self, server: Dict, config: Dict) -> Result:
        """Deploy Traefik via docker stack"""

    def full_setup(self, server: Dict) -> Result:
        """Executa setup completo em ordem"""
        steps = [
            self.setup_base,
            self.install_docker,
            self.init_swarm,
            self.deploy_traefik
        ]
        for step in steps:
            result = step(server)
            if not result.success:
                return result
        return Result(success=True)
```

### Componente 5: Integration [Dia 4]

```python
# src/orchestrator.py (atualizar)
class Orchestrator:
    def __init__(self):
        self.storage = StorageManager()
        self.ssh_manager = SSHKeyManager()  # NOVO
        self.ansible_runner = AnsibleRunner(self.ssh_manager)  # NOVO
        self.server_setup = ServerSetup(self.ansible_runner)  # NOVO

    def setup_server(self, server_name: str) -> bool:
        """Setup completo do servidor"""
        # 1. Pegar info do servidor
        server = self.storage.state.get_server(server_name)

        # 2. Garantir que temos SSH key
        if not self.ssh_manager.has_key(server_name):
            self.ssh_manager.generate_key_pair(server_name)

        # 3. Executar setup
        result = self.server_setup.full_setup(server)

        # 4. Atualizar state
        if result.success:
            self.storage.state.update_server(server_name, {
                "status": "ready",
                "apps": ["traefik"]
            })

        return result.success
```

## 🧪 Estratégia de Testes com TDD

### Dia 1: SSH Manager
```python
# tests/unit/test_ssh_manager.py
def test_generate_ed25519_key():
    """Testa geração de chave Ed25519"""

def test_save_key_with_permissions():
    """Verifica permissão 600 no arquivo"""

def test_get_public_key_format():
    """Verifica formato OpenSSH da chave pública"""
```

### Dia 2: Ansible Runner
```python
# tests/unit/test_ansible_runner.py
def test_create_inventory():
    """Testa geração de inventory"""

def test_run_playbook_mock():
    """Mock do ansible-runner"""

@pytest.mark.integration
def test_ansible_ping():
    """Teste real com módulo ping"""
```

### Dia 3: Server Setup
```python
# tests/unit/test_server_setup.py
def test_setup_sequence():
    """Verifica ordem de execução"""

def test_error_handling():
    """Testa tratamento de erros"""
```

### Dia 4: Integration
```python
# tests/integration/test_full_setup.py
@pytest.mark.slow
def test_complete_server_setup():
    """Teste end-to-end com servidor mock"""
```

## 📦 Dependências Novas

```txt
# requirements.txt
ansible-core>=2.16.0     # Core do Ansible
ansible-runner>=2.3.0    # Python API oficial
jinja2>=3.1.0           # Para templates (já deve ter)
```

## 📁 Estrutura de Arquivos

```
LivChatSetup/
├── src/
│   ├── ssh_manager.py      # NOVO
│   ├── ansible_runner.py   # NOVO
│   ├── server_setup.py     # NOVO
│   └── orchestrator.py     # ATUALIZAR
│
├── ansible/                 # NOVO
│   ├── playbooks/
│   │   ├── base-setup.yml
│   │   ├── docker-install.yml
│   │   ├── swarm-init.yml
│   │   └── traefik-deploy.yml
│   └── inventory/
│       └── hosts.yml       # Gerado dinamicamente
│
├── templates/              # NOVO
│   └── traefik-stack.j2   # Template para Traefik
│
└── tests/
    ├── unit/
    │   ├── test_ssh_manager.py     # NOVO
    │   ├── test_ansible_runner.py  # NOVO
    │   └── test_server_setup.py    # NOVO
    └── integration/
        └── test_full_setup.py       # NOVO
```

## 🎮 CLI Commands

```bash
# Novos comandos
livchat-setup setup-server <name>     # Setup completo
livchat-setup server-status <name>    # Verificar status
livchat-setup ssh-key generate <name> # Gerar chave SSH
```

## ✅ Checklist de Implementação

### Dia 1 (4h)
- [ ] Implementar SSHKeyManager com TDD
- [ ] Implementar AnsibleRunner básico
- [ ] Testes unitários passando

### Dia 2 (4h)
- [ ] Completar AnsibleRunner
- [ ] Criar playbooks base
- [ ] Teste de integração com Ansible

### Dia 3 (4h)
- [ ] Implementar ServerSetup
- [ ] Template do Traefik
- [ ] Integração com Orchestrator

### Dia 4 (4h)
- [ ] Comandos CLI
- [ ] Testes end-to-end
- [ ] Documentação
- [ ] Code review

## 🎯 Critério de Sucesso

```bash
# Deve funcionar completamente:
livchat-setup create-server test-srv --type cx21
livchat-setup setup-server test-srv

# Verificar:
ssh -i ~/.livchat/ssh_keys/test-srv root@<ip> "docker stack ls"
# Deve mostrar: traefik

curl -I https://<ip>
# Deve retornar 404 do Traefik (não erro de conexão)
```

## 📊 Métricas

- Setup completo: <10 minutos
- Taxa de sucesso: >95%
- Cobertura de testes: >85%
- Ansible playbooks: 100% idempotentes

## ⚠️ Considerações Importantes

1. **Ansible-runner** é o wrapper oficial, mais estável que usar a API diretamente
2. **Playbooks simples** primeiro, complexidade vem depois
3. **Idempotência** desde o início - poder rodar várias vezes
4. **Logs detalhados** do Ansible para debug

## 🚀 Próximos Passos (Plan-03)

1. Deploy do Portainer
2. App Registry com YAML
3. Deploy de apps reais (Postgres, Redis, N8N)
4. Integração com Portainer API

---

*Versão: 2.0.0*
*Data: 2024-12-17*
*Status: Alinhado com CLAUDE.md Phase 2*
*Abordagem: Ansible-first, sem hibridismo*