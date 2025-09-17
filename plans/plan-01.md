# Plan 01: Setup Inicial + Primeiro Servidor Hetzner

## 📋 Resumo
Implementar a base do LivChat Setup com foco em simplicidade: configuração inicial, gerenciamento de estado e criação do primeiro servidor na Hetzner.

## 🎯 Objetivo do Sprint
Conseguir executar:
```python
from livchat import LivChatSetup

setup = LivChatSetup()
setup.init()
setup.configure_provider("hetzner", token="xxx")
server = setup.create_server("test-01", "cx21", "nbg1")
print(f"Server created: {server['ip']}")
```

## 📁 Estruturas de Dados (Versões Simples)

### `.livchat/config.yaml`
```yaml
version: 1
provider: hetzner
region: nbg1
server_type: cx21
```

### `.livchat/state.json`
```json
{
  "servers": {
    "test-01": {
      "provider": "hetzner",
      "id": "12345",
      "ip": "1.2.3.4",
      "type": "cx21",
      "region": "nbg1",
      "created_at": "2024-12-16T10:00:00Z"
    }
  }
}
```

### `.livchat/credentials.vault`
```
Arquivo criptografado com Ansible Vault contendo:
{
  "hetzner_token": "xxx",
  "cloudflare_token": "yyy"
}
```

## ✅ Checklist de Implementação

### Fase 1: Estrutura Base
- [ ] Criar estrutura de diretórios do projeto
- [ ] Criar `requirements.txt` com dependências iniciais
- [ ] Criar `setup.py` para instalação
- [ ] Criar `__init__.py` com classe principal `LivChatSetup`
- [ ] Implementar logging básico

### Fase 2: Gerenciamento de Configuração
- [ ] Criar classe `ConfigManager`
  - [ ] Método `init()` - criar `.livchat/`
  - [ ] Método `load_config()` - ler `config.yaml`
  - [ ] Método `save_config()` - salvar `config.yaml`
  - [ ] Método `get(key)` - buscar configuração
  - [ ] Método `set(key, value)` - atualizar configuração

### Fase 3: Gerenciamento de Estado
- [ ] Criar classe `StateManager`
  - [ ] Método `load_state()` - ler `state.json`
  - [ ] Método `save_state()` - salvar `state.json`
  - [ ] Método `add_server(server_data)` - adicionar servidor
  - [ ] Método `get_server(name)` - buscar servidor
  - [ ] Método `list_servers()` - listar todos
  - [ ] Método `remove_server(name)` - remover servidor

### Fase 4: Gerenciamento de Secrets
- [ ] Criar classe `SecretsManager`
  - [ ] Método `init_vault()` - criar senha do vault
  - [ ] Método `encrypt(data)` - criptografar dados
  - [ ] Método `decrypt()` - decriptar vault
  - [ ] Método `set_secret(key, value)` - adicionar secret
  - [ ] Método `get_secret(key)` - buscar secret

### Fase 5: Provider Hetzner
- [ ] Criar classe `HetznerProvider`
  - [ ] Método `__init__(token)` - inicializar com token
  - [ ] Método `create_server(name, type, location)` - criar servidor
  - [ ] Método `list_servers()` - listar servidores
  - [ ] Método `get_server(id)` - buscar servidor
  - [ ] Método `delete_server(id)` - deletar servidor
  - [ ] Tratamento de erros da API

### Fase 6: Integração
- [ ] Conectar `LivChatSetup` com todos os managers
- [ ] Implementar fluxo completo de criação
- [ ] Adicionar validações
- [ ] Implementar rollback em caso de erro

## 🧪 Testes de Validação

### Teste 1: Inicialização
```python
def test_init():
    """Verifica se .livchat/ é criado corretamente"""
    setup = LivChatSetup()
    setup.init()

    assert Path("~/.livchat").exists()
    assert Path("~/.livchat/config.yaml").exists()
    assert Path("~/.livchat/state.json").exists()
    print("✅ Inicialização OK")
```

