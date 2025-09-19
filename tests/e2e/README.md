# 🧪 Testes E2E - Workflow de Monitoramento

## 🎯 Configuração Padrão do Servidor

**IMPORTANTE**: Todos os testes devem usar esta configuração:

```yaml
Servidor: server-e2e-test
Tipo: CCX23 (4 vCPU AMD, 16GB RAM, 80GB NVMe)
OS: Debian 12
Região: ash (Ashburn, VA)
SSH Key: server-e2e-test_key
Custo: €0.026/hora
```

## 🚀 Workflow de Execução com Monitoramento

### 1. Setup Inicial

```bash
# Ativar ambiente virtual
source venv/bin/activate

# Configurar credenciais (se necessário)
export HETZNER_TOKEN="seu-token"
export LIVCHAT_E2E_REAL=true
export PYTHONPATH=/home/pedro/dev/sandbox/LivChatSetup
```

### 2. Executar Teste em Background

```bash
# Iniciar teste completo em background
pytest tests/e2e/test_complete_workflow.py::TestRealInfrastructure::test_real_complete_app_deployment_flow \
    -xvs --tb=line --timeout=1800 > test.log 2>&1 &

# Capturar o PID
TEST_PID=$!
echo "🚀 Teste iniciado com PID: $TEST_PID"
```

### 3. Monitoramento com Sleep Visual

```bash
# Sleep com progresso visual (RECOMENDADO)
echo "⏰ Aguardando 60 segundos..." && sleep 60 && echo "✅ 60 segundos completos"

# Sleep mais longo
echo "⏰ Aguardando 90 segundos para Docker/Swarm..." && sleep 90 && echo "✅ Verificando..."

# Sleep com múltiplas etapas
for i in 1 2 3; do
    echo "⏰ Etapa $i/3: Aguardando 60s..."
    sleep 60
    echo "✅ Etapa $i completa"
    tail -20 test.log | grep -E "(Criando|Docker|Portainer|PASSED|FAILED)"
done
```

### 4. Verificar Progresso em Tempo Real

```bash
# Ver últimas linhas do log
tail -f test.log | grep --color=auto -E "(✓|✅|❌|PASSED|FAILED|ERROR)"

# Filtrar por componente específico
tail -100 test.log | grep -i portainer

# Verificar se ainda está rodando
ps -p $TEST_PID && echo "🔄 Ainda executando..." || echo "✅ Finalizado"
```

## 📊 Usando Background Bash do Claude

```python
# 1. Iniciar teste em background
from subprocess import Popen
process = Popen([
    'pytest',
    'tests/e2e/test_complete_workflow.py::TestRealInfrastructure::test_real_complete_app_deployment_flow',
    '-xvs', '--tb=line'
], stdout=PIPE, stderr=PIPE, text=True)

# 2. Monitorar com sleep
import time
for i in range(5):
    time.sleep(60)
    print(f"⏰ Minuto {i+1}/5 - Teste em execução...")

# 3. Verificar resultado
if process.poll() is None:
    print("🔄 Ainda rodando...")
else:
    print(f"✅ Finalizado com código: {process.returncode}")
```

## 🔍 Comandos de Monitoramento Úteis

```bash
# Status do servidor na Hetzner
hcloud server describe server-e2e-test

# Verificar Traefik
ssh -i /tmp/*/ssh_keys/server-e2e-test_key root@IP "docker service ls"

# Verificar Portainer
curl -k https://IP:9443/api/system/status

# Logs do Docker
ssh -i /tmp/*/ssh_keys/server-e2e-test_key root@IP "docker service logs traefik_traefik"
```

## ⏱️ Tempos Esperados

| Etapa | Tempo | Visual |
|-------|-------|--------|
| Criar servidor | ~20s | `🖥️ Criando...` |
| SSH disponível | ~30s | `🔑 Aguardando SSH...` |
| Base setup | ~2min | `🔧 Setup base...` |
| Docker install | ~1.5min | `🐳 Docker...` |
| Swarm init | ~30s | `🐝 Swarm...` |
| Traefik | ~30s | `🔀 Traefik...` |
| Portainer | ~1min | `📊 Portainer...` |
| **Total** | **~6min** | `✅ Completo` |

## 🐛 Debug Rápido

```bash
# Se o teste falhar, verificar servidor
hcloud server list | grep e2e

# SSH direto no servidor
ssh -i /tmp/livchat*/ssh_keys/server-e2e-test_key root@$(hcloud server ip server-e2e-test)

# Ver estado dos serviços
docker stack ls
docker service ls

# Limpar servidor se necessário
hcloud server delete server-e2e-test
```

## ⚠️ Problemas Conhecidos

1. **DNS Cloudflare**: API error `'SyncV4PagePaginationArray[Zone]' object is not subscriptable`
2. **Portainer YAML**: Erro na linha 62 do template
3. **Servidor diferente**: Teste completo criando configs diferentes do padrão

## 🎯 Comando Recomendado para Teste Completo

```bash
# Setup completo com monitoramento visual
export LIVCHAT_E2E_REAL=true && \
pytest tests/e2e/test_complete_workflow.py::TestRealInfrastructure::test_real_complete_app_deployment_flow \
    -xvs --tb=line --timeout=1800 &

# Monitorar com sleep visual
for i in {1..10}; do
    echo "⏰ [$i/10] Aguardando 30s..." && sleep 30
    echo "📊 Status:" && ps aux | grep pytest | head -1
done
```

---

**Versão**: 3.0.0
**Foco**: Workflow de Monitoramento com Sleep Visual
**Última atualização**: 2025-01-19