# LivChat Setup - Test Standards

Este documento descreve os padrões de testes do projeto LivChat Setup.

## 📁 Estrutura

```
tests/
├── unit/              # Unit tests (isolados, mockados)
│   ├── api/          # API routes tests
│   ├── orchestrator/ # Orchestrator modules tests
│   ├── integrations/ # Portainer, Cloudflare tests
│   └── *.py          # Outros componentes
├── integration/       # Integration tests (múltiplos componentes)
└── e2e/              # End-to-end tests (sistema completo)
```

## 🧪 Padrões de Unit Tests

### 1. Performance Target
- **Meta**: < 0.05s por teste
- **Máximo aceitável**: < 0.5s por teste
- **Suite completa**: < 2 minutos

### 2. Mocking Pattern (IMPORTANTE!)

#### ✅ PADRÃO CORRETO
```python
from unittest.mock import MagicMock, AsyncMock, patch

# Use MagicMock SEM spec= (evita imports pesados)
mock_storage = MagicMock()
mock_storage.state = MagicMock()
mock_storage.state.get_server = MagicMock(return_value={"name": "test"})

# Use AsyncMock para métodos async
mock_client = MagicMock()
mock_client.deploy = AsyncMock(return_value={"success": True})

# SEMPRE mock time.sleep para evitar waits reais
@patch('time.sleep')
async def test_something(mock_sleep, ...):
    # Teste rápido sem esperar!
    pass
```

#### ❌ PADRÃO ERRADO
```python
# NÃO use spec= em unit tests (causa lentidão)
mock = Mock(spec=RealClass)  # ❌ Importa classe real!

# NÃO esqueça de mockar time.sleep
async def test_something(...):
    time.sleep(15)  # ❌ Teste vai demorar 15s!
```

### 3. Estrutura de Teste

```python
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

class TestMyComponent:
    """Test suite for MyComponent"""

    @pytest.fixture
    def mock_dependency(self):
        """Create mock dependency"""
        mock = MagicMock()
        mock.method = AsyncMock(return_value={"success": True})
        return mock

    @pytest.fixture
    def component(self, mock_dependency):
        """Create component instance with mocks"""
        from src.my_component import MyComponent
        return MyComponent(dependency=mock_dependency)

    @pytest.mark.asyncio
    @patch('time.sleep')  # Se componente usa time.sleep
    async def test_something(self, mock_sleep, component):
        """Test description"""
        # Given
        expected = "result"

        # When
        result = await component.do_something()

        # Then
        assert result == expected
```

## 📊 Checklist de Performance

Se seus testes estão lentos (> 2s), verifique:

- [ ] Todos os `time.sleep()` estão mockados?
- [ ] Usando `MagicMock()` ao invés de `Mock(spec=...)`?
- [ ] Métodos async usam `AsyncMock()`?
- [ ] Não está fazendo I/O real (HTTP, filesystem)?
- [ ] Imports estão dentro das funções de teste quando possível?

## 🎯 Exemplos Reais do Projeto

### Exemplo 1: Portainer Tests (RÁPIDO ✅)
**Tempo**: 11 testes em 0.34s (média 0.03s/teste)

```python
# tests/unit/integrations/test_portainer.py
@pytest.mark.asyncio
async def test_authentication_success(client):
    # Mock direto no método do cliente
    client._request = AsyncMock(return_value=mock_response)

    token = await client.authenticate()

    assert token == "token123"
```

### Exemplo 2: DeploymentManager Tests (RÁPIDO ✅)
**Tempo**: 11 testes em 0.39s (média 0.035s/teste)

```python
# tests/unit/orchestrator/test_deployment_manager.py
@pytest.mark.asyncio
@patch('time.sleep')  # Mock essencial!
async def test_deploy_app_success(mock_sleep, deployment_manager):
    result = await deployment_manager.deploy_app("server", "n8n")

    assert result["success"] is True
    assert mock_sleep.call_count == 2  # Postgres + Redis waits
```

## 🚨 Problemas Comuns

### Problema: Testes demoram 30s+
**Causa**: `time.sleep()` não mockado
**Solução**:
```python
@patch('time.sleep')
async def test_something(mock_sleep, ...):
    # Teste rápido!
```

### Problema: Testes demoram 10s+
**Causa**: Usando `Mock(spec=ClassName)` - importa classe real
**Solução**:
```python
# ANTES (lento)
mock = Mock(spec=StorageManager)

# DEPOIS (rápido)
mock = MagicMock()
```

### Problema: I/O real em unit tests
**Causa**: HTTP requests, file reads sem mock
**Solução**:
```python
# Mock o método, não a biblioteca!
client.fetch_data = AsyncMock(return_value={"data": "test"})
```

## 📚 Referências

- **CLAUDE.md**: Seção "Test-Before-Commit" com regras obrigatórias
- **pytest.ini**: Configurações do pytest
- **conftest.py**: Fixtures compartilhadas

---

**Última atualização**: 2025-10-19 (v0.2.5)
**Padrão estabelecido durante**: PLAN-08 (Refactoring Large Files)