### Teste 2: Configuração
```python
def test_config():
    """Verifica leitura e escrita de configurações"""
    setup = LivChatSetup()

    # Escrever
    setup.config.set("test_key", "test_value")

    # Ler
    value = setup.config.get("test_key")
    assert value == "test_value"

    # Persistência
    setup2 = LivChatSetup()
    assert setup2.config.get("test_key") == "test_value"
    print("✅ Configuração OK")
```

### Teste 3: Secrets
```python
def test_secrets():
    """Verifica criptografia e decriptografia"""
    setup = LivChatSetup()

    # Salvar secret
    setup.secrets.set_secret("test_token", "secret123")

    # Recuperar
    token = setup.secrets.get_secret("test_token")
    assert token == "secret123"

    # Verificar que está criptografado no arquivo
    with open("~/.livchat/credentials.vault", "r") as f:
        content = f.read()
        assert "secret123" not in content
    print("✅ Secrets OK")
```

### Teste 4: Estado
```python
def test_state():
    """Verifica gerenciamento de estado"""
    setup = LivChatSetup()

    # Adicionar servidor
    server_data = {
        "provider": "hetzner",
        "id": "123",
        "ip": "1.2.3.4",
        "type": "cx21"
    }
    setup.state.add_server("test-01", server_data)

    # Recuperar
    server = setup.state.get_server("test-01")
    assert server["ip"] == "1.2.3.4"

    # Listar
    servers = setup.state.list_servers()
    assert len(servers) == 1
    print("✅ Estado OK")
```

### Teste 5: Criação Real (Hetzner)
```python
def test_create_server_real():
    """Teste E2E com Hetzner real (requer token válido)"""
    setup = LivChatSetup()

    # Configurar token (manual para teste)
    token = input("Digite o token Hetzner: ")
    setup.configure_provider("hetzner", token)

    # Criar servidor
    server = setup.create_server(
        name="test-livchat-01",
        type="cx21",
        region="nbg1"
    )

    assert server["ip"] is not None
    assert server["id"] is not None

    # Verificar no estado
    saved = setup.state.get_server("test-livchat-01")
    assert saved["ip"] == server["ip"]

    # Cleanup
    setup.delete_server("test-livchat-01")
    print("✅ Criação real OK")
```

### Teste 6: Fluxo Completo
```python
def test_complete_flow():
    """Teste do fluxo completo do usuário"""
    # 1. Nova instalação
    setup = LivChatSetup()
    setup.init()

    # 2. Configurar provider
    setup.configure_provider("hetzner", "fake_token")

    # 3. Verificar configuração salva
    assert setup.secrets.get_secret("hetzner_token") == "fake_token"

    # 4. Simular criação (mock)
    with mock.patch('hetzner.create_server'):
        server = setup.create_server("prod-01", "cx21", "nbg1")
        assert setup.state.get_server("prod-01") is not None

    print("✅ Fluxo completo OK")
```

## 📊 Critérios de Sucesso

1. ✅ `.livchat/` criado com estrutura correta
2. ✅ Configurações persistem entre execuções
3. ✅ Secrets são criptografados
4. ✅ Estado é mantido em `state.json`
5. ✅ Servidor criado na Hetzner com SDK oficial
6. ✅ Todos os testes passam

## 🚫 Fora de Escopo (Por Enquanto)

- Interface CLI completa
- Múltiplos providers
- Deploy de aplicações
- Integração com Ansible
- API REST
- MCP Server

## 📅 Timeline

- **Dia 1**: Estrutura base + ConfigManager + StateManager
- **Dia 2**: SecretsManager + HetznerProvider
- **Dia 3**: Integração + Testes + Refinamentos

## 🔄 Próximos Passos (Plan 02)

Após conclusão bem-sucedida:
1. Adicionar Ansible Runner
2. Implementar instalação do Docker/Traefik/Portainer
3. Sistema de dependências entre apps
4. Primeiras aplicações (postgres, redis)